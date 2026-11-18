# Part 1: Build the lakehouse, run the jobs, watch the files pile up

**Goal:** by the end of this part everyone has a working lakehouse, has loaded data into it by hand, and can *prove* with SQL that it is filling up with small files.

Nothing here is magic. Every step is a command you can read, and after every step there is something to look at.

---

## The picture

```
 ┌────────────┐   writes orders     ┌──────────────┐
 │  shop app  │ ──────────────────▶ │  Postgres    │   the company's app database (source)
 └────────────┘   every second      └──────┬───────┘
                                           │  loader: "copy the new rows"  (a Trino INSERT)
                                           ▼
 ┌────────────┐   "where is the     ┌──────────────┐        ┌──────────────┐
 │   Trino    │ ◀─ latest version?" │    Nessie    │        │  Amazon S3   │
 │ (compute)  │ ──────────────────▶ │  (catalog)   │        │  (storage)   │
 └────────────┘    reads / writes Parquet + Iceberg metadata ───────────▶ │
```

| Layer | Tool | Job in one line |
|---|---|---|
| Compute | **Trino** | Runs our SQL: reads the source, writes the lakehouse, answers queries |
| Catalog | **Nessie** | Remembers where the *latest* version of each table is |
| Table format | **Iceberg** | The index card: which files make up the table right now |
| File format | **Parquet** | The data files themselves |
| Storage | **Amazon S3** | Where every file lives |

---

## Step 1: Start the lakehouse (paused)

We start everything **paused**, so nothing happens until we say so.

```bash
cd lab
cp .env.example .env                 # first time only: fill in AWS keys, region, bucket
ORDERS_PER_SECOND=0 LOAD_EVERY_SECONDS=0 docker compose up -d
docker compose ps
```

You should see `postgres`, `nessie`, `trino`, `shop` and `loader` running. Trino takes about a minute to become healthy.

**Check each layer is alive:**
- Nessie UI: http://localhost:19120 → one branch, `main`, no tables yet
- Trino UI: http://localhost:8080 (any username) → no queries yet
- S3 console → your bucket → nothing under `rotten-lakehouse/` yet

---

## Step 2: Meet the company

Open the Trino CLI and run the statements in [`sql/part1/01_explore.sql`](../sql/part1/01_explore.sql) one at a time:

```bash
docker compose exec trino trino
```

Trino sees two catalogs: `shop` (the company's Postgres) and `lakehouse` (Iceberg on S3). The app is paused, so the order count is 0.

Now let the company take some orders, then count again:

```bash
docker compose exec shop python shop.py burst 500
```
```sql
SELECT count(*) FROM shop.public.orders;   -- 500
```

---

## Step 3: Run the pipeline once, by hand

```bash
docker compose exec loader python loader.py once
```

You'll see something like:
```
one load: orders: +500 rows, +1 file(s) → 1 files, avg 14 KB | payments: +470 rows, +1 file(s) → 1 files, avg 11 KB
```

**What just happened:** the loader ran one SQL statement per table:
```sql
INSERT INTO lakehouse.bronze.orders
SELECT ... FROM shop.public.orders
WHERE order_id > <last loaded id> AND order_id <= <newest id>;
```
That INSERT is **one commit**. It wrote a Parquet file to S3, wrote Iceberg metadata next to it, and Nessie moved `main` to point at the new version.

**Go and look:**
- S3 console → `rotten-lakehouse/bronze/orders-…/data/` → one Parquet file. `metadata/` → a `metadata.json`, a manifest list and a manifest.
- Nessie UI → `main` now has commits.
- Health check:
```bash
docker compose exec trino trino --catalog lakehouse --schema bronze -f /sql/part1/02_table_health.sql
```

---

## Step 4: Do what real pipelines do, many small loads

Real "near real-time" pipelines run every few seconds or minutes. Do it 10 times:

```bash
for i in $(seq 1 10); do
  docker compose exec shop python shop.py burst 50
  docker compose exec loader python loader.py once
done
```

Run the health check again. Same table, more data, but now:
- **snapshots** went from 1 to 11
- **data files** went from 1 to 11 (or more: one per day partition touched)
- **average file size** dropped
- **manifests** went from 1 to 11

**This is the small file problem being born.** Nobody did anything wrong. Each load was correct. The table just recorded every one of them.

---

## Step 5: Look inside the table

Iceberg tables have hidden metadata tables. Run [`sql/part1/03_inside_the_table.sql`](../sql/part1/03_inside_the_table.sql) one query at a time:

| Query | What to point at |
|---|---|
| `"orders$snapshots"` | one row per load, each adding 1 file and a few dozen rows |
| `"orders$files"` | the real Parquet files on S3, in **KB** |
| size buckets | almost everything is under 1 MB; healthy is 128 MB+ |
| `"orders$partitions"` | files per day |
| `"orders$manifests"` | one manifest per commit: the list a query reads *before* any data |

---

## Step 6: Autopilot, and watch it rot live

Switch the company and the pipeline on:

```bash
docker compose up -d      # default: ~8 orders/second, a load every 10 seconds
```

In a second terminal, the live meter:
```bash
docker compose exec loader python watch.py
```

And in a third, follow the pipeline log:
```bash
docker compose logs -f loader
```
```
run 12: orders: +81 rows, +1 file(s) → 23 files, avg 9 KB | payments: ...
run 13: orders: +77 rows, +1 file(s) → 24 files, avg 9 KB | ...
```

Leave it for 10 minutes: that's 60 commits, 60+ small files per table.

---

## Step 7: See what a query has to do

Run a dashboard query a few times as the files pile up:

```bash
docker compose exec loader python bench.py
```

Then open the **Trino UI** (http://localhost:8080), click the latest query, and look at:
- **Splits**: roughly one per file Trino had to open
- **Input**: rows and bytes read
- **Elapsed time**

Ten minutes later, run it again. More splits, more time, for a table that is still only a few MB.

---

## What we proved in Part 1

1. Every load is a commit; every commit leaves a snapshot, a manifest, a metadata file and at least one data file.
2. Frequent small loads mean many tiny files, not a few big ones.
3. Queries pay for it: more files to plan, open and read.

**Next, Part 2: get rid of the small files (compaction), and see why storage goes *up* before it goes down.**
