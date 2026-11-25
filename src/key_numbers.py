"""Collect the headline numbers used by the dashboard, the PDF and the README into data/out/key_numbers.json.
Every number is read from data/out (SQL, validators, monitoring) or data/reference: nothing is typed by hand.

    python src/key_numbers.py
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "out"


def csv(name):
    return pd.read_csv(OUT / f"{name}.csv")


def build() -> dict:
    k = {}
    ra = csv("real_audit_summary").set_index("metric").value
    rev = csv("real_audit_revenue_impact").iloc[0]
    gap = csv("real_audit_duplicate_gap").set_index("gap_bucket").duplicated_ids
    ch = csv("real_channels").set_index("channel")
    k["real"] = {
        "purchase_events": int(ra.purchase_events), "distinct_ids": int(ra.distinct_transaction_ids),
        "without_id": int(ra.purchases_without_id), "pct_without_id": round(100 * ra.purchases_without_id / ra.purchase_events, 1),
        "duplicated_ids": int(ra.duplicated_ids), "extra_rows": int(ra.extra_purchase_rows),
        "dup_within_1min": int(gap.get("1: < 1 min", 0)), "pct_revenue_counted_twice": float(rev.pct_revenue_counted_twice),
        "revenue_counted_twice": float(rev.revenue_counted_twice),
        "page_views": int(ra.page_views), "self_referral_pv": int(ra.page_views_self_referral),
        "pct_self_referral_pv": round(100 * ra.page_views_self_referral / ra.page_views, 1),
        "missing_medium_pv": int(ra.page_views_missing_medium),
        "pct_missing_medium_pv": round(100 * ra.page_views_missing_medium / ra.page_views, 1),
        "data_deleted_pv": int(ra.page_views_medium_data_deleted), "sessions": int(ra.sessions),
        "self_ref_sessions": int(ch.loc["Self-referral (bug)", "sessions"]),
        "self_ref_session_purchases": int(ch.loc["Self-referral (bug)", "purchases"]),
        "pct_purchases_in_self_ref_sessions": round(100 * ch.loc["Self-referral (bug)", "purchases"] / ch.purchases.sum(), 1),
    }
    d = csv("real_audit_daily")
    d["date"] = pd.to_datetime(d.date)
    brk = d.date[(d.self_referral_share < 0.05) & (d.date > d.date.min())].min()     # first day under 5%
    share = lambda x: round(100 * (x.self_referral_share * x.page_views).sum() / x.page_views.sum(), 1)
    k["real"].update({"selfref_break_date": brk.strftime("%Y-%m-%d"), "selfref_before_pct": share(d[d.date < brk]),
                      "selfref_after_pct": share(d[d.date >= brk])})
    rec = csv("reconciliation_weekly")
    head = csv("reconciliation_headline").set_index("platform")
    g = rec[rec.platform == "google_ads"]
    meta = rec[rec.platform == "meta"]
    frs = meta[meta.market.isin(["FR", "ES"])]
    before = frs[frs.week < "2026-10-05"]
    after = frs[frs.week >= "2026-10-12"]
    rb = before.platform_conversions.sum() / before.backend_orders.sum()
    raf = after.platform_conversions.sum() / after.backend_orders.sum()
    k["recon"] = {
        "market_weeks": int(len(rec)), "unexplained": int((rec.category == "unexplained").sum()),
        "anomalous": int((rec.category == "anomalous").sum()), "expected": int((rec.category == "expected").sum()),
        "pct_explained": 100.0 * (rec.category != "unexplained").mean(),
        "google_r0": float(g.expected_ratio.iloc[0]), "google_gap_pct": round(100 * (g.expected_ratio.iloc[0] - 1), 1),
        "google_anomalous": int(head.loc["google_ads", "anomalous_market_weeks"]),
        "meta_r0": float(meta.expected_ratio.iloc[0]), "meta_frs_before": round(rb, 2), "meta_frs_after": round(raf, 2),
        "meta_multiplier": round(raf / rb, 1), "meta_anomalous": int(head.loc["meta", "anomalous_market_weeks"]),
    }
    cb = csv("consent_breaks")
    k["consent"] = {"up_pct": round(100 * cb[cb.dir == "up"].mean_deviation.iloc[0], 1),
                    "down_pct": round(100 * cb[cb.dir == "down"].mean_deviation.iloc[0], 1),
                    "pre_choice_share": round(100 * cb[cb.dir == "up"].mean_pre_choice_share.iloc[0], 1)}
    u = csv("utm_unassigned_summary").set_index("agency")
    ua = csv("utm_by_agency").set_index("agency")
    links = csv("utm_validation")
    k["utm"] = {"pct_unassigned": float(u.loc["ALL", "pct_unassigned"]), "agy2_unassigned": float(u.loc["AGY2", "pct_unassigned"]),
                "links": int(len(links)), "links_fail": int((links.status == "FAIL").sum()),
                "pct_links_compliant": round(100 * (links.status == "PASS").mean(), 1),
                "agy2_compliant": float(ua.loc["AGY2", "pct_compliant"]),
                "missing_medium_pct": round(100 * links.issues.fillna("").str.contains("utm_medium missing").mean(), 1)}
    dq = csv("dedup_ga4_market").set_index("market")
    k["dedup"] = {"it_extra_pct": float(dq.loc["IT", "pct_extra_purchases"]),
                  "purchase_events": int(dq.purchase_events.sum()), "unique": int(dq.unique_transactions.sum()),
                  "pct_deduplicated": round(100 * dq.unique_transactions.sum() / dq.purchase_events.sum(), 2)}
    sa = csv("server_alerts").set_index("destination")
    av = csv("server_availability").set_index("destination")
    k["server"] = {"alert_first_hour": str(sa.loc["meta_capi", "first_alert_hour"]), "alert_raised": str(sa.loc["meta_capi", "alert_raised_at"]),
                   "failed_events": int(sa.loc["meta_capi", "failed_events"]), "alert_hours": int(sa.loc["meta_capi", "alert_hours"]),
                   "delivered_pct": round(100 * (1 - csv("server_hourly").errors.sum() / csv("server_hourly").events.sum()), 2),
                   "meta_capi_delivered_pct": float(av.loc["meta_capi", "pct_events_delivered"])}
    md = csv("meta_daily_vs_outage").set_index("date")
    k["server"]["meta_day_dev_pct"] = round(100 * md.loc["2026-11-05", "deviation"], 1)
    k["server"]["meta_noise_range_pct"] = [round(100 * md.deviation.drop("2026-11-05").min(), 1), round(100 * md.deviation.drop("2026-11-05").max(), 1)]
    fq = csv("feed_validation_summary").set_index("market")
    k["feed"] = {"pl_pct": float(fq.loc["PL", "pct_at_risk"]), "uk_pct": float(fq.loc["UK", "pct_at_risk"]),
                 "wrong_currency": int(fq.wrong_currency.sum()), "missing_availability": int(fq.missing_required.sum())}
    mon = csv("monitoring_report")
    k["monitoring"] = {"checks": int(len(mon)), "fail": int((mon.status == "FAIL").sum()), "warn": int((mon.status == "WARN").sum())}
    ds = OUT / "detection_summary.csv"
    if ds.exists():
        d = pd.read_csv(ds)
        k["monitoring"]["found"] = int(d.found.sum())
    import pyarrow.parquet as pq
    sim = {t: pq.ParquetFile(ROOT / "data" / "sim" / f"{t}.parquet").metadata.num_rows
           for t in ("ga4_events", "orders_backend", "server_events", "pixel_events")}
    k["sim_rows"] = sim
    gvl = json.loads((ROOT / "data" / "reference" / "iab_gvl_summary.json").read_text(encoding="utf-8"))
    k["iab"] = {"version": gvl["vendorListVersion"], "updated": gvl["lastUpdated"][:10], "vendors": gvl["vendors"], "purposes": gvl["purposes"]}
    return k


if __name__ == "__main__":
    k = build()
    (OUT / "key_numbers.json").write_text(json.dumps(k, indent=1), encoding="utf-8")
    print(json.dumps({s: k[s] for s in ("recon", "consent", "utm", "dedup", "server", "feed")}, separators=(",", ":")))
