-- "Deleted isn't deleted": a GDPR-style delete is not done until old snapshots are expired.
-- Run these one at a time in the Trino CLI:
--   docker compose exec trino trino --catalog lakehouse --schema bronze

-- 1. Pick a customer and note the current snapshot id
SELECT count(*) FROM orders WHERE customer_id = 42;
SELECT snapshot_id FROM "orders$snapshots" ORDER BY committed_at DESC LIMIT 1;

-- 2. "Forget" the customer
DELETE FROM orders WHERE customer_id = 42;
SELECT count(*) FROM orders WHERE customer_id = 42;   -- 0. Looks deleted…

-- 3. …but time travel still finds them (paste the snapshot id from step 1)
SELECT count(*) FROM orders FOR VERSION AS OF <snapshot_id> WHERE customer_id = 42;

-- 4. Now expire old snapshots, and try step 3 again: the old version (and its files) are gone.
ALTER TABLE orders EXECUTE expire_snapshots(retention_threshold => '0s');
