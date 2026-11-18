# The lab: a real company lakehouse that rots in front of you

**Teaching it? Follow the step-by-step guide:** [Part 1: build it and watch it rot](guide/part-1-build-and-watch-it-rot.md). More parts coming.

The same story as the [simulator](https://profbiyi.github.io/rotten-lakehouse/), with real tools.

```
 shop app ──writes every second──▶ Postgres (shop db)
                                        │
 loader ──every 10s: INSERT INTO lakehouse SELECT new rows FROM shop (Trino)
                                        ▼
            Iceberg tables  ◀── catalog: Nessie
            on Amazon S3    ◀── queries: Trino
```

- **shop**: a fake online shop. Takes ~8 orders a second, plus payments, into its own Postgres. Knows nothing about the lakehouse.
- **loader**: the data team's "near real-time" pipeline. Every 10 seconds it copies the new rows into `lakehouse.bronze.orders` and `lakehouse.bronze.payments` (Iceberg, partitioned by day). Every run is a small commit, which is how the rot starts.
- **Nessie** is the catalog, **Trino** is the engine, **Amazon S3** holds the files.

## What you need

- Docker Desktop with **6 GB+ RAM**
- Free ports: **8080** (Trino), **19120** (Nessie), **5433** (Postgres)
- An **S3 bucket** and an **IAM user** that can use it

### Set up AWS (once)

1. Create a bucket, e.g. `yourname-rotten-lakehouse`, in your region.
2. Create an IAM user with only this policy (replace the bucket name), then create an access key for it:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::yourname-rotten-lakehouse" },
    { "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::yourname-rotten-lakehouse/*" }
  ]
}
```
3. Put the keys in `lab/.env` (git-ignored, never commit it):
```bash
cd lab
cp .env.example .env     # then fill in the four values
```

Everything goes under `s3://<your-bucket>/rotten-lakehouse/`. An hour of the demo is a few MB and a few thousand requests: pennies. Delete that folder when you're done.

## Run it

```bash
docker compose up -d
docker compose logs -f shop loader      # wait for "loader running…", then Ctrl+C
```

| What | Where |
|---|---|
| Trino UI (query times) | http://localhost:8080 (any username) |
| Nessie UI (commits pile up) | http://localhost:19120 |
| S3 console (files pile up) | AWS console → S3 → your bucket → `rotten-lakehouse/` |

## Three ways to feed it

**1. Autopilot (default):** start it and walk away. The shop sells ~8 orders a second, and the loader commits every 10 seconds.
```bash
docker compose up -d
```

**2. You drive:** start everything paused, then send data and load it yourself, so the room sees each commit land.
```bash
ORDERS_PER_SECOND=0 LOAD_EVERY_SECONDS=0 docker compose up -d
docker compose exec shop   python shop.py burst 500   # the app takes 500 orders
docker compose exec loader python loader.py once      # the pipeline loads them: 1 commit per table
```
Run the `loader.py once` line 10 times in a row and you have just made 10 small commits.

**3. Turbo:** make it rot fast for a short session.
```bash
LOAD_EVERY_SECONDS=2 docker compose up -d
```

Switch between modes any time by re-running `docker compose up -d` with different values.

## The demo, step by step

**1. Watch it rot (leave this running in its own terminal)**
```bash
docker compose exec loader python watch.py            # or: watch.py payments
```
Snapshots, data files, manifests and files on S3 climb every 10 seconds. The dashboard query gets slower.

**2. Look inside with SQL**
```bash
docker compose exec trino trino --catalog lakehouse --schema bronze -f /sql/part1/03_inside_the_table.sql
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

Set `LOAD_EVERY_SECONDS` and `ORDERS_PER_SECOND` when you start it (see "Three ways to feed it" above).

## Notes

- `lakehouse.properties` sets `iceberg.expire-snapshots.min-retention=0s` and `iceberg.remove-orphan-files.min-retention=0s` so cleanup works immediately. **Lab only.** The production default is 7 days.
- **Nessie and cleanup:** Nessie keeps history across branches. Expiring snapshots on `main` is fine here because there's only `main`. With other branches or tags, files may still be needed elsewhere. Nessie ships its own reference-aware GC tool for that, and Iceberg's own Nessie catalog disables `expire_snapshots` by default for the same reason.
- Start fresh: `docker compose down -v`, then delete `s3://<your-bucket>/rotten-lakehouse/` (`aws s3 rm --recursive s3://<your-bucket>/rotten-lakehouse/`).
- Uses `fs.s3.enabled` (current Trino). Older Trino releases call it `fs.native-s3.enabled`.
