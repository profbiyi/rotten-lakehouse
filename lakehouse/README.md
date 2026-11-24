# Part 1: The lakehouse

A small, real lakehouse. A pretend shop keeps selling things, and a loader keeps copying the new data into the lakehouse, like a real company.

```
   SHOP                   LOADER                      LAKEHOUSE
 (Postgres)  ───────▶  every 10 seconds  ───────▶  bronze → silver → gold
 8 orders a second      copies new rows            (Iceberg tables on S3)
```

| Piece | What it is | In real life |
|---|---|---|
| **shop** | Pretend app taking orders and payments | Your company's app |
| **loader** | Copies new rows every 10 seconds | The data team's pipeline |
| **Trino** | Runs our SQL | The query engine |
| **Nessie** | Remembers where each table's latest version is | The catalog |
| **S3** | Stores the files | Storage |

---

## Step 1: Set up (once)

You need **Docker Desktop** and an **S3 bucket** with an access key that can read and write it.

```bash
cd lakehouse
cp .env.example .env        # then open .env and fill in your keys, region and bucket
```

## Step 2: Start it

```bash
docker compose up -d
docker compose logs -f loader
```

After about a minute you should see:
```
Loader started: one load every 10 seconds
load 1: bronze.orders +480, bronze.payments +450
load 2: bronze.orders +81, bronze.payments +77
```
`Ctrl+C` stops watching. The lakehouse keeps running.

## Step 3: Connect

| Tool | How |
|---|---|
| **DBeaver** | New connection → Trino → host `localhost`, port `8080`, user: any name, no password |
| **Trino CLI** | `docker compose exec trino trino` |
| **Trino UI** | http://localhost:8080 (see every query, its time and its files) |
| **S3** | AWS console → your bucket → `rotten-lakehouse/` |

## Step 4: See it working

Run [`sql/01_explore.sql`](sql/01_explore.sql), one query at a time. The shop and the lakehouse fill up together.

## Step 5: Add silver and gold

Run [`sql/02_create_silver_gold.sql`](sql/02_create_silver_gold.sql). The loader fills them on its next run, and from then on every 10 seconds:

- **silver.orders_enriched**: each order joined with its customer, product and payment
- **gold.daily_revenue**: revenue per day and country, updated with a MERGE

## Step 6: Look at the files

Let it run for 15 minutes, then:

1. **S3 console** → `rotten-lakehouse/bronze/orders-…/data/` → page after page of tiny files
2. Run [`sql/03_see_the_files.sql`](sql/03_see_the_files.sql) → hundreds of files, each a few KB

**The data is small. The number of files is huge. That's the small file problem.**

Next: [Part 2: fix it](../solutions/README.md).

---

### Handy commands

```bash
docker compose stop shop loader     # pause the data
docker compose start shop loader    # carry on
docker compose down                 # stop everything (files stay on S3)
docker compose down -v              # stop and wipe the databases (then delete rotten-lakehouse/ in S3 too)
```
