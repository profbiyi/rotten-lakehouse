# Part 2: Fix it

The lakehouse from Part 1 now has thousands of tiny files. We fix it in four steps, one SQL file each. Run them in DBeaver or the Trino CLI, and run [`00_health_check.sql`](00_health_check.sql) before and after every step.

```bash
# from the lakehouse/ folder
docker compose exec trino trino -f /solutions/00_health_check.sql
```

## First, pause the loader

```bash
docker compose stop loader
```
So the numbers stay still while we look at them. (In a real company the pipeline keeps running; we'll come back to that at the end.)

---

## The four fixes

| Step | File | In plain words | What you'll see |
|---|---|---|---|
| 1 | [`01_compact.sql`](01_compact.sql) | Empty 500 small envelopes into one big folder | **files** way down, **avg_kb** way up, **versions** +1. But in S3 the old small files are **still there**. |
| 2 | [`02_tidy_manifests.sql`](02_tidy_manifests.sql) | Rewrite 500 sticky notes (lists of files) into one page | Fewer manifests: queries plan faster |
| 3 | [`03_expire_old_versions.sql`](03_expire_old_versions.sql) | Shred old drafts you'll never read | **versions** down to 1. In S3 the old small files are **gone**. Storage finally drops. |
| 4 | [`04_remove_orphan_files.sql`](04_remove_orphan_files.sql) | Throw away boxes with no label | Removes leftovers from crashed writes. Often nothing to do. |

### Why don't the files disappear after step 1?

Because Iceberg keeps **old versions** of the table, so you can time travel. The old versions still point to the old small files, so Iceberg can't delete them yet. Compaction only adds a *new* version made of big files.

```
after step 1:   newest version → 3 big files
                old versions   → 500 small files   (still on S3)

after step 3:   newest version → 3 big files
                old versions   → gone, and their 500 small files deleted from S3
```

**To see it in S3:** select the table's `data/` folder → **Actions → Calculate total size**. It shows the number of objects. Do this before step 1, after step 1 (it goes **up**), and after step 3 (it goes **down**).

---

## After the fixes

1. Run `00_health_check.sql`: few files, big files, one version.
2. Run a dashboard query and compare it in the Trino UI (http://localhost:8080) with one from before: fewer splits, faster.
3. Start the loader again:
   ```bash
   docker compose start loader
   ```
   Wait 5 minutes and run the health check. **The small files are coming back.**

## The lesson

Cleaning up once doesn't fix it. **Maintenance is a job you schedule**, like backups:

| Job | How often (typical) |
|---|---|
| Compact | Every hour or every night, on the busiest tables |
| Tidy manifests | Every day or week |
| Expire old versions | Every day, keeping the last 7 days |
| Remove orphan files | Every week, keeping the last 7 days |

In a real company, an orchestrator (Airflow, Prefect, Dagster, a cron job) runs these same SQL statements on a schedule, so nobody has to remember.
