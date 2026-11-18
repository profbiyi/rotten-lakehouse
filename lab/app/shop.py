"""
The company: an online shop that keeps taking orders and payments.
Writes to its own Postgres database, like any normal app. Knows nothing about the lakehouse.

  python shop.py              run forever (~ORDERS_PER_SECOND orders a second; 0 = paused)
  python shop.py burst 500    insert 500 orders right now, then exit
"""
import os
import random
import sys
import time

import psycopg

DSN = os.environ["SHOP_DSN"]
RATE = float(os.environ.get("ORDERS_PER_SECOND", "8"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS products (
    product_id  BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    price       NUMERIC(12,2) NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    order_id    BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    product_id  BIGINT NOT NULL,
    quantity    INT NOT NULL,
    amount      NUMERIC(12,2) NOT NULL,
    status      TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id  BIGSERIAL PRIMARY KEY,
    order_id    BIGINT NOT NULL,
    method      TEXT NOT NULL,
    amount      NUMERIC(12,2) NOT NULL,
    status      TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);
"""

COUNTRIES = ["Nigeria", "Ghana", "Kenya", "France", "UK", "South Africa", "Egypt", "Canada"]
CATEGORIES = ["Electronics", "Fashion", "Groceries", "Books", "Home", "Beauty"]
FIRST = ["Ada", "Tunde", "Chioma", "Kwame", "Amara", "Yusuf", "Zainab", "Femi", "Ngozi", "Kofi", "Aisha", "Emeka"]
LAST = ["Okafor", "Mensah", "Bello", "Adeyemi", "Otieno", "Diallo", "Eze", "Balogun", "Nwosu", "Asante"]
METHODS = ["card", "card", "card", "bank_transfer", "wallet", "ussd"]


def connect():
    while True:
        try:
            return psycopg.connect(DSN, autocommit=True)
        except psycopg.OperationalError as e:
            print("waiting for postgres…", str(e).splitlines()[0])
            time.sleep(2)


def seed(cur):
    cur.execute("SELECT count(*) FROM products")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO products (name, category, price) VALUES (%s, %s, %s)",
            [(f"{random.choice(CATEGORIES)} item {i}", random.choice(CATEGORIES),
              round(random.uniform(2, 400), 2)) for i in range(1, 201)])
    cur.execute("SELECT count(*) FROM customers")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO customers (name, country) VALUES (%s, %s)",
            [(f"{random.choice(FIRST)} {random.choice(LAST)}", random.choice(COUNTRIES)) for _ in range(2000)])
    cur.execute("SELECT product_id, price FROM products")
    products = cur.fetchall()
    cur.execute("SELECT max(customer_id) FROM customers")
    return products, cur.fetchone()[0]


def make_orders(conn, cur, products, max_customer, n):
    with conn.transaction():
        for _ in range(n):
            product_id, price = random.choice(products)
            qty = random.choice([1, 1, 1, 2, 2, 3, 5])
            amount = round(float(price) * qty, 2)
            status = random.choices(["paid", "pending", "cancelled"], [85, 10, 5])[0]
            cur.execute(
                "INSERT INTO orders (customer_id, product_id, quantity, amount, status) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING order_id",
                (random.randint(1, max_customer), product_id, qty, amount, status))
            order_id = cur.fetchone()[0]
            if status != "cancelled":
                pay_status = "success" if status == "paid" else random.choice(["failed", "processing"])
                cur.execute(
                    "INSERT INTO payments (order_id, method, amount, status) VALUES (%s, %s, %s, %s)",
                    (order_id, random.choice(METHODS), amount, pay_status))


def main():
    conn = connect()
    cur = conn.cursor()
    cur.execute(SCHEMA)
    products, max_customer = seed(cur)

    if len(sys.argv) > 2 and sys.argv[1] == "burst":
        n = int(sys.argv[2])
        make_orders(conn, cur, products, max_customer, n)
        print(f"burst: inserted {n} orders")
        return

    if RATE <= 0:
        print("shop paused (ORDERS_PER_SECOND=0). Send data yourself with: python shop.py burst 500")
        while True:
            time.sleep(60)

    print(f"shop open: {len(products)} products, {max_customer} customers, ~{RATE} orders/second")
    total = 0
    while True:
        n = max(1, int(random.gauss(RATE, RATE / 3)))
        make_orders(conn, cur, products, max_customer, n)
        total += n
        if total % 200 < n:
            print(f"{total} orders so far")
        time.sleep(1)


if __name__ == "__main__":
    main()
