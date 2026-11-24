# Rotten Lakehouses: The Small File Problem

A DEC Series session for the Data Engineering Community.

A lakehouse that works perfectly on day 1 slowly fills up with thousands of tiny files. Queries get slower and storage keeps growing. In this session we watch it happen on a real lakehouse, then fix it step by step.

## How the session goes

| | What | Where |
|---|---|---|
| 1 | **Build a real lakehouse** that a pretend shop keeps sending data to | [`lakehouse/`](lakehouse/README.md) |
| 2 | **Watch the small files pile up** in S3 and in SQL | [`lakehouse/`](lakehouse/README.md), steps 5 and 6 |
| 3 | **Understand it** with the simulator | https://profbiyi.github.io/rotten-lakehouse/ |
| 4 | **Fix it**, one SQL file per step | [`solutions/`](solutions/README.md) |

## The stack

| Layer | Tool |
|---|---|
| Query engine | Trino |
| Catalog | Nessie |
| Table format | Apache Iceberg |
| File format | Parquet |
| Storage | Amazon S3 |

## Quick start

```bash
git clone https://github.com/profbiyi/rotten-lakehouse
cd rotten-lakehouse/lakehouse
cp .env.example .env        # add your AWS keys, region and bucket
docker compose up -d
```

Then follow [`lakehouse/README.md`](lakehouse/README.md).
