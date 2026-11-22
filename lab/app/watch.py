"""
Live rot meter. Refreshes every few seconds while the shop and loader run.

  docker compose exec loader python watch.py              # orders table
  docker compose exec loader python watch.py payments     # payments table
  docker compose exec loader python watch.py silver.orders_enriched
  docker compose exec loader python watch.py gold.daily_revenue
"""
import sys
import time

from common import table_stats, timed_query, trino_conn

TABLE = sys.argv[1] if len(sys.argv) > 1 else "orders"
EVERY = 5
QUERY_EVERY = 4  # run the dashboard query every Nth refresh (it gets slower as the table rots)

DASHBOARD = {
    "orders": "SELECT date_trunc('hour', created_at) h, status, count(*), sum(amount) FROM orders GROUP BY 1, 2",
    "payments": "SELECT method, status, count(*), sum(amount) FROM payments GROUP BY 1, 2",
    "silver.orders_enriched": "SELECT country, category, count(*), sum(amount) FROM silver.orders_enriched GROUP BY 1, 2",
    "gold.daily_revenue": "SELECT * FROM gold.daily_revenue ORDER BY order_day DESC, revenue DESC",
}.get(TABLE, f"SELECT count(*) FROM {TABLE}")

LABELS = [
    ("rows", "rows in the table"),
    ("snapshots", "snapshots (commits kept)"),
    ("live_data_files", "data files the query reads"),
    ("delete_files", "delete files (from MERGE/DELETE)"),
    ("avg_file_kb", "average file size (KB)"),
    ("manifests_to_plan", "manifests to plan"),
    ("data_files_on_s3", "data files on S3"),
    ("unused_data_files_on_s3", "  of which unused (old snapshots)"),
    ("metadata_files_on_s3", "metadata files on S3"),
]


def main():
    conn = trino_conn()
    tick, last_q = 0, None
    while True:
        try:
            s = table_stats(conn, TABLE)
        except Exception as e:
            print("table not ready yet:", str(e).splitlines()[0][:100])
            time.sleep(EVERY)
            continue
        if tick % QUERY_EVERY == 0:
            secs, splits = timed_query(conn, DASHBOARD, runs=1)
            last_q = f"{secs:.2f} s   ({splits} splits)"
        tick += 1
        print("\033[2J\033[H", end="")  # clear screen
        print(f"ROTTEN LAKEHOUSE WATCH   lakehouse.{TABLE if '.' in TABLE else 'bronze.' + TABLE}   {time.strftime('%H:%M:%S')}\n")
        for key, label in LABELS:
            print(f"  {label:<36} {s[key]}")
        print(f"\n  {'dashboard query':<36} {last_q}")
        print("\n  Ctrl+C to stop. Run maintenance in another terminal and watch these numbers move.")
        time.sleep(EVERY)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
