-- 03 · EXPIRE OLD VERSIONS: forget old versions, and delete the files only they used
--
-- Iceberg keeps every old version of the table, so you can "time travel".
-- Those old versions still point to the old small files, so S3 keeps them.
-- Think of it as: shredding old drafts you will never read again.
--
-- '0s' = keep only the latest version. DEMO ONLY.
-- In a real company use something like '7d': you can still go back 7 days.

ALTER TABLE lakehouse.bronze.orders           EXECUTE expire_snapshots(retention_threshold => '0s');
ALTER TABLE lakehouse.bronze.payments         EXECUTE expire_snapshots(retention_threshold => '0s');
ALTER TABLE lakehouse.silver.orders_enriched  EXECUTE expire_snapshots(retention_threshold => '0s');
ALTER TABLE lakehouse.gold.daily_revenue      EXECUTE expire_snapshots(retention_threshold => '0s');

-- Now run 00_health_check.sql:
--   versions → 1
--
-- Then look at S3: the old small files are GONE. Storage finally goes down.
--
-- The trade-off: you can no longer time travel to the versions you just expired.
