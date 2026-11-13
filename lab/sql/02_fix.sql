-- The four cleanup chores, in order. Run them one at a time and re-run 01_inspect.sql in between.
-- Lab catalog allows 0s retention. In production the minimum is 7d by default.

-- 1. Compaction: rewrite small files into bigger ones (bin-pack). Storage goes UP after this.
ALTER TABLE orders EXECUTE optimize(file_size_threshold => '128MB');

-- 2. Merge the many small manifests so planning reads fewer files.
ALTER TABLE orders EXECUTE optimize_manifests;

-- 3. Expire old snapshots. This is what actually deletes the old small files from S3.
ALTER TABLE orders EXECUTE expire_snapshots(retention_threshold => '0s');

-- 4. Remove files no snapshot points to (e.g. leftovers from failed writes).
ALTER TABLE orders EXECUTE remove_orphan_files(retention_threshold => '0s');
