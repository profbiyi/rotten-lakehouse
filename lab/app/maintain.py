"""
Clean up the rot with Trino's Iceberg table procedures, one chore at a time.

  docker compose exec loader python maintain.py optimize     # compaction (bin-pack small files)
  docker compose exec loader python maintain.py manifests    # optimize_manifests
  docker compose exec loader python maintain.py expire       # expire_snapshots (+ deletes files only old snapshots used)
  docker compose exec loader python maintain.py orphans      # remove_orphan_files
  docker compose exec loader python maintain.py all          # all four, in the right order

Add a table name to do one table only, e.g.  maintain.py optimize orders
"""
import sys
import time

from common import TABLES, q, table_stats, trino_conn

STEPS = {
    "optimize":  "ALTER TABLE {t} EXECUTE optimize(file_size_threshold => '128MB')",
    "manifests": "ALTER TABLE {t} EXECUTE optimize_manifests",
    "expire":    "ALTER TABLE {t} EXECUTE expire_snapshots(retention_threshold => '0s')",
    "orphans":   "ALTER TABLE {t} EXECUTE remove_orphan_files(retention_threshold => '0s')",
}
ORDER = ["optimize", "manifests", "expire", "orphans"]
SHOW = ["snapshots", "live_data_files", "avg_file_kb", "manifests_to_plan",
        "data_files_on_s3", "unused_data_files_on_s3", "metadata_files_on_s3"]


def show(title, before, after):
    print(f"\n  {title}")
    for k in SHOW:
        b, a = before.get(k), after.get(k)
        arrow = "  " if b == a else ("↓ " if (a or 0) < (b or 0) else "↑ ")
        print(f"    {k:<26} {str(b):>8} → {str(a):<8} {arrow}")


def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    tables = [sys.argv[2]] if len(sys.argv) > 2 else TABLES
    steps = ORDER if step == "all" else [step]
    if any(s not in STEPS for s in steps):
        sys.exit(f"unknown step {step}; use one of: {', '.join(ORDER)}, all")

    conn = trino_conn()
    for t in tables:
        for s in steps:
            before = table_stats(conn, t)
            sql = STEPS[s].format(t=t)
            print(f"\n{t}: {sql}")
            start = time.time()
            q(conn, sql)
            show(f"{s} took {time.time() - start:.1f}s", before, table_stats(conn, t))


if __name__ == "__main__":
    main()
