# Rotten Lakehouses: The Small File Problem

A DEC Series session for the Data Engineering Community: small files, piling history, metadata bloat, and how to clean up the mess.

## 1. The simulator

**Live: https://profbiyi.github.io/rotten-lakehouse/**

A clickable demo of what small, frequent writes do to a lakehouse table:

- **Stream micro-batches** and watch tiny files, snapshots and manifests pile up
- **Run an analytical query** and see planning, file opens and storage requests grow
- **Compact files**, then notice that storage went *up*, not down
- **Expire + clean up** to actually get the space back
- Switch to **DuckLake** to see data inlining avoid most small files, and `CHECKPOINT` clean up in one step

Query times come from a simple illustrative cost model, not a benchmark. The lab below gives real numbers.

The simulator is a single self-contained file: [`docs/index.html`](docs/index.html).

## 2. The hands-on lab

Same small-write workload into:

- **Iceberg**: Spark + Lakekeeper (REST catalog) + Silo (S3)
- **DuckLake**: DuckDB 2.0 + Postgres catalog + Silo (S3)

```bash
cd lab
docker compose up -d
alias lab='docker compose exec -w /home/jovyan/lab lab python'

lab iceberg_rot.py rot       # 200 tiny appends
lab iceberg_rot.py inspect   # count the damage
lab iceberg_rot.py bench     # time a query
lab iceberg_rot.py fix       # compact, expire, rewrite manifests, remove orphans
lab iceberg_rot.py bench     # compare

# same commands for ducklake_rot.py
```

Full steps, URLs and what to expect: [`lab/README.md`](lab/README.md).

## What to take home

1. Small, frequent writes are normal. Rot is the price you pay.
2. Compaction makes it fast. Expiry and cleanup make it small.
3. Maintenance is a scheduled job, whichever table format you pick.
