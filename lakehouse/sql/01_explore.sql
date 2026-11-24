-- 01 · EXPLORE: is the lakehouse working?
-- Run in DBeaver, or:  docker compose exec trino trino
-- Run one query at a time.


-- Trino talks to two systems. Each one is a "catalog".
SHOW CATALOGS;
--   shop       = the shop's own database (Postgres)
--   lakehouse  = our tables on S3 (Iceberg + Nessie)


-- The shop is busy. Run this a few times and watch the number grow.
SELECT count(*) AS orders_in_shop FROM shop.public.orders;


-- The loader copies them into the lakehouse every 10 seconds.
SELECT count(*) AS orders_in_lakehouse FROM lakehouse.bronze.orders;


-- Both side by side: the lakehouse is a few seconds behind the shop.
SELECT
  (SELECT count(*) FROM shop.public.orders)      AS in_shop,
  (SELECT count(*) FROM lakehouse.bronze.orders) AS in_lakehouse;


-- It is real data. Query it like any database.
SELECT * FROM lakehouse.bronze.orders ORDER BY order_id DESC LIMIT 10;

SELECT status, count(*) AS orders, sum(amount) AS revenue
FROM lakehouse.bronze.orders
GROUP BY status;
