"""Collect the public references used as the rulebook of the study (PUBLIC DATA).

- Official documentation pages (Google, Meta, CNIL) are fetched once and cached in data/cache/
  (not committed). For each page we record the HTTP status, the read date and whether the
  key facts we cite are present on the page (simple keyword checks, printed in sources.csv).
- IAB TCF Global Vendor List v3: version, last update and vendor count.
- Public holidays 2026 for the 8 simulated markets (date.nager.at), used by the simulation.

Polite: at most 1 request per second, generic User-Agent, no account, no key, no personal data.

    python src/collect_refs.py
Outputs: data/reference/sources.csv, data/reference/iab_gvl_summary.json, data/reference/holidays_2026.csv
"""
import json
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
REF = ROOT / "data" / "reference"
UA = {"User-Agent": "tracking-case-study/1.0", "Accept-Language": "en-US,en;q=0.9"}
TODAY = date.today().isoformat()

DOCS = [
    ("ga4_recommended_events", "https://developers.google.com/analytics/devguides/collection/ga4/reference/events",
     ["purchase", "transaction_id", "items"]),
    ("ga4_bigquery_export_schema", "https://support.google.com/analytics/answer/7029846?hl=en",
     ["event_params", "user_pseudo_id"]),
    ("ga4_measurement_protocol", "https://developers.google.com/analytics/devguides/collection/protocol/ga4",
     ["server-to-server", "Measurement Protocol"]),
    ("meta_capi_deduplication", "https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events",
     ["event_id"]),
    ("google_tag_gateway", "https://developers.google.com/tag-platform/tag-manager/gateway",
     ["gateway"]),
    ("merchant_center_product_data_spec", "https://support.google.com/merchants/answer/7052112?hl=en",
     ["image_link", "availability", "price"]),
    ("cnil_cookies_rules", "https://www.cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies",
     ["consentement"]),
]
GVL = "https://vendor-list.consensu.org/v3/vendor-list.json"
MARKETS = {"FR": "FR", "DE": "DE", "ES": "ES", "IT": "IT", "UK": "GB", "NL": "NL", "PL": "PL", "US": "US"}

_last = 0.0


def fetch(url: str, cache_name: str) -> tuple[int, str]:
    """GET with a 1 request/second limit and an on-disk cache."""
    global _last
    path = CACHE / cache_name
    if path.exists():
        return 200, path.read_text(encoding="utf-8", errors="ignore")
    wait = 1.0 - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    r = requests.get(url, headers=UA, timeout=40)
    if r.status_code == 200:
        path.write_text(r.text, encoding="utf-8")
    return r.status_code, r.text


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    REF.mkdir(parents=True, exist_ok=True)
    rows = []
    for key, url, words in DOCS:
        status, text = fetch(url, f"{key}.html")
        low = text.lower()
        rows.append({"source": key, "url": url, "http_status": status, "read_on": TODAY,
                     "checked_keywords": ";".join(words),
                     "keywords_found": all(w.lower() in low for w in words)})

    status, text = fetch(GVL, "iab_gvl_v3.json")
    gvl = json.loads(text)
    summary = {"url": GVL, "read_on": TODAY, "http_status": status,
               "vendorListVersion": gvl.get("vendorListVersion"), "lastUpdated": gvl.get("lastUpdated"),
               "vendors": len(gvl.get("vendors", {})), "purposes": len(gvl.get("purposes", {})),
               "specialFeatures": len(gvl.get("specialFeatures", {}))}
    (REF / "iab_gvl_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    rows.append({"source": "iab_tcf_gvl_v3", "url": GVL, "http_status": status, "read_on": TODAY,
                 "checked_keywords": "vendors", "keywords_found": summary["vendors"] > 0})

    hol = []
    for market, iso in MARKETS.items():
        url = f"https://date.nager.at/api/v3/PublicHolidays/2026/{iso}"
        status, text = fetch(url, f"holidays_2026_{iso}.json")
        for h in json.loads(text):
            if h.get("global", True):
                hol.append({"market": market, "date": h["date"], "name": h["name"]})
        rows.append({"source": f"nager_holidays_{iso}", "url": url, "http_status": status, "read_on": TODAY,
                     "checked_keywords": "date", "keywords_found": True})
    pd.DataFrame(hol).drop_duplicates().to_csv(REF / "holidays_2026.csv", index=False)
    pd.DataFrame(rows).to_csv(REF / "sources.csv", index=False)
    print(pd.DataFrame(rows)[["source", "http_status", "keywords_found"]].to_string(index=False))
    print({k: summary[k] for k in ("vendorListVersion", "lastUpdated", "vendors", "purposes")})


if __name__ == "__main__":
    main()
