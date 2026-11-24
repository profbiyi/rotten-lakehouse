-- 01 · COMPACT: merge the small files into big ones
--
-- Think of it as: emptying 500 small envelopes into one big folder.
-- Same data, far fewer files to open.
--
-- Rewrites every file smaller than 128 MB into bigger files.
-- The new files become a new version of the table.

ALTER TABLE lakehouse.bronze.orders           EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lakehouse.bronze.payments         EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lakehouse.silver.orders_enriched  EXECUTE optimize(file_size_threshold => '128MB');
ALTER TABLE lakehouse.gold.daily_revenue      EXECUTE optimize(file_size_threshold => '128MB');

-- Now run 00_health_check.sql:
--   files   → way down (one or a few per partition)
--   avg_kb  → way up
--   versions → one MORE (compaction is a new version)
--
-- Then look at S3: the old small files are STILL THERE.
-- The old versions of the table still point to them. That's step 03.
