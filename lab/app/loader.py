"""
The data team's pipeline. Every few seconds:
  bronze  copy new rows from the shop's Postgres          (INSERT)
  silver  join the new orders with payments, customers,   (INSERT, partitioned by day + country)
          products
  gold    refresh revenue per day and country              (MERGE)
Silver and gold are refreshed only once they exist: you create them yourself
with sql/part1/04_silver_gold.sql, and the next run backfills and keeps them fresh.
Every statement is one commit: new data files, a manifest, a snapshot, a metadata.json.
Nothing here is wrong. Watch what it does to the files.

  python loader.py         run every LOAD_EVERY_SECONDS (0 = paused, load by hand instead)
  python loader.py once    run one load right now, then exit
"""
import os
import sys
import time

from common import CATALOG, SCHEMA, q, q1, trino_conn

EVERY = int(os.environ.get("LOAD_EVERY_SECONDS", "10"))

DDL = [
    f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}",
    f"""CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.orders (
        order_id BIGINT, customer_id BIGINT, product_id BIGINT, quantity INTEGER,
        amount DECIMAL(12,2), status VARCHAR, created_at TIMESTAMP(6))
        WITH (format = 'PARQUET', partitioning = ARRAY['day(created_at)'])""",
    f"""CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.payments (
        payment_id BIGINT, order_id BIGINT, method VARCHAR, amount DECIMAL(12,2),
        status VARCHAR, created_at TIMESTAMP(6))
        WITH (format = 'PARQUET', partitioning = ARRAY['day(created_at)'])""",
]

SILVER_INSERT = """
INSERT INTO lakehouse.silver.orders_enriched
SELECT o.order_id, o.created_at, CAST(o.created_at AS DATE),
       o.customer_id, c.name, c.country,
       o.product_id, pr.name, pr.category,
       o.quantity, o.amount, o.status, p.method, p.status
FROM lakehouse.bronze.orders o
LEFT JOIN lakehouse.bronze.payments p ON p.order_id = o.order_id
JOIN shop.public.customers c  ON c.customer_id = o.customer_id
JOIN shop.public.products  pr ON pr.product_id = o.product_id
WHERE o.order_id > {lo} AND o.order_id <= {hi}"""

GOLD_MERGE = """
MERGE INTO lakehouse.gold.daily_revenue t
USING (
    SELECT order_day, country,
           count(*)                           AS orders,
           CAST(sum(amount) AS DECIMAL(18,2)) AS revenue,
           count_if(order_status = 'paid')    AS paid_orders
    FROM lakehouse.silver.orders_enriched
    WHERE order_day >= (SELECT min(order_day) FROM lakehouse.silver.orders_enriched
                        WHERE order_id > {lo} AND order_id <= {hi})
    GROUP BY 1, 2
) s
ON t.order_day = s.order_day AND t.country = s.country
WHEN MATCHED THEN UPDATE SET orders = s.orders, revenue = s.revenue,
                             paid_orders = s.paid_orders, updated_at = localtimestamp(6)
WHEN NOT MATCHED THEN INSERT (order_day, country, orders, revenue, paid_orders, updated_at)
     VALUES (s.order_day, s.country, s.orders, s.revenue, s.paid_orders, localtimestamp(6))"""

SOURCES = {  # lakehouse table -> (source table, id column, columns)
    "orders": ("shop.public.orders", "order_id",
               "order_id, customer_id, product_id, quantity, amount, status, created_at"),
    "payments": ("shop.public.payments", "payment_id",
                 "payment_id, order_id, method, amount, status, created_at"),
}


def last_commit(conn, table):
    """What the latest commit did, from the table's own snapshot summary."""
    schema, name = table.split(".") if "." in table else ("bronze", table)
    summary = q(conn, f'SELECT summary FROM lakehouse.{schema}."{name}$snapshots" '
                      f'ORDER BY committed_at DESC LIMIT 1')[0][0]
    files = int(summary.get("total-data-files", 0))
    deletes = int(summary.get("total-delete-files", 0))
    avg_kb = int(summary.get("total-files-size", 0)) / max(files + deletes, 1) / 1024
    out = f"+{summary.get('added-data-files', 0)} file(s) → {files} files"
    if deletes:
        out += f" + {deletes} delete files"
    return out + f", avg {avg_kb:.0f} KB"


def table_exists(conn, schema, name):
    return q1(conn, f"SELECT count(*) FROM lakehouse.information_schema.tables "
                    f"WHERE table_schema = '{schema}' AND table_name = '{name}'") > 0


def load_once(conn, watermark):
    line = []
    for table, (src, col, cols) in SOURCES.items():
        hi = q1(conn, f"SELECT coalesce(max({col}), 0) FROM {src}")
        if hi > watermark[table]:
            q(conn, f"INSERT INTO {table} SELECT {cols} FROM {src} "
                    f"WHERE {col} > {watermark[table]} AND {col} <= {hi}")
            line.append(f"bronze.{table}: +{hi - watermark[table]} rows, {last_commit(conn, table)}")
            watermark[table] = hi

    # silver and gold: only once you have created them
    if not table_exists(conn, "silver", "orders_enriched"):
        watermark["silver"] = None
        return "\n    ".join(line) or "nothing new"
    if watermark["silver"] is None:  # just created: backfill from the start
        watermark["silver"] = q1(conn, "SELECT coalesce(max(order_id), 0) FROM lakehouse.silver.orders_enriched")
    lo, hi = watermark["silver"], watermark["orders"]
    if hi > lo:
        q(conn, SILVER_INSERT.format(lo=lo, hi=hi))
        line.append(f"silver: +{hi - lo} rows, {last_commit(conn, 'silver.orders_enriched')}")
        if table_exists(conn, "gold", "daily_revenue"):
            first = not watermark.get("gold_ready")  # gold just created: rebuild every day once
            q(conn, GOLD_MERGE.format(lo=0 if first else lo, hi=hi))
            watermark["gold_ready"] = True
            line.append(f"gold (MERGE): {last_commit(conn, 'gold.daily_revenue')}")
        else:
            watermark["gold_ready"] = False
        watermark["silver"] = hi
    return "\n    ".join(line) or "nothing new"


def check_bucket():
    """Fail early with a clear message if the bucket or keys are wrong."""
    import boto3
    bucket = os.environ["S3_BUCKET"]
    try:
        boto3.client("s3", region_name=os.environ["AWS_REGION"]).list_objects_v2(Bucket=bucket, MaxKeys=1)
        print(f"S3 OK: s3://{bucket}/rotten-lakehouse/")
    except Exception as e:
        sys.exit(f"Cannot use s3://{bucket}: {e}\nCheck lab/.env (keys, region, bucket name) and the IAM policy.")


def main():
    check_bucket()
    conn = trino_conn()
    for stmt in DDL:
        q(conn, stmt)

    # wait for the shop to create its tables
    while True:
        try:
            q(conn, "SELECT 1 FROM shop.public.payments LIMIT 1")
            break
        except Exception:
            print("waiting for the shop to open…")
            time.sleep(3)

    watermark = {t: q1(conn, f"SELECT coalesce(max({col}), 0) FROM {t}") for t, (_, col, _) in SOURCES.items()}
    watermark["silver"] = None  # read when silver exists

    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print("one load:\n    " + load_once(conn, watermark))
        return

    if EVERY <= 0:
        print("loader paused (LOAD_EVERY_SECONDS=0). Load by hand with: python loader.py once")
        while True:
            time.sleep(60)

    print(f"loader running every {EVERY}s, starting after {watermark}")
    run = 0
    while True:
        run += 1
        print(f"run {run}:\n    {load_once(conn, watermark)}")
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
