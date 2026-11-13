"""
Rotten Lakehouse: Iceberg side (Spark + Lakekeeper + Silo).

  python iceberg_rot.py rot --batches 200 --rows 50   # many tiny appends
  python iceberg_rot.py inspect                       # how rotten is it?
  python iceberg_rot.py bench                         # time a scan query
  python iceberg_rot.py fix                           # compaction + expiry + manifests + orphans
  python iceberg_rot.py reset                         # drop the table and start again
"""
import argparse
import os
import time

from pyspark.conf import SparkConf
from pyspark.sql import SparkSession

CATALOG = "lakekeeper"
TABLE = f"{CATALOG}.rot.events"


def spark_session() -> SparkSession:
    import pyspark

    spark_minor = ".".join(pyspark.__version__.split(".")[:2])
    iceberg = os.environ.get("ICEBERG_VERSION", "1.10.0")
    conf = (
        SparkConf()
        .setMaster("local[*]")
        .setAppName("rotten-lakehouse-iceberg")
        .set("spark.jars.packages",
             f"org.apache.iceberg:iceberg-spark-runtime-{spark_minor}_2.12:{iceberg},"
             f"org.apache.iceberg:iceberg-aws-bundle:{iceberg}")
        .set("spark.sql.extensions",
             "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .set(f"spark.sql.catalog.{CATALOG}", "org.apache.iceberg.spark.SparkCatalog")
        .set(f"spark.sql.catalog.{CATALOG}.type", "rest")
        .set(f"spark.sql.catalog.{CATALOG}.uri",
             os.environ.get("CATALOG_URL", "http://lakekeeper:8181/catalog"))
        .set(f"spark.sql.catalog.{CATALOG}.warehouse", os.environ.get("WAREHOUSE", "demo"))
        .set(f"spark.sql.catalog.{CATALOG}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .set("spark.sql.defaultCatalog", CATALOG)
        # Keep each append to ONE file so the rot is easy to count
        .set("spark.sql.shuffle.partitions", "1")
        .set("spark.default.parallelism", "1")
    )
    spark = SparkSession.builder.config(conf=conf).getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def ensure_table(spark):
    spark.sql(f"CREATE NAMESPACE IF NOT EXISTS {CATALOG}.rot")
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            event_id  BIGINT,
            user_id   INT,
            amount    DOUBLE,
            event_ts  TIMESTAMP
        ) USING iceberg
    """)


def scalar(spark, sql):
    return spark.sql(sql).collect()[0][0]


def stats(spark) -> dict:
    return {
        "rows": scalar(spark, f"SELECT count(*) FROM {TABLE}"),
        "live_data_files": scalar(spark, f"SELECT count(*) FROM {TABLE}.files"),
        "files_held_by_history": scalar(spark, f"SELECT count(DISTINCT file_path) FROM {TABLE}.all_data_files"),
        "avg_file_kb": scalar(spark, f"SELECT round(avg(file_size_in_bytes) / 1024, 1) FROM {TABLE}.files"),
        "snapshots": scalar(spark, f"SELECT count(*) FROM {TABLE}.snapshots"),
        "manifests": scalar(spark, f"SELECT count(*) FROM {TABLE}.manifests"),
        "metadata_json_files": scalar(spark, f"SELECT count(*) FROM {TABLE}.metadata_log_entries"),
    }


def print_stats(title, s):
    print(f"\n=== {title} ===")
    for k, v in s.items():
        print(f"  {k:<24} {v}")


def cmd_rot(spark, batches, rows):
    ensure_table(spark)
    start = scalar(spark, f"SELECT coalesce(max(event_id), 0) FROM {TABLE}")
    t0 = time.time()
    for i in range(batches):
        lo = start + i * rows + 1
        # One tiny append = one data file + one manifest + one snapshot + one metadata.json
        spark.range(lo, lo + rows).selectExpr(
            "id AS event_id",
            "CAST(rand() * 10000 AS INT) AS user_id",
            "round(rand() * 500, 2) AS amount",
            "current_timestamp() AS event_ts",
        ).coalesce(1).writeTo(TABLE).append()
        if (i + 1) % 25 == 0:
            print(f"  appended {i + 1}/{batches} batches ({time.time() - t0:.0f}s)")
    print_stats("Iceberg after small writes", stats(spark))


def cmd_bench(spark, runs=5):
    q = f"SELECT user_id % 10 AS bucket, count(*), sum(amount) FROM {TABLE} GROUP BY 1"
    spark.sql(q).collect()  # warm-up
    times = []
    for _ in range(runs):
        t = time.time()
        spark.sql(q).collect()
        times.append(time.time() - t)
    print(f"\nIceberg query: median {sorted(times)[len(times) // 2] * 1000:.0f} ms over {runs} runs")


def cmd_fix(spark):
    print_stats("Iceberg BEFORE maintenance", stats(spark))
    now = scalar(spark, "SELECT current_timestamp()")
    ident = "rot.events"

    print("\n1. rewrite_data_files (compaction)")
    spark.sql(f"""
        CALL {CATALOG}.system.rewrite_data_files(
            table => '{ident}',
            options => map('min-input-files', '2', 'target-file-size-bytes', '134217728'))
    """).show(truncate=False)

    print("2. expire_snapshots (drop history, free old files)")
    spark.sql(f"""
        CALL {CATALOG}.system.expire_snapshots(
            table => '{ident}', older_than => TIMESTAMP '{now}', retain_last => 1)
    """).show(truncate=False)

    print("3. rewrite_manifests")
    spark.sql(f"CALL {CATALOG}.system.rewrite_manifests(table => '{ident}')").show(truncate=False)

    print("4. remove_orphan_files (files no snapshot points to, e.g. from failed writes)")
    try:
        spark.sql(f"""
            CALL {CATALOG}.system.remove_orphan_files(
                table => '{ident}', older_than => TIMESTAMP '{now}')
        """).show(truncate=False)
    except Exception as e:  # listing can be refused with vended credentials
        print(f"   skipped: {str(e).splitlines()[0]}")

    print_stats("Iceberg AFTER maintenance", stats(spark))


def cmd_reset(spark):
    spark.sql(f"DROP TABLE IF EXISTS {TABLE} PURGE")
    print("dropped", TABLE)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["rot", "inspect", "bench", "fix", "reset"])
    p.add_argument("--batches", type=int, default=200)
    p.add_argument("--rows", type=int, default=50)
    a = p.parse_args()

    spark = spark_session()
    if a.command == "rot":
        cmd_rot(spark, a.batches, a.rows)
    elif a.command == "inspect":
        print_stats("Iceberg", stats(spark))
    elif a.command == "bench":
        cmd_bench(spark)
    elif a.command == "fix":
        cmd_fix(spark)
    elif a.command == "reset":
        cmd_reset(spark)
