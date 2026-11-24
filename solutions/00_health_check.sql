-- 00 · HEALTH CHECK
-- Run this before and after every fix, and compare.

SELECT 'bronze.orders' AS table_name,
       (SELECT count(*) FROM lakehouse.bronze."orders$snapshots")             AS versions,
       (SELECT count(*) FROM lakehouse.bronze."orders$files")                 AS files,
       (SELECT round(avg(file_size_in_bytes) / 1024.0) FROM lakehouse.bronze."orders$files") AS avg_kb
UNION ALL
SELECT 'bronze.payments',
       (SELECT count(*) FROM lakehouse.bronze."payments$snapshots"),
       (SELECT count(*) FROM lakehouse.bronze."payments$files"),
       (SELECT round(avg(file_size_in_bytes) / 1024.0) FROM lakehouse.bronze."payments$files")
UNION ALL
SELECT 'silver.orders_enriched',
       (SELECT count(*) FROM lakehouse.silver."orders_enriched$snapshots"),
       (SELECT count(*) FROM lakehouse.silver."orders_enriched$files"),
       (SELECT round(avg(file_size_in_bytes) / 1024.0) FROM lakehouse.silver."orders_enriched$files")
UNION ALL
SELECT 'gold.daily_revenue',
       (SELECT count(*) FROM lakehouse.gold."daily_revenue$snapshots"),
       (SELECT count(*) FROM lakehouse.gold."daily_revenue$files"),
       (SELECT round(avg(file_size_in_bytes) / 1024.0) FROM lakehouse.gold."daily_revenue$files");

-- versions = how many versions (snapshots) of the table are kept
-- files    = how many files a query has to open
-- avg_kb   = average file size (healthy: 128 MB = 131,072 KB or more)
