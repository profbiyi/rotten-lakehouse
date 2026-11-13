# Rotten Lakehouses: The Small File Problem

A DEC Series session for the Data Engineering Community: small files, piling history, metadata bloat, and how to clean up the mess.

## 1. The simulator

**Live: https://profbiyi.github.io/rotten-lakehouse/**

A clickable demo of what small, frequent writes do to a lakehouse table:

- **Stream micro-batches** and watch tiny files, snapshots and manifests pile up
- **Run an analytical query** and see planning, file opens and storage requests grow
- **Compact files**, then notice that storage went *up*, not down
- **Expire + clean up** to actually get the space back
- Watch **compaction under the hood**: candidates, rewrite groups, bin-packing, commits, with sliders for `target-file-size-bytes`, `max-file-group-size-bytes`, `max-concurrent-file-group-rewrites` and partial progress
- Toggle **partition by day** to see small files multiply
- Turn on a **maintenance policy** (event or schedule trigger) and let it clean up while data streams in
- Switch to **DuckLake** to see data inlining avoid most small files, and `CHECKPOINT` clean up in one step

Query times come from a simple illustrative cost model, not a benchmark. The lab below gives real numbers.

The simulator is a single self-contained file: [`docs/index.html`](docs/index.html).

## 2. The hands-on lab: a company lakehouse that rots for real

Nessie + Iceberg + Trino + S3, fed by a fake online shop. A pipeline loads new orders and payments every 10 seconds, the way many "near real-time" pipelines do, and you watch the small files, snapshots and manifests pile up. Then you fix it with Trino's Iceberg procedures.

```bash
cd lab
docker compose up -d
docker compose exec loader python watch.py      # live rot meter
docker compose exec loader python bench.py      # time the company dashboards
docker compose exec loader python maintain.py all
```

Full walkthrough: [`lab/README.md`](lab/README.md).

### Bonus lab: Iceberg vs DuckLake

Spark + Lakekeeper vs DuckDB + DuckLake, same small-write load: [`bonus-iceberg-vs-ducklake/`](bonus-iceberg-vs-ducklake/).

## What to take home

1. Small, frequent writes are normal. Rot is the price you pay.
2. Compaction makes it fast. Expiry and cleanup make it small.
3. Maintenance is a scheduled job, whichever table format you pick.
