"""
Run the company's dashboard queries and time them.

  docker compose exec loader python bench.py
"""
from common import timed_query, trino_conn

QUERIES = {
    "revenue by hour": "SELECT date_trunc('hour', created_at), sum(amount) FROM orders WHERE status = 'paid' GROUP BY 1",
    "top 10 customers": "SELECT customer_id, sum(amount) s FROM orders GROUP BY 1 ORDER BY s DESC LIMIT 10",
    "payment success rate": "SELECT method, avg(CASE WHEN status = 'success' THEN 1.0 ELSE 0 END) FROM payments GROUP BY 1",
    "orders joined to payments": """SELECT o.status, p.method, count(*) FROM orders o
                                    JOIN payments p ON o.order_id = p.order_id GROUP BY 1, 2""",
}


def main():
    conn = trino_conn()
    print(f"{'query':<28} {'median':>8} {'splits':>8}")
    total = 0
    for name, sql in QUERIES.items():
        secs, splits = timed_query(conn, sql, runs=3)
        total += secs
        print(f"{name:<28} {secs:>7.2f}s {splits:>8}")
    print(f"{'TOTAL':<28} {total:>7.2f}s")


if __name__ == "__main__":
    main()
