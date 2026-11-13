# The lab: a real company lakehouse that rots in front of you

The same story as the [simulator](https://profbiyi.github.io/rotten-lakehouse/), with real tools.

```
 shop app ──writes every second──▶ Postgres (shop db)
                                        │
 loader ──every 10s: INSERT INTO lakehouse SELECT new rows FROM shop (Trino)
                                        ▼
            Iceberg tables  ◀── catalog: Nessie
            on S3 (Silo)    ◀── queries: Trino
```

- **shop**: a fake online shop. Takes ~8 orders a second, plus payments, into its own Postgres. Knows nothing about the lakehouse.
- **loader**: the data team's "near real-time" pipeline. Every 10 seconds it copies the new rows into `lakehouse.bronze.orders` and `lakehouse.bronze.payments` (Iceberg, partitioned by day). Every run is a small commit, which is how the rot starts.
- **Nessie** is the catalog, **Trino** is the engine, **Silo** (an S3-compatible store) holds the files.

## What you need

- Docker Desktop with **6 GB+ RAM**
- Free ports: **8080** (Trino), **19120** (Nessie), **9000/9001** (Silo), **5433** (Postgres)

## Run it

```bash
cd lab
docker compose up -d
docker compose logs -f shop loader      # wait for "loader running…", then Ctrl+C
```

| What | Where |
|---|---|
| Trino UI (query times) | http://localhost:8080 (any username) |
| Nessie UI (commits pile up) | http://localhost:19120 |
| Silo console (files pile up) | http://localhost:9001 (admin / password) |

## The demo, step by step

**1. Watch it rot (leave this running in its own terminal)**
```bash
docker compose exec loader python watch.py            # or: watch.py payments
```
Snapshots, data files, manifests and files on S3 climb every 10 seconds. The dashboard query gets slower.

**2. Look inside with SQL**
```bash
docker compose exec trino trino --catalog lakehouse --schema bronze -f /sql/01_inspect.sql
```

**3. Time the company dashboards**
```bash
docker compose exec loader python bench.py
```

**4. Fix it, one chore at a time** (watch the numbers in the watch terminal)
```bash
docker compose exec loader python maintain.py optimize    # compaction: files ↓, but data files on S3 ↑ (the trap)
docker compose exec loader python maintain.py manifests   # manifests to plan ↓
docker compose exec loader python maintain.py expire      # snapshots ↓, unused files on S3 deleted
docker compose exec loader python maintain.py orphans     # leftovers from failed writes
docker compose exec loader python bench.py                # compare with step 3
```
Or all four in order: `maintain.py all`. Each step prints before → after.

**5. Watch it rot again.** The loader never stopped. Maintenance is a job you schedule, not a one-off.

**Bonus: "deleted isn't deleted".** Follow `sql/03_deleted_isnt_deleted.sql` in the Trino CLI:
```bash
docker compose exec trino trino --catalog lakehouse --schema bronze
```

## Make it rot faster or slower

In `docker-compose.yml`: `LOAD_EVERY_SECONDS` on the loader (try `3`) and `ORDERS_PER_SECOND` on the shop. Then `docker compose up -d`.

## Notes

- `lakehouse.properties` sets `iceberg.expire-snapshots.min-retention=0s` and `iceberg.remove-orphan-files.min-retention=0s` so cleanup works immediately. **Lab only.** The production default is 7 days.
- **Nessie and cleanup:** Nessie keeps history across branches. Expiring snapshots on `main` is fine here because there's only `main`. With other branches or tags, files may still be needed elsewhere. Nessie ships its own reference-aware GC tool for that, and Iceberg's own Nessie catalog disables `expire_snapshots` by default for the same reason.
- Start fresh: `docker compose down -v`.
- Uses `fs.s3.enabled` (current Trino). Older Trino releases call it `fs.native-s3.enabled`.
