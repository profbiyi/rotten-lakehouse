# Rotten Lakehouse Lab

Watch a lakehouse rot under small writes, then fix it. Same workload into:

- **Iceberg**: Spark + Lakekeeper (REST catalog) + Silo (S3)
- **DuckLake**: DuckDB 2.0 + Postgres catalog + Silo (S3), two tables:
  - `events_tiny`: inlining off (behaves like Iceberg: one Parquet file per insert)
  - `events_inlined`: inlining on (small inserts sit in the Postgres catalog)

## Start

```bash
docker compose up -d
docker compose logs -f lab    # wait for the Jupyter URL, then Ctrl+C
```

First Spark run downloads the Iceberg jars (cached after that).

| What | URL |
|---|---|
| Silo console (watch files pile up) | http://localhost:9001 (silo-root-user / silo-root-password) |
| Lakekeeper UI | http://localhost:8181/ui |
| Jupyter | http://localhost:8888 |
| Spark UI (while a job runs) | http://localhost:4040 |

## Run the experiment

```bash
alias lab='docker compose exec -w /home/jovyan/lab lab python'

# 1. Rot: 200 appends of 50 rows each
lab iceberg_rot.py  rot --batches 200 --rows 50
lab ducklake_rot.py rot --batches 200 --rows 50

# 2. Look at the damage
lab iceberg_rot.py  inspect
lab ducklake_rot.py inspect
lab iceberg_rot.py  bench
lab ducklake_rot.py bench

# 3. Fix it
lab iceberg_rot.py  fix      # rewrite_data_files, expire_snapshots, rewrite_manifests, remove_orphan_files
lab ducklake_rot.py fix      # CHECKPOINT, then forced expiry + cleanup

# 4. Measure again
lab iceberg_rot.py  bench
lab ducklake_rot.py bench

# Start over
lab iceberg_rot.py  reset
lab ducklake_rot.py reset
```

## What to expect

| Metric | Iceberg | DuckLake (inlining off) | DuckLake (inlining on) |
|---|---|---|---|
| Data files after 200 appends | ~200 | ~200 | ~0 |
| Snapshots | ~200 | ~400 for the whole lake (both tables) | shared with the left |
| Manifests / metadata.json files | ~200 each | none (metadata is SQL rows) | none |
| Where the rot lives | S3 files + metadata files | S3 files | rows in the Postgres catalog |
| Fix | 4 Spark procedures | `CHECKPOINT` | `CHECKPOINT` (flush first) |

Things to point out in the session:

- `files` vs `files_held_by_history` (Iceberg) and `live_parquet_files` vs `parquet_files_on_s3` (DuckLake): compaction alone does **not** shrink storage. Old files stay until snapshots are expired and cleanup runs.
- After `CHECKPOINT`, DuckLake's default retention still keeps old files, so S3 barely shrinks until the forced expiry step. That's retention working as designed, not a bug.
- Make the rot worse: `--batches 1000 --rows 5`, or add a `PARTITIONED BY (days(event_ts))` to multiply files.

## Known rough edges (not tested end to end yet)

- `remove_orphan_files` needs to list the bucket. With Lakekeeper vending credentials, that can be refused; the script skips it and says so.
- DuckLake table options use `WITH (data_inlining_row_limit = N)`, which needs a recent ducklake extension (ships with DuckDB 2.0).
- Silo replaces MinIO, following Lakekeeper's own example. Swap to `minio/minio` if you prefer; the S3 settings are the same.
