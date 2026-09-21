"""Seeded synthetic sources for the lab, written into the raw schema."""
import argparse, random, csv, tempfile, os
from datetime import datetime, timedelta
import duckdb

BASE = datetime(2026, 9, 1)          # fixed, never wall clock
CURRENCIES = ["USD", "EUR", "GBP", "JPY"]
COUNTRIES = ["US", "GB", "DE", "JP", "IN"]
N_CUST, N_SF, N_SHOP = 5_000, 50_000, 20_000

DDL = {
  "customers": "customer_id BIGINT, email VARCHAR, country VARCHAR, _loaded_at TIMESTAMP",
  "currency_exchange_rates": "currency VARCHAR, rate_date DATE, rate_to_usd DOUBLE, _loaded_at TIMESTAMP",
  "salesforce_orders": "order_id BIGINT, customer_id BIGINT, amount DOUBLE, "
                       "currency VARCHAR, created_at TIMESTAMP, _loaded_at TIMESTAMP",
  "shopify_orders": "order_ref VARCHAR, cust_email VARCHAR, total_cents BIGINT, "
                    "curr VARCHAR, placed_at TIMESTAMP, _loaded_at TIMESTAMP",
}


def build(seed, defects):
    rng = random.Random(seed)
    customers = [(i + 1, f"user{i+1}@example.com",
                  COUNTRIES[rng.randrange(len(COUNTRIES))], BASE)
                 for i in range(N_CUST)]

    fx = [(c, (BASE - timedelta(days=d)).date(),
           1.0 if c == "USD" else round(rng.uniform(0.6, 1.4), 6), BASE)
          for d in range(30) for c in CURRENCIES]

    sf = []
    for i in range(N_SF):
        cur = CURRENCIES[rng.randrange(len(CURRENCIES))]
        if "dirty-currency" in defects and i % 500 == 0:
            cur = cur + " " if i % 1000 == 0 else cur.lower()
        cust = rng.randrange(1, N_CUST + 1)
        if "null-customer" in defects and i % 5000 == 0:
            cust = N_CUST + 9000 + i          # points at nobody
        sf.append((i + 1, cust, round(rng.uniform(5, 900), 2), cur,
                   BASE - timedelta(minutes=rng.randrange(0, 60 * 24 * 29)), BASE))

    shop = []
    for i in range(N_SHOP):
        placed = BASE - timedelta(minutes=rng.randrange(0, 60 * 24 * 29))
        shop.append((f"SH-{i+1:07d}", f"user{rng.randrange(1, N_CUST+1)}@example.com",
                     rng.randrange(500, 90_000),
                     CURRENCIES[rng.randrange(len(CURRENCIES))].lower(), placed, BASE))
    if "late-shopify" in defects:
        cutoff = BASE - timedelta(hours=3)
        shop = [r for r in shop if r[4] < cutoff]

    return {"customers": customers, "currency_exchange_rates": fx,
            "salesforce_orders": sf, "shopify_orders": shop}


def generate(db_path="analytics.duckdb", seed=42, defects=frozenset()):
    data = build(seed, set(defects))
    con = duckdb.connect(db_path)
    try:
        con.execute("create schema if not exists raw")
        tmpdir = tempfile.mkdtemp()
        try:
            for table, rows in data.items():
                con.execute(f"drop table if exists raw.{table}")
                con.execute(f"create table raw.{table} ({DDL[table]})")
                csv_path = os.path.join(tmpdir, f"{table}.csv")
                with open(csv_path, "w", newline="") as f:
                    headers = [col.split()[0] for col in DDL[table].split(",")]
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    writer.writerows(rows)
                con.execute(f"COPY raw.{table} FROM '{csv_path}' (FORMAT CSV, HEADER)")
            return {t: len(r) for t, r in data.items()}
        finally:
            for f in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, f))
            os.rmdir(tmpdir)
    finally:
        con.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="analytics.duckdb")
    p.add_argument("--seed", type=int, default=42)
    for f in ["dirty-currency", "null-customer", "late-shopify"]:
        p.add_argument(f"--{f}", action="store_true")
    a = p.parse_args()
    d = {f for f in ["dirty-currency", "null-customer", "late-shopify"]
         if getattr(a, f.replace("-", "_"))}
    for t, c in sorted(generate(a.db, a.seed, d).items()):
        print(f"raw.{t:20s} {c:>7,}")
    print(f"defects: {sorted(d) or ['none']}")
