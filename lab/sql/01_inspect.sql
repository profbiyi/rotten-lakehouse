-- Look inside the rot with Iceberg metadata tables.
-- Run:  docker compose exec trino trino --catalog lakehouse --schema bronze -f /sql/01_inspect.sql

-- How many commits have we kept?
SELECT count(*) AS snapshots FROM "orders$snapshots";

-- How many data files, and how small are they?
SELECT count(*)                                   AS data_files,
       round(avg(file_size_in_bytes) / 1024, 1)   AS avg_kb,
       round(min(file_size_in_bytes) / 1024, 1)   AS min_kb,
       round(max(file_size_in_bytes) / 1024, 1)   AS max_kb
FROM "orders$files";

-- Files per day partition (partitioning multiplies small files)
SELECT partition, record_count, file_count, total_size
FROM "orders$partitions"
ORDER BY 1;

-- How many manifests does a query have to read to plan?
SELECT count(*) AS manifests FROM "orders$manifests";

-- The last 10 commits: each one is a tiny append
SELECT committed_at, operation, summary['added-data-files'] AS files_added, summary['added-records'] AS rows_added
FROM "orders$snapshots"
ORDER BY committed_at DESC
LIMIT 10;
