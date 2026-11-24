"""
THE LOADER: the data team's pipeline.

Every few seconds it copies the new rows from the shop's database into the lakehouse:

  bronze   raw copy of orders and payments         (INSERT)
  silver   orders joined with payments, customers  (INSERT)   - only once you create it
  gold     revenue per day and country             (MERGE)    - only once you create it

Each statement is one commit. Each commit writes new files to S3.
"""
import os
import time

import trino

LOAD_EVERY_SECONDS = int(os.environ.get("LOAD_EVERY_SECONDS", "10"))


def run(sql):
    cursor = trino_db.cursor()
    cursor.execute(sql)
    return cursor.fetchall()


def table_exists(schema, table):
    return run(f"SELECT count(*) FROM lakehouse.information_schema.tables "
               f"WHERE table_schema = '{schema}' AND table_name = '{table}'")[0][0] > 0


# 1. Connect to Trino (wait if it is still starting)
while True:
    try:
        trino_db = trino.dbapi.connect(host="trino", port=8080, user="loader", catalog="lakehouse")
        run("SELECT 1")
        break
    except Exception:
        print("waiting for trino...")
        time.sleep(3)

# 2. Create the bronze tables (same columns as the shop)
run("CREATE SCHEMA IF NOT EXISTS lakehouse.bronze")
run("""CREATE TABLE IF NOT EXISTS lakehouse.bronze.orders (
         order_id BIGINT, customer_id BIGINT, product_id BIGINT, quantity INTEGER,
         amount DECIMAL(12,2), status VARCHAR, created_at TIMESTAMP(6))
       WITH (partitioning = ARRAY['day(created_at)'])""")
run("""CREATE TABLE IF NOT EXISTS lakehouse.bronze.payments (
         payment_id BIGINT, order_id BIGINT, method VARCHAR, amount DECIMAL(12,2),
         status VARCHAR, created_at TIMESTAMP(6))
       WITH (partitioning = ARRAY['day(created_at)'])""")

# 3. Wait until the shop has created its tables
while True:
    try:
        run("SELECT 1 FROM shop.public.payments LIMIT 1")
        break
    except Exception:
        print("waiting for the shop...")
        time.sleep(3)

# 4. Load forever
print(f"Loader started: one load every {LOAD_EVERY_SECONDS} seconds")
load = 0
while True:
    load += 1
    done = []

    # BRONZE: copy rows we don't have yet
    for table, id_column in [("orders", "order_id"), ("payments", "payment_id")]:
        last_loaded = run(f"SELECT coalesce(max({id_column}), 0) FROM lakehouse.bronze.{table}")[0][0]
        rows = run(f"""INSERT INTO lakehouse.bronze.{table}
                       SELECT * FROM shop.public.{table}
                       WHERE {id_column} > {last_loaded}""")[0][0]
        done.append(f"bronze.{table} +{rows}")

    # SILVER: new orders, joined with their payment, customer and product
    if table_exists("silver", "orders_enriched"):
        rows = run("""INSERT INTO lakehouse.silver.orders_enriched
                      SELECT o.order_id, o.created_at, CAST(o.created_at AS DATE),
                             c.customer_id, c.name, c.country,
                             pr.product_id, pr.name, pr.category,
                             o.quantity, o.amount, o.status, p.method, p.status
                      FROM lakehouse.bronze.orders o
                      LEFT JOIN lakehouse.bronze.payments p ON p.order_id = o.order_id
                      JOIN shop.public.customers c  ON c.customer_id = o.customer_id
                      JOIN shop.public.products  pr ON pr.product_id = o.product_id
                      WHERE o.order_id > (SELECT coalesce(max(order_id), 0)
                                          FROM lakehouse.silver.orders_enriched)""")[0][0]
        done.append(f"silver +{rows}")

    # GOLD: recalculate today's revenue per country, and update the table (MERGE)
    if table_exists("gold", "daily_revenue"):
        run("""MERGE INTO lakehouse.gold.daily_revenue t
               USING (SELECT order_day, country,
                             count(*)                           AS orders,
                             CAST(sum(amount) AS DECIMAL(18,2)) AS revenue
                      FROM lakehouse.silver.orders_enriched
                      GROUP BY order_day, country) s
               ON t.order_day = s.order_day AND t.country = s.country
               WHEN MATCHED AND t.orders <> s.orders
                    THEN UPDATE SET orders = s.orders, revenue = s.revenue
               WHEN NOT MATCHED
                    THEN INSERT VALUES (s.order_day, s.country, s.orders, s.revenue)""")
        done.append("gold updated")

    print(f"load {load}: " + ", ".join(done))
    time.sleep(LOAD_EVERY_SECONDS)
