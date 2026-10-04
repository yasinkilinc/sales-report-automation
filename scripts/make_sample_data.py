"""Generate the fictional sample exports in data/sample (deterministic, seed 42).

Three channels of a small homeware shop, July to September 2026, each with its own quirks:
- Webshop: monthly CSV, EUR, ISO timestamps, a few refunds (negative quantity)
- Marketplace: monthly .xlsx, GBP, two title rows above the header, dd/mm/yyyy text dates,
  each export repeats the last 3 days of the previous month (overlap -> duplicates)
- Wholesale: one semicolon CSV, USD, dd.mm.yyyy dates, decimal comma and thousands dot
Some rows are deliberately broken (bad dates, missing prices, zero quantities, messy SKUs).
"""

import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"
MONTHS = [(2026, 7), (2026, 8), (2026, 9)]
PRODUCTS = [  # sku, name, EUR retail price
    ("MUG-350", "Ceramic mug 350 ml", 14.90),
    ("MUG-500", "Ceramic mug 500 ml", 17.50),
    ("BWL-15", "Stoneware bowl 15 cm", 19.90),
    ("PLT-27", "Dinner plate 27 cm", 22.00),
    ("TPT-1L", "Glass teapot 1 l", 34.90),
    ("CAD-SET", "Coaster set of 4", 12.50),
    ("TWL-LIN", "Linen tea towel", 9.90),
    ("JAR-750", "Storage jar 750 ml", 11.90),
    ("BRD-OAK", "Oak serving board", 39.00),
    ("CND-SOY", "Soy candle 200 g", 16.90),
    ("VAS-20", "Handmade vase 20 cm", 44.00),
    ("SPN-WD", "Wooden spoon set", 13.50),
]


def days_in(year: int, month: int) -> list[date]:
    first = date(year, month, 1)
    nxt = date(year + month // 12, month % 12 + 1, 1)
    return [first + timedelta(days=i) for i in range((nxt - first).days)]


def orders(rng: random.Random, n_orders: int, days: list[date]):
    """(day, [(sku, name, price), ...]) sorted by day, so order numbers can follow the calendar."""
    picked = [
        (rng.choice(days), rng.sample(PRODUCTS, rng.choice([1, 1, 1, 2, 2, 3])))
        for _ in range(n_orders)
    ]
    return sorted(picked, key=lambda o: o[0])


def webshop(rng: random.Random):
    for year, month in MONTHS:
        rows = []
        for n, (day, items) in enumerate(orders(rng, 140, days_in(year, month))):
            stamp = datetime(
                day.year, day.month, day.day, 7 + n * 16 // 140 % 17, rng.randint(0, 59)
            )
            for sku, name, price in items:
                order = f"WS-{10000 + month * 1000 + n}"
                rows.append(
                    [order, f"{stamp:%Y-%m-%d %H:%M}", sku, name, rng.randint(1, 3), f"{price:.2f}"]
                )
        for row in rng.sample(rows, 4):  # refunds
            rows.append([f"{row[0]}-R", row[1], row[2], row[3], -1, row[5]])
        rows[5][2] = f"  {rows[5][2].lower()} "  # messy SKU, still valid
        rows[9][5] = ""  # missing price
        path = OUT / f"webshop_orders_{year}-{month:02d}.csv"
        with path.open("w", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(["Order ID", "Created at", "Lineitem sku", "Lineitem name", "Lineitem quantity", "Lineitem price"])  # fmt: skip
            writer.writerows(sorted(rows, key=lambda r: r[1]))


def marketplace(rng: random.Random):
    tail: list[list] = []
    for year, month in MONTHS:
        rows = []
        for day, items in orders(rng, 90, days_in(year, month)):
            order = f"204-{rng.randint(1000000, 9999999)}-{rng.randint(1000000, 9999999)}"
            for sku, name, price in items:
                gbp = round(price * 0.88, 2)
                rows.append([order, f"{day:%d/%m/%Y}", sku, name, rng.randint(1, 2), gbp])
        rows[3][2] = rows[3][2].replace("-", " - ")  # 'MUG - 350'
        rows[7][1] = "31/09/2026" if month == 9 else rows[7][1]  # impossible date
        wb = Workbook()
        ws = wb.active
        ws.title = "Orders"
        ws.append([f"Marketplace order report {year}-{month:02d}"])
        ws.append([f"Generated {date(year, month, 28) + timedelta(days=5):%Y-%m-%d}"])
        ws.append(["order-id", "purchase-date", "sku", "product-name", "quantity-purchased", "item-price"])  # fmt: skip
        for row in tail + rows:  # overlap: previous month's last 3 days again
            ws.append(row)
        wb.save(OUT / f"marketplace_orders_{year}-{month:02d}.xlsx")
        last_days = {f"{d:%d/%m/%Y}" for d in days_in(year, month)[-3:]}
        tail = [r for r in rows if r[1] in last_days]


def wholesale(rng: random.Random):
    rows = []
    all_days = [d for y, m in MONTHS for d in days_in(y, m) if d.weekday() < 5]
    for n, (day, items) in enumerate(orders(rng, 45, all_days)):
        for sku, name, price in items:
            usd = f"{price * 0.55 * 1.16:.2f}".replace(".", ",")
            rows.append(
                [f"INV-26-{301 + n}", f"{day:%d.%m.%Y}", sku, name, str(rng.randint(12, 80)), usd]
            )
    rows[2][4] = "0"
    rows[11][1] = "2026-08-14"  # wrong date format for this source
    with (OUT / "wholesale_invoices_2026-Q3.csv").open("w", newline="") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\n")
        writer.writerow(["Invoice", "Invoice date", "Item code", "Description", "Qty", "Net price"])
        for n, row in enumerate(rows):
            writer.writerow(row)
            if n == 15:
                writer.writerow([])  # stray blank line


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    webshop(rng)
    marketplace(rng)
    wholesale(rng)
    print(f"sample files written to {OUT}")


if __name__ == "__main__":
    main()
