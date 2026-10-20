"""Build the practice database: a fictional bubble-tea chain "Trà Sữa Mây" (SQLite, deterministic).

  python make_db.py        → data/trasua.db   (core tables + 26 unrelated "noise" tables for Level 5)

Everything is invented. Business rules hidden in the data (the traps the questions test):
  - orders.status is 'completed', 'cancelled' or 'refunded'; revenue counts completed orders only
  - revenue = SUM(order_items.quantity * order_items.unit_price); unit_price can differ from products.price
    (promotions), so products.price is NOT the price paid
  - "số ly" (cups sold) = SUM(quantity), not the number of orders or of order lines
  - customers.tier is 'member', 'silver' or 'gold' ("thành viên vàng" = gold)
  - dates are ISO text 'YYYY-MM-DD HH:MM:SS'; data covers 2026-01-01 .. 2026-09-30
"""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE / "data" / "trasua.db"

CORE = """
CREATE TABLE branches (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL, opened_at TEXT NOT NULL);
CREATE TABLE products (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price INTEGER NOT NULL, is_active INTEGER NOT NULL);
CREATE TABLE customers (
  id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, city TEXT NOT NULL, tier TEXT NOT NULL, joined_at TEXT NOT NULL);
CREATE TABLE staff (
  id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, branch_id INTEGER NOT NULL REFERENCES branches(id), role TEXT NOT NULL);
CREATE TABLE orders (
  id INTEGER PRIMARY KEY, customer_id INTEGER REFERENCES customers(id), branch_id INTEGER NOT NULL REFERENCES branches(id),
  staff_id INTEGER REFERENCES staff(id), ordered_at TEXT NOT NULL, channel TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE order_items (
  id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL REFERENCES products(id),
  size TEXT NOT NULL, quantity INTEGER NOT NULL, unit_price INTEGER NOT NULL);
"""

BRANCHES = [("Mây Nguyễn Huệ", "Hồ Chí Minh", "2024-03-01"), ("Mây Thảo Điền", "Hồ Chí Minh", "2024-09-15"),
            ("Mây Phú Nhuận", "Hồ Chí Minh", "2025-06-01"), ("Mây Hoàn Kiếm", "Hà Nội", "2024-11-20"),
            ("Mây Cầu Giấy", "Hà Nội", "2026-04-10"), ("Mây Hải Châu", "Đà Nẵng", "2025-02-14")]
PRODUCTS = [("Trà sữa trân châu", "trà sữa", 35000), ("Trà sữa matcha", "trà sữa", 42000),
            ("Trà sữa khoai môn", "trà sữa", 39000), ("Trà sữa ô long", "trà sữa", 40000),
            ("Trà đào cam sả", "trà trái cây", 38000), ("Trà vải", "trà trái cây", 36000),
            ("Trà chanh dây", "trà trái cây", 33000), ("Cà phê sữa đá", "cà phê", 29000),
            ("Bạc xỉu", "cà phê", 32000), ("Sữa tươi trân châu đường đen", "sữa tươi", 45000),
            ("Sữa chua dâu", "sữa chua", 41000), ("Bánh flan", "bánh", 20000)]
FIRST = ["An", "Bình", "Châu", "Dũng", "Giang", "Hà", "Hải", "Hạnh", "Hiếu", "Hoa", "Hùng", "Khánh", "Lan", "Linh",
         "Long", "Mai", "Minh", "Nam", "Ngọc", "Phong", "Phương", "Quân", "Quỳnh", "Sơn", "Tâm", "Thảo", "Trang",
         "Tuấn", "Vy", "Yến"]
LAST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Võ", "Đặng", "Bùi", "Đỗ", "Ngô"]
MID = ["Văn", "Thị", "Minh", "Ngọc", "Thanh", "Hoàng", "Gia", "Bảo"]

NOISE = ["suppliers", "purchase_orders", "inventory", "inventory_moves", "ingredients", "recipes", "equipment",
         "maintenance_logs", "shifts", "timesheets", "payroll", "leave_requests", "promotions", "promotion_usage",
         "marketing_campaigns", "ad_spend", "social_posts", "reviews", "complaints", "delivery_partners",
         "delivery_fees", "vouchers", "gift_cards", "utilities_bills", "rent_contracts", "audit_logs"]


def ts(d):
    return d.strftime("%Y-%m-%d %H:%M:%S")


def main():
    rnd = random.Random(2026)
    DB.parent.mkdir(exist_ok=True)
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(CORE)
    con.executemany("INSERT INTO branches VALUES (?,?,?,?)", [(i + 1, *b) for i, b in enumerate(BRANCHES)])
    con.executemany("INSERT INTO products VALUES (?,?,?,?,?)",
                    [(i + 1, n, c, p, 0 if n == "Trà sữa ô long" else 1) for i, (n, c, p) in enumerate(PRODUCTS)])
    cities = ["Hồ Chí Minh"] * 5 + ["Hà Nội"] * 3 + ["Đà Nẵng"] * 2
    customers = []
    for i in range(600):
        joined = datetime(2024, 1, 1) + timedelta(days=rnd.randint(0, 990))
        tier = rnd.choices(["member", "silver", "gold"], [70, 22, 8])[0]
        name = f"{rnd.choice(LAST)} {rnd.choice(MID)} {rnd.choice(FIRST)}"
        customers.append((i + 1, name, rnd.choice(cities), tier, ts(joined)))
    con.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)
    staff = []
    for b in range(1, 7):
        for k in range(4):
            role = "quản lý" if k == 0 else "pha chế" if k < 3 else "thu ngân"
            staff.append((len(staff) + 1, f"{rnd.choice(LAST)} {rnd.choice(MID)} {rnd.choice(FIRST)}", b, role))
    con.executemany("INSERT INTO staff VALUES (?,?,?,?)", staff)
    weights = [3, 2, 1.5, 2.2, 1, 1.4]                       # branch popularity
    pop = [5, 4, 3, 1, 4.5, 2, 2, 3, 2.5, 3.5, 1.5, 1]       # product popularity
    orders, items = [], []
    day = datetime(2026, 1, 1)
    while day <= datetime(2026, 9, 30):
        for b in range(1, 7):
            opened = datetime.fromisoformat(BRANCHES[b - 1][2])
            if day < opened:
                continue
            season = 1.25 if day.month in (5, 6, 7) else 1.0  # summer is busier
            for _ in range(rnd.randint(2, 5) if rnd.random() < weights[b - 1] / 3.2 * season else rnd.randint(0, 2)):
                oid = len(orders) + 1
                when = day + timedelta(hours=rnd.randint(8, 21), minutes=rnd.randint(0, 59), seconds=rnd.randint(0, 59))
                cust = rnd.randint(1, 600) if rnd.random() < 0.8 else None      # 20% walk-in, no customer
                status = rnd.choices(["completed", "cancelled", "refunded"], [90, 7, 3])[0]
                channel = rnd.choices(["tại quầy", "grab", "shopeefood", "app"], [55, 20, 15, 10])[0]
                orders.append((oid, cust, b, (b - 1) * 4 + rnd.randint(2, 4), ts(when), channel, status))
                for _ in range(rnd.choices([1, 2, 3], [60, 30, 10])[0]):
                    pid = rnd.choices(range(1, 13), pop)[0]
                    if pid == 4 and day >= datetime(2026, 7, 1):          # ô long discontinued in July
                        pid = 2
                    price = PRODUCTS[pid - 1][2]
                    size = rnd.choices(["M", "L"], [65, 35])[0]
                    if size == "L":
                        price += 6000
                    if day.month == 8 and pid in (5, 6, 7):                # August promo on fruit teas: -20%
                        price = int(price * 0.8)
                    items.append((len(items) + 1, oid, pid, size, rnd.choices([1, 2, 3, 4], [70, 20, 7, 3])[0], price))
        day += timedelta(days=1)
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", orders)
    con.executemany("INSERT INTO order_items VALUES (?,?,?,?,?,?)", items)
    for t in NOISE:                                             # Level 5: a realistic, much bigger schema
        cols = ", ".join(f"{c} {ty}" for c, ty in rnd.sample(
            [("branch_id", "INTEGER"), ("amount", "INTEGER"), ("note", "TEXT"), ("created_at", "TEXT"),
             ("status", "TEXT"), ("product_id", "INTEGER"), ("staff_id", "INTEGER"), ("quantity", "INTEGER"),
             ("name", "TEXT"), ("updated_at", "TEXT"), ("customer_id", "INTEGER"), ("price", "INTEGER")], 5))
        con.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY, {cols})")
    con.commit()
    n = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("orders", "order_items", "customers")}
    print("✓", DB.name, n, "+", len(NOISE), "noise tables")


if __name__ == "__main__":
    main()
