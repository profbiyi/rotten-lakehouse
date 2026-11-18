-- PART 1 · Step 5: look inside the table with Iceberg's metadata tables.
-- Every Iceberg table has hidden tables that describe it: "<table>$snapshots", "$files", "$manifests", "$partitions".
-- Run one at a time:  docker compose exec trino trino --catalog lakehouse --schema bronze

-- 1. Every load is a commit. Every commit is a snapshot (a saved version of the table).
SELECT committed_at,
       operation,
       summary['added-records']    AS rows_added,
       summary['added-data-files'] AS files_added,
       summary['total-data-files'] AS files_in_table
FROM "orders$snapshots"
ORDER BY committed_at DESC
LIMIT 10;

-- 2. The actual Parquet files on S3. Look at the sizes: kilobytes, not megabytes.
SELECT file_path,
       record_count,
       round(file_size_in_bytes / 1024.0, 1) AS size_kb
FROM "orders$files"
ORDER BY file_size_in_bytes
LIMIT 10;

-- 3. Size distribution: how many files are "small"?
SELECT CASE
         WHEN file_size_in_bytes < 1024 * 1024        THEN '1. under 1 MB'
         WHEN file_size_in_bytes < 32 * 1024 * 1024   THEN '2. 1-32 MB'
         WHEN file_size_in_bytes < 128 * 1024 * 1024  THEN '3. 32-128 MB'
         ELSE '4. 128 MB+ (healthy)'
       END AS size_bucket,
       count(*) AS files
FROM "orders$files"
GROUP BY 1
ORDER BY 1;

-- 4. Partitioning by day: files per day
SELECT partition, record_count, file_count, round(total_size / 1024.0, 1) AS total_kb
FROM "orders$partitions"
ORDER BY 1;

-- 5. Manifests: the lists of files a query must read before it reads any data
SELECT path, added_data_files_count, existing_data_files_count
FROM "orders$manifests";
