-- 04 · REMOVE ORPHAN FILES: delete files that no version points to at all
--
-- If a write crashes halfway (network blip, Trino restarted), it can leave files
-- in the table's folder that were never added to any version. Nobody will ever
-- read them, but you still pay for them.
-- Think of it as: throwing away boxes on the shelf that have no label.

ALTER TABLE lakehouse.bronze.orders           EXECUTE remove_orphan_files(retention_threshold => '0s');
ALTER TABLE lakehouse.bronze.payments         EXECUTE remove_orphan_files(retention_threshold => '0s');
ALTER TABLE lakehouse.silver.orders_enriched  EXECUTE remove_orphan_files(retention_threshold => '0s');
ALTER TABLE lakehouse.gold.daily_revenue      EXECUTE remove_orphan_files(retention_threshold => '0s');

-- In this demo there may be none: that's fine, it just means nothing crashed.
--
-- DEMO ONLY: '0s' could delete files a running write is still adding.
-- In a real company keep the default (7 days).
