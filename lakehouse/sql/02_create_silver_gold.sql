-- 02 · CREATE SILVER AND GOLD
-- Run in DBeaver, or:  docker compose exec trino trino -f /sql/02_create_silver_gold.sql
--
-- bronze = raw copy of the shop
-- silver = clean, joined data (one row per order, with customer, product and payment)
-- gold   = ready-made numbers for the dashboard (revenue per day and country)
--
-- After you create them, the loader fills them on its next run, and keeps them fresh.


-- SILVER
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
WITH (partitioning = ARRAY['day(created_at)', 'country']);
-- Partitioned by day AND country, because analysts filter by both.


-- GOLD
CREATE SCHEMA IF NOT EXISTS lakehouse.gold;

CREATE TABLE IF NOT EXISTS lakehouse.gold.daily_revenue (
    order_day   DATE,
    country     VARCHAR,
    orders      BIGINT,
    revenue     DECIMAL(18,2)
);
-- Updated with a MERGE every load, so the dashboard is always fresh.


-- Wait 10 seconds, then:
-- SELECT * FROM lakehouse.gold.daily_revenue ORDER BY order_day DESC, revenue DESC;
