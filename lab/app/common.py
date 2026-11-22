"""Shared helpers: Trino connection, table stats, S3 listing."""
import os
import re
import time

import boto3
import trino

CATALOG = "lakehouse"
SCHEMA = "bronze"
TABLES = ["orders", "payments", "silver.orders_enriched", "gold.daily_revenue"]


def meta(table, suffix):
    """orders -> "orders$files";  silver.orders_enriched -> silver."orders_enriched$files" """
    if "." in table:
        schema, name = table.split(".", 1)
        return f'{schema}."{name}${suffix}"'
    return f'"{table}${suffix}"'


def trino_conn():
    while True:
        try:
            conn = trino.dbapi.connect(host=os.environ.get("TRINO_HOST", "trino"),
                                       port=int(os.environ.get("TRINO_PORT", "8080")),
                                       user="rotten-lab", catalog=CATALOG, schema=SCHEMA)
            conn.cursor().execute("SELECT 1").fetchall()
            return conn
        except Exception as e:  # Trino still starting
            print("waiting for trino…", str(e).splitlines()[0][:120])
            time.sleep(3)


def q(conn, sql):
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchall()


def q1(conn, sql):
    rows = q(conn, sql)
    return rows[0][0] if rows else None


def table_location(conn, table):
    ddl = q1(conn, f"SHOW CREATE TABLE {table}")
    m = re.search(r"location = '([^']+)'", ddl)
    return m.group(1) if m else None


def s3_counts(location):
    """Count objects actually sitting on S3 under the table's data/ and metadata/ folders."""
    if not location:
        return None, None
    s3 = boto3.client("s3", region_name=os.environ["AWS_REGION"])  # keys come from AWS_* env vars
    bucket, _, prefix = location.replace("s3://", "").partition("/")
    counts = {"data": 0, "metadata": 0}
    for kind in counts:
        token = None
        while True:
            kw = {"Bucket": bucket, "Prefix": f"{prefix.rstrip('/')}/{kind}/"}
            if token:
                kw["ContinuationToken"] = token
            r = s3.list_objects_v2(**kw)
            counts[kind] += r.get("KeyCount", 0)
            if not r.get("IsTruncated"):
                break
            token = r["NextContinuationToken"]
    return counts["data"], counts["metadata"]


def table_stats(conn, table):
    data_files, avg_bytes, delete_files = q(conn, f"""
        SELECT count_if(content = 0),
               coalesce(avg(CASE WHEN content = 0 THEN file_size_in_bytes END), 0),
               count_if(content <> 0)
        FROM {meta(table, 'files')}""")[0]
    loc = table_location(conn, table)
    s3_data, s3_meta = s3_counts(loc)
    live = data_files + delete_files
    return {
        "rows": q1(conn, f"SELECT count(*) FROM {table}"),
        "snapshots": q1(conn, f"SELECT count(*) FROM {meta(table, 'snapshots')}"),
        "live_data_files": data_files,
        "delete_files": delete_files,
        "avg_file_kb": round(avg_bytes / 1024, 1),
        "manifests_to_plan": q1(conn, f"SELECT count(*) FROM {meta(table, 'manifests')}"),
        "data_files_on_s3": s3_data,
        "unused_data_files_on_s3": (s3_data - live) if s3_data is not None else None,
        "metadata_files_on_s3": s3_meta,
    }


def timed_query(conn, sql, runs=3):
    """Median wall time plus Trino's own stats (splits ~ files opened)."""
    times, splits = [], 0
    for _ in range(runs):
        cur = conn.cursor()
        t = time.time()
        cur.execute(sql)
        cur.fetchall()
        times.append(time.time() - t)
        splits = (cur.stats or {}).get("totalSplits", splits)
    times.sort()
    return times[len(times) // 2], splits
