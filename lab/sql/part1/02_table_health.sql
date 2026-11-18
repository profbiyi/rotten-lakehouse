-- PART 1 · The health check. Run this after every load and watch the numbers.
--   docker compose exec trino trino --catalog lakehouse --schema bronze -f /sql/part1/02_table_health.sql

SELECT
  (SELECT count(*) FROM orders)                                       AS rows_in_table,
  (SELECT count(*) FROM "orders$snapshots")                           AS snapshots,
  (SELECT count(*) FROM "orders$files")                               AS data_files,
  (SELECT round(avg(file_size_in_bytes) / 1024.0, 1) FROM "orders$files") AS avg_file_kb,
  (SELECT count(*) FROM "orders$manifests")                           AS manifests;

-- What a healthy table looks like: few files of 128-512 MB each.
-- What you will see: more files every load, each a few KB.
