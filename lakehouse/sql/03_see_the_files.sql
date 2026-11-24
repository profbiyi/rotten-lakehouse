-- 03 · SEE THE FILES
-- Every Iceberg table has hidden tables that describe it:
--   "orders$snapshots"  = every version of the table (one per load)
--   "orders$files"      = every data file the table uses right now
-- Run one query at a time.


-- 1. How many times has the loader written to bronze.orders?
SELECT count(*) AS snapshots FROM lakehouse.bronze."orders$snapshots";


-- 2. How many files, and how big are they?
SELECT count(*)                                  AS files,
       round(avg(file_size_in_bytes) / 1024.0)   AS avg_size_kb
FROM lakehouse.bronze."orders$files";
-- A healthy file is 128 MB or more. Ours are a few KB.


-- 3. Look at a few of them. These are real Parquet files on S3.
SELECT file_path, record_count, round(file_size_in_bytes / 1024.0) AS size_kb
FROM lakehouse.bronze."orders$files"
LIMIT 10;


-- 4. The last 10 loads: each one added a file with a handful of rows
SELECT committed_at,
       summary['added-records']    AS rows_added,
       summary['added-data-files'] AS files_added
FROM lakehouse.bronze."orders$snapshots"
ORDER BY committed_at DESC
LIMIT 10;


-- 5. All the tables at once
SELECT 'bronze.orders' AS table_name, count(*) AS files, round(avg(file_size_in_bytes) / 1024.0) AS avg_kb
FROM lakehouse.bronze."orders$files"
UNION ALL
SELECT 'bronze.payments', count(*), round(avg(file_size_in_bytes) / 1024.0)
FROM lakehouse.bronze."payments$files"
UNION ALL
SELECT 'silver.orders_enriched', count(*), round(avg(file_size_in_bytes) / 1024.0)
FROM lakehouse.silver."orders_enriched$files"
UNION ALL
SELECT 'gold.daily_revenue', count(*), round(avg(file_size_in_bytes) / 1024.0)
FROM lakehouse.gold."daily_revenue$files";
-- Silver has the most files: every load is split by country.
-- Gold is tiny, but every MERGE leaves extra files behind.
