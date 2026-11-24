"""
THE SHOP: a pretend online shop.

It keeps taking orders and payments, and saves them in its own Postgres database,
just like a real app. It knows nothing about the lakehouse.
"""
import os
import random
import time

import psycopg

DATABASE = os.environ["SHOP_DSN"]
ORDERS_PER_SECOND = int(os.environ.get("ORDERS_PER_SECOND", "8"))

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id BIGSERIAL PRIMARY KEY,
    name        TEXT,
    country     TEXT
);
CREATE TABLE IF NOT EXISTS products (
    product_id  BIGSERIAL PRIMARY KEY,
    name        TEXT,
    category    TEXT,
    price       NUMERIC(12,2)
);
CREATE TABLE IF NOT EXISTS orders (
    order_id    BIGSERIAL PRIMARY KEY,
    customer_id BIGINT,
    product_id  BIGINT,
    quantity    INT,
    amount      NUMERIC(12,2),
    status      TEXT,
    created_at  TIMESTAMP DEFAULT now()
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id  BIGSERIAL PRIMARY KEY,
    order_id    BIGINT,
    method      TEXT,
    amount      NUMERIC(12,2),
    status      TEXT,
    created_at  TIMESTAMP DEFAULT now()
);
"""

COUNTRIES = ["Nigeria", "Ghana", "Kenya", "France", "UK", "South Africa", "Egypt", "Canada"]
CATEGORIES = ["Electronics", "Fashion", "Groceries", "Books", "Home", "Beauty"]
NAMES = ["Ada", "Tunde", "Chioma", "Kwame", "Amara", "Yusuf", "Zainab", "Femi", "Ngozi", "Kofi"]
PAYMENT_METHODS = ["card", "card", "bank_transfer", "wallet", "ussd"]


# 1. Connect (wait if Postgres is still starting)
while True:
    try:
        db = psycopg.connect(DATABASE, autocommit=True)
        break
    except psycopg.OperationalError:
        print("waiting for postgres...")
        time.sleep(2)
cur = db.cursor()

# 2. Create the tables, and some customers and products the first time
cur.execute(CREATE_TABLES)
cur.execute("SELECT count(*) FROM customers")
if cur.fetchone()[0] == 0:
    for _ in range(2000):
        cur.execute("INSERT INTO customers (name, country) VALUES (%s, %s)",
                    (random.choice(NAMES), random.choice(COUNTRIES)))
    for i in range(200):
        cur.execute("INSERT INTO products (name, category, price) VALUES (%s, %s, %s)",
                    (f"product {i}", random.choice(CATEGORIES), round(random.uniform(2, 400), 2)))

cur.execute("SELECT product_id, price FROM products")
products = cur.fetchall()
print(f"Shop is open: about {ORDERS_PER_SECOND} orders per second")

# 3. Take orders forever
total = 0
while True:
    for _ in range(ORDERS_PER_SECOND):
        product_id, price = random.choice(products)
        quantity = random.choice([1, 1, 2, 3])
        amount = round(float(price) * quantity, 2)
        status = random.choices(["paid", "pending", "cancelled"], [85, 10, 5])[0]

        cur.execute("INSERT INTO orders (customer_id, product_id, quantity, amount, status) "
                    "VALUES (%s, %s, %s, %s, %s) RETURNING order_id",
                    (random.randint(1, 2000), product_id, quantity, amount, status))
        order_id = cur.fetchone()[0]

        if status != "cancelled":
            cur.execute("INSERT INTO payments (order_id, method, amount, status) VALUES (%s, %s, %s, %s)",
                        (order_id, random.choice(PAYMENT_METHODS), amount,
                         "success" if status == "paid" else "failed"))
    total += ORDERS_PER_SECOND
    if total % 500 < ORDERS_PER_SECOND:
        print(f"{total} orders so far")
    time.sleep(1)
