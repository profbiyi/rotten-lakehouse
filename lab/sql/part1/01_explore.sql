-- PART 1 · Step 2: what is in this lakehouse?
-- Run one statement at a time in the Trino CLI:
--   docker compose exec trino trino

-- Trino can talk to many systems. Each one is a "catalog".
SHOW CATALOGS;
--   lakehouse  -> Iceberg tables on S3, tracked by Nessie
--   shop       -> the company's Postgres database (the source)

-- The company's app database: what tables does it have?
SHOW TABLES FROM shop.public;

-- The app is taking orders right now. Run this a few times and watch it grow.
SELECT count(*) AS orders_in_app FROM shop.public.orders;

-- The latest orders, as the app sees them
SELECT order_id, customer_id, amount, status, created_at
FROM shop.public.orders
ORDER BY order_id DESC
LIMIT 5;

-- The lakehouse side: the loader already created empty bronze tables. No data yet.
SHOW SCHEMAS FROM lakehouse;
SHOW TABLES FROM lakehouse.bronze;
SELECT count(*) FROM lakehouse.bronze.orders;   -- 0
