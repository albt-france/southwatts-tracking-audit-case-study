"""Product feed validator (SIMULATED feed of the fictional Client M).

Rules taken from the Merchant Center "Product data specification"
(https://support.google.com/merchants/answer/7052112?hl=en, read 2026-11-25):
  - required: id, title, link, image_link, price, availability (plus gtin when the product has one);
  - price carries an ISO 4217 currency code;
  - availability is one of in_stock, out_of_stock, preorder, backorder;
  - title at most 150 characters.
Client M rules on top: currency must be the market's currency; links on https; GTIN check digit valid.
Only the rules above are checked: this is not a full Merchant Center review.

    python src/feed_validator.py                      (data/sim/product_feed.parquet)
    python src/feed_validator.py my_feed.csv          (any CSV with the same columns)
Outputs: data/out/feed_validation.csv (one row per issue), data/out/feed_validation_summary.csv
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MARKET_CURRENCY = {"FR": "EUR", "DE": "EUR", "ES": "EUR", "IT": "EUR", "NL": "EUR", "UK": "GBP", "PL": "PLN", "US": "USD"}
AVAILABILITY = {"in_stock", "out_of_stock", "preorder", "backorder"}
REQUIRED = ["sku", "title", "link", "image_link", "price", "currency", "availability"]
SEVERITY = {"missing_required": "disapproval risk", "wrong_currency": "disapproval risk", "invalid_availability": "disapproval risk",
            "invalid_price": "disapproval risk", "title_too_long": "warning", "not_https": "warning", "gtin_check_digit": "warning"}


def gtin_ok(g) -> bool:
    s = str(g or "")
    if not s.isdigit() or len(s) not in (8, 12, 13, 14):
        return False
    d = [int(c) for c in s]
    body, chk = d[:-1][::-1], d[-1]
    return (10 - sum(v * (3 if i % 2 == 0 else 1) for i, v in enumerate(body)) % 10) % 10 == chk


def check(feed: pd.DataFrame) -> pd.DataFrame:
    issues = []
    for r in feed.itertuples(index=False):
        def add(kind, detail):
            issues.append({"sku": r.sku, "market": r.market, "issue": kind, "severity": SEVERITY[kind], "detail": detail})
        for col in REQUIRED:
            v = getattr(r, col)
            if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
                add("missing_required", col)
        if r.currency and r.market in MARKET_CURRENCY and r.currency != MARKET_CURRENCY[r.market]:
            add("wrong_currency", f"{r.currency} instead of {MARKET_CURRENCY[r.market]}")
        if r.availability and r.availability not in AVAILABILITY:
            add("invalid_availability", str(r.availability))
        if r.price is None or pd.isna(r.price) or r.price <= 0:
            add("invalid_price", str(r.price))
        if r.title and len(r.title) > 150:
            add("title_too_long", str(len(r.title)))
        for col in ("link", "image_link"):
            if getattr(r, col) and not str(getattr(r, col)).startswith("https://"):
                add("not_https", col)
        if getattr(r, "gtin", None) and not gtin_ok(r.gtin):
            add("gtin_check_digit", str(r.gtin))
    return pd.DataFrame(issues, columns=["sku", "market", "issue", "severity", "detail"])


def main() -> None:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "sim" / "product_feed.parquet"
    feed = pd.read_parquet(src) if src.suffix == ".parquet" else pd.read_csv(src)
    res = check(feed)
    out = ROOT / "data" / "out"
    res.to_csv(out / "feed_validation.csv", index=False)
    summ = (feed.groupby("market").size().rename("products").to_frame()
            .join(res.groupby("market").sku.nunique().rename("products_with_issue")).fillna(0).astype(int))
    summ["pct_at_risk"] = (100 * summ.products_with_issue / summ.products).round(1)
    summ = summ.join(res.pivot_table(index="market", columns="issue", values="sku", aggfunc="count")).fillna(0)
    summ.reset_index().to_csv(out / "feed_validation_summary.csv", index=False)
    print(f"feed validator: {len(feed)} rows, {len(res)} issues on {res.sku.nunique() if len(res) else 0} SKUs "
          f"({', '.join(f'{m}: {int(v)}' for m, v in summ.products_with_issue.items() if v)})")


if __name__ == "__main__":
    main()
