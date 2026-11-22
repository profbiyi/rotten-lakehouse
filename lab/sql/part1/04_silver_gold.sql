-- PART 1 · Step 6: silver and gold, built the way many teams build them on day 1.
-- The loader creates these tables and refreshes them after every bronze load.
-- This file shows exactly what it runs, so nothing is hidden.

------------------------------------------------------------------
-- SILVER: one clean, joined row per order
------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS lakehouse.silver;

CREATE TABLE IF NOT EXISTS lakehouse.silver.orders_enriched (
    order_id        BIGINT,
    created_at      TIMESTAMP(6),
    order_day       DATE,
    customer_id     BIGINT,
    customer_name   VARCHAR,
    country         VARCHAR,
    product_id      BIGINT,
    product_name    VARCHAR,
    category        VARCHAR,
    quantity        INTEGER,
    amount          DECIMAL(12,2),
    order_status    VARCHAR,
    payment_method  VARCHAR,
    payment_status  VARCHAR
)
WITH (
    format = 'PARQUET',
    partitioning = ARRAY['day(created_at)', 'country']   -- analysts filter by day and country
);

-- Every load, append the new orders (between the last loaded id and the newest one):
-- INSERT INTO lakehouse.silver.orders_enriched
-- SELECT o.order_id, o.created_at, CAST(o.created_at AS DATE),
--        o.customer_id, c.name, c.country,
--        o.product_id, pr.name, pr.category,
--        o.quantity, o.amount, o.status, p.method, p.status
-- FROM lakehouse.bronze.orders o
-- LEFT JOIN lakehouse.bronze.payments p ON p.order_id = o.order_id
-- JOIN shop.public.customers c  ON c.customer_id = o.customer_id
-- JOIN shop.public.products  pr ON pr.product_id = o.product_id
-- WHERE o.order_id > <last loaded> AND o.order_id <= <newest>;

------------------------------------------------------------------
-- GOLD: revenue per day and country, kept up to date for the dashboard
------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS lakehouse.gold;

CREATE TABLE IF NOT EXISTS lakehouse.gold.daily_revenue (
    order_day    DATE,
    country      VARCHAR,
    orders       BIGINT,
    revenue      DECIMAL(18,2),
    paid_orders  BIGINT,
    updated_at   TIMESTAMP(6)
)
WITH (format = 'PARQUET');

-- Every load, upsert the totals for the days that just changed:
-- MERGE INTO lakehouse.gold.daily_revenue t
-- USING (
--     SELECT order_day, country,
--            count(*)                          AS orders,
--            CAST(sum(amount) AS DECIMAL(18,2)) AS revenue,
--            count_if(order_status = 'paid')   AS paid_orders
--     FROM lakehouse.silver.orders_enriched
--     WHERE order_day >= <earliest day in this load>
--     GROUP BY 1, 2
-- ) s
-- ON t.order_day = s.order_day AND t.country = s.country
-- WHEN MATCHED THEN UPDATE SET orders = s.orders, revenue = s.revenue,
--                              paid_orders = s.paid_orders, updated_at = localtimestamp(6)
-- WHEN NOT MATCHED THEN INSERT (order_day, country, orders, revenue, paid_orders, updated_at)
--      VALUES (s.order_day, s.country, s.orders, s.revenue, s.paid_orders, localtimestamp(6));

------------------------------------------------------------------
-- Look at all three layers
------------------------------------------------------------------
SELECT * FROM lakehouse.gold.daily_revenue ORDER BY order_day DESC, revenue DESC;

SELECT 'bronze.orders' AS layer, count_if(content = 0) AS data_files, count_if(content <> 0) AS delete_files,
       round(avg(CASE WHEN content = 0 THEN file_size_in_bytes END) / 1024.0, 1) AS avg_kb
FROM lakehouse.bronze."orders$files"
UNION ALL
SELECT 'silver.orders_enriched', count_if(content = 0), count_if(content <> 0),
       round(avg(CASE WHEN content = 0 THEN file_size_in_bytes END) / 1024.0, 1)
FROM lakehouse.silver."orders_enriched$files"
UNION ALL
SELECT 'gold.daily_revenue', count_if(content = 0), count_if(content <> 0),
       round(avg(CASE WHEN content = 0 THEN file_size_in_bytes END) / 1024.0, 1)
FROM lakehouse.gold."daily_revenue$files";
