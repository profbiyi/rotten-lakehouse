"""
Rotten Lakehouse: DuckLake side (DuckDB 2.0 + Postgres catalog + Silo).

Two tables get the SAME small-write load:
  events_tiny     -> inlining OFF  (every insert = a new Parquet file, like Iceberg)
  events_inlined  -> inlining ON   (small inserts land in the Postgres catalog, zero files)

  python ducklake_rot.py rot --batches 200 --rows 50
  python ducklake_rot.py inspect
  python ducklake_rot.py bench
  python ducklake_rot.py fix
  python ducklake_rot.py reset
"""
import argparse
import time

import duckdb

DATA_PATH = "s3://ducklake/lake/"
CATALOG_DSN = "ducklake:postgres:dbname=ducklake host=db user=postgres password=postgres"
TABLES = {"events_tiny": 0, "events_inlined": 1000}  # table -> data_inlining_row_limit
META = "__ducklake_metadata_lake"  # DuckLake exposes its catalog tables under this schema


def connect():
    con = duckdb.connect()
    con.sql("INSTALL ducklake; INSTALL postgres; INSTALL httpfs;")
    con.sql("LOAD ducklake; LOAD postgres; LOAD httpfs;")
    # S3 creds both as a secret and as SET (CHECKPOINT reads the SET values)
    con.sql("""
        CREATE OR REPLACE SECRET silo (
            TYPE s3, KEY_ID 'silo-root-user', SECRET 'silo-root-password',
            ENDPOINT 'silo:9000', URL_STYLE 'path', USE_SSL false, REGION 'local-01')
    """)
    for k, v in {
        "s3_endpoint": "silo:9000", "s3_access_key_id": "silo-root-user",
        "s3_secret_access_key": "silo-root-password", "s3_url_style": "path",
        "s3_use_ssl": "false", "s3_region": "local-01",
    }.items():
        con.sql(f"SET {k} = '{v}'")
    con.sql(f"ATTACH '{CATALOG_DSN}' AS lake (DATA_PATH '{DATA_PATH}')")
    con.sql("USE lake")
    return con


def ensure_tables(con):
    for t, limit in TABLES.items():
        con.sql(f"""
            CREATE TABLE IF NOT EXISTS {t} (
                event_id BIGINT, user_id INTEGER, amount DOUBLE, event_ts TIMESTAMP
            ) WITH (data_inlining_row_limit = {limit})
        """)


def scalar(con, sql):
    return con.sql(sql).fetchone()[0]


def stats(con, table) -> dict:
    live = con.sql(f"""
        SELECT count(*), coalesce(sum(f.record_count), 0), round(avg(f.file_size_bytes) / 1024, 1)
        FROM {META}.ducklake_data_file f
        JOIN {META}.ducklake_table t USING (table_id)
        WHERE t.table_name = '{table}' AND t.end_snapshot IS NULL AND f.end_snapshot IS NULL
    """).fetchone()
    rows = scalar(con, f"SELECT count(*) FROM {table}")
    on_storage = scalar(con, f"SELECT count(*) FROM glob('{DATA_PATH}main/{table}/**/*.parquet')")
    return {
        "rows": rows,
        "live_parquet_files": live[0],
        "parquet_files_on_s3": on_storage,
        "avg_file_kb": live[2],
        "rows_inlined_in_catalog": rows - live[1],
    }


def print_stats(title, con):
    snaps = scalar(con, "SELECT count(*) FROM ducklake_snapshots('lake')")
    for t in TABLES:
        print(f"\n=== {title}: {t} ===")
        for k, v in stats(con, t).items():
            print(f"  {k:<26} {v}")
    print(f"\n  snapshots (whole lake)     {snaps}")


def cmd_rot(con, batches, rows):
    ensure_tables(con)
    start = scalar(con, "SELECT coalesce(max(event_id), 0) FROM events_tiny")
    t0 = time.time()
    for i in range(batches):
        lo = start + i * rows + 1
        for t in TABLES:
            # autocommit: each INSERT is its own snapshot
            con.sql(f"""
                INSERT INTO {t}
                SELECT range, (random() * 10000)::INT, round(random() * 500, 2), now()
                FROM range({lo}, {lo + rows})
            """)
        if (i + 1) % 25 == 0:
            print(f"  appended {i + 1}/{batches} batches ({time.time() - t0:.0f}s)")
    print_stats("DuckLake after small writes", con)


def cmd_bench(con, runs=5):
    for t in TABLES:
        q = f"SELECT user_id % 10 AS bucket, count(*), sum(amount) FROM {t} GROUP BY 1"
        con.sql(q).fetchall()
        times = []
        for _ in range(runs):
            s = time.time()
            con.sql(q).fetchall()
            times.append(time.time() - s)
        print(f"DuckLake {t:<15} median {sorted(times)[len(times) // 2] * 1000:.0f} ms over {runs} runs")


def cmd_fix(con):
    print_stats("DuckLake BEFORE maintenance", con)

    print("\n1. CHECKPOINT  (flush inlined -> expire -> merge -> rewrite -> cleanup -> orphans)")
    con.sql("CHECKPOINT")
    print_stats("DuckLake after CHECKPOINT", con)

    # Default retention keeps old snapshots/files for a while, so storage barely shrinks.
    # Lab only: force retention to "now" so you can watch S3 actually get cleaned.
    print("\n2. Lab only: expire all old snapshots + delete their files now")
    con.sql("CALL ducklake_expire_snapshots('lake', older_than => now())").show()
    con.sql("CALL ducklake_cleanup_old_files('lake', cleanup_all => true)").show()
    print_stats("DuckLake AFTER forced cleanup", con)


def cmd_reset(con):
    for t in TABLES:
        con.sql(f"DROP TABLE IF EXISTS {t}")
    con.sql("CALL ducklake_expire_snapshots('lake', older_than => now())")
    con.sql("CALL ducklake_cleanup_old_files('lake', cleanup_all => true)")
    print("dropped", ", ".join(TABLES))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["rot", "inspect", "bench", "fix", "reset"])
    p.add_argument("--batches", type=int, default=200)
    p.add_argument("--rows", type=int, default=50)
    a = p.parse_args()

    con = connect()
    if a.command == "rot":
        cmd_rot(con, a.batches, a.rows)
    elif a.command == "inspect":
        print_stats("DuckLake", con)
    elif a.command == "bench":
        cmd_bench(con)
    elif a.command == "fix":
        cmd_fix(con)
    elif a.command == "reset":
        cmd_reset(con)
