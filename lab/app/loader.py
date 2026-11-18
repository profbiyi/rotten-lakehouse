"""
The data team's pipeline: every few seconds, copy new rows from the shop's
Postgres into Iceberg bronze tables. One small INSERT per table per run =
one commit = new data files, a new manifest, a new snapshot, a new metadata.json.
This is how most "near real-time" pipelines rot a lakehouse.

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

SOURCES = {  # lakehouse table -> (source table, id column, columns)
    "orders": ("shop.public.orders", "order_id",
               "order_id, customer_id, product_id, quantity, amount, status, created_at"),
    "payments": ("shop.public.payments", "payment_id",
                 "payment_id, order_id, method, amount, status, created_at"),
}


def load_once(conn, watermark):
    line = []
    for table, (src, col, cols) in SOURCES.items():
        hi = q1(conn, f"SELECT coalesce(max({col}), 0) FROM {src}")
        if hi > watermark[table]:
            q(conn, f"INSERT INTO {table} SELECT {cols} FROM {src} "
                    f"WHERE {col} > {watermark[table]} AND {col} <= {hi}")
            line.append(f"{table} +{hi - watermark[table]} rows")
            watermark[table] = hi
    return ", ".join(line) or "nothing new"


def main():
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

    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print("one load:", load_once(conn, watermark), "(1 commit per table)")
        return

    if EVERY <= 0:
        print("loader paused (LOAD_EVERY_SECONDS=0). Load by hand with: python loader.py once")
        while True:
            time.sleep(60)

    print(f"loader running every {EVERY}s, starting after {watermark}")
    run = 0
    while True:
        run += 1
        print(f"run {run}: {load_once(conn, watermark)}")
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
