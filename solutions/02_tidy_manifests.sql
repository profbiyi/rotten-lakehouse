-- 02 · TIDY THE MANIFESTS: merge the small "lists of files" into a few
--
-- Before reading any data, a query reads the table's manifests:
-- lists of which files belong to the table. Every load added one more list.
-- Think of it as: rewriting 500 sticky notes into one neat page.

-- How many manifests now?
SELECT count(*) AS manifests FROM lakehouse.bronze."orders$manifests";

ALTER TABLE lakehouse.bronze.orders           EXECUTE optimize_manifests;
ALTER TABLE lakehouse.bronze.payments         EXECUTE optimize_manifests;
ALTER TABLE lakehouse.silver.orders_enriched  EXECUTE optimize_manifests;
ALTER TABLE lakehouse.gold.daily_revenue      EXECUTE optimize_manifests;

-- And now?
SELECT count(*) AS manifests FROM lakehouse.bronze."orders$manifests";
-- Queries now plan faster. No data files changed.
