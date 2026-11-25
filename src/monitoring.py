"""Daily and hourly tracking monitoring for the fictional Client M (SIMULATED).

Each check gives PASS, WARN or FAIL against documented thresholds (docs/monitoring_runbook.md).
Inputs: the simulated tables (data/sim) and the SQL outputs (data/out, from src/run_sql.py).

  check                     grain                  WARN            FAIL
  sessions_vs_baseline      day x market           |dev| > 12%     |dev| > 25%      (holidays: PASS, noted)
  pre_consent_hits          day x market           -               share > 0%       (hits before the consent choice)
  ga4_duplicate_purchases   day x market           > 1%            > 3%             (same transaction_id twice)
  meta_event_id_match       day x market           < 98%           < 90%            (pixel vs CAPI, same order)
  purchase_self_referral    day x market           > 2%            > 5%             (own domain / payment provider)
  paid_unassigned_share     week x market          > 5%            > 10%
  platform_reconciliation   week x market x platf  -               category anomalous (expected gaps: PASS)
  server_error_rate         hour x destination     > 5%            > 20%            (only hours with >= 10 events)
  feed_quality              market (snapshot)      -               any disapproval-risk issue

    python src/monitoring.py
Outputs: data/out/monitoring_report.csv, data/out/monitoring_status.csv (latest status per check and market) and,
when the local answer key data/_hidden_truth.csv exists, data/out/detection_summary.csv.
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM, OUT = ROOT / "data" / "sim", ROOT / "data" / "out"


def status(value, warn, fail, higher_is_bad=True):
    v = np.asarray(value, dtype=float)
    if higher_is_bad:
        return np.where(v > fail, "FAIL", np.where(v > warn, "WARN", "PASS"))
    return np.where(v < fail, "FAIL", np.where(v < warn, "WARN", "PASS"))


def rows(df, check, grain, value_col, warn, fail, higher_is_bad=True, note=""):
    out = pd.DataFrame({"check": check, "grain": grain, "period": df["period"].astype(str), "scope": df["scope"],
                        "value": df[value_col].round(4), "warn_threshold": warn, "fail_threshold": fail})
    out["status"] = status(df[value_col].fillna(0), warn if warn is not None else fail, fail, higher_is_bad)
    out["note"] = note
    return out


def main() -> None:
    con = duckdb.connect()
    for f in SIM.glob("*.parquet"):
        con.execute(f"CREATE VIEW {f.stem} AS SELECT * FROM read_parquet('{f.as_posix()}')")
    parts = []

    c = pd.read_csv(OUT / "consent_daily.csv")
    c["period"], c["scope"], c["absdev"] = c.date, c.market, c.deviation.abs()
    r = rows(c, "sessions_vs_baseline", "day", "absdev", 0.12, 0.25)
    r.loc[c.holiday.to_numpy(), ["status", "note"]] = ["PASS", "public holiday"]
    parts.append(r)
    parts.append(rows(c, "pre_consent_hits", "day", "pre_choice_share", 0.0, 0.0))

    d = pd.read_csv(OUT / "dedup_ga4_daily.csv").rename(columns={"date": "period", "market": "scope"})
    parts.append(rows(d, "ga4_duplicate_purchases", "day", "duplicate_rate", 0.01, 0.03))

    m = pd.read_csv(OUT / "dedup_meta_daily.csv").rename(columns={"date": "period", "market": "scope"})
    parts.append(rows(m, "meta_event_id_match", "day", "event_id_match_rate", 0.98, 0.90, higher_is_bad=False))

    s = con.execute("""
        SELECT event_date AS period, market AS scope,
               AVG(CASE WHEN source LIKE '%clientm.example' OR source LIKE 'pay.%' THEN 1.0 ELSE 0.0 END) AS share
        FROM ga4_events WHERE event_name = 'purchase' GROUP BY ALL ORDER BY 1, 2""").df()
    parts.append(rows(s, "purchase_self_referral", "day", "share", 0.02, 0.05))

    u = pd.read_csv(OUT / "utm_unassigned_weekly.csv")
    u["period"], u["scope"], u["share"] = u.week, u.market, u.pct_unassigned / 100
    parts.append(rows(u, "paid_unassigned_share", "week", "share", 0.05, 0.10))

    rec = pd.read_csv(OUT / "reconciliation_weekly.csv")
    rr = pd.DataFrame({"check": "platform_reconciliation", "grain": "week", "period": rec.week.astype(str),
                       "scope": rec.market + " / " + rec.platform, "value": rec.ratio, "warn_threshold": np.nan,
                       "fail_threshold": np.nan, "status": np.where(rec.category == "anomalous", "FAIL", "PASS"),
                       "note": rec.explanation})
    parts.append(rr)

    h = pd.read_csv(OUT / "server_hourly.csv")
    h = h[h.events >= 10].rename(columns={"hour_utc": "period", "destination": "scope"})
    parts.append(rows(h, "server_error_rate", "hour", "error_rate", 0.05, 0.20))

    fq = pd.read_csv(OUT / "feed_validation_summary.csv")
    fq["period"], fq["scope"], fq["share"] = "2026-11-23", fq.market, fq.pct_at_risk / 100
    parts.append(rows(fq, "feed_quality", "snapshot", "share", 0.0, 0.0))

    rep = pd.concat(parts, ignore_index=True)
    rep.to_csv(OUT / "monitoring_report.csv", index=False)
    latest = rep.sort_values("period").groupby(["check", "scope"]).tail(1)
    latest.to_csv(OUT / "monitoring_status.csv", index=False)
    counts = rep.status.value_counts().to_dict()
    print(f"monitoring: {len(rep):,} checks | {counts}")

    truth_path = ROOT / "data" / "_hidden_truth.csv"
    if truth_path.exists():
        detect(rep, pd.read_csv(truth_path))


# which check is expected to catch each planted event, and on which scope
CATCH = {1: (["pre_consent_hits", "sessions_vs_baseline"], ["DE"]), 2: ("meta_event_id_match", ["FR", "ES"]), 3: ("paid_unassigned_share", None),
         4: ("ga4_duplicate_purchases", ["IT"]), 5: ("purchase_self_referral", ["UK"]), 7: ("feed_quality", ["PL", "UK"]),
         8: ("server_error_rate", ["meta_capi"])}


def detect(rep: pd.DataFrame, truth: pd.DataFrame) -> None:
    res = []
    for t in truth.itertuples():
        if t.event == 6:   # must NOT be raised as a bug: no FAIL whose explanation is the attribution difference
            bad = rep[(rep.check == "platform_reconciliation") & (rep.status == "FAIL") & rep.note.str.startswith("attribution")]
            res.append({"event": 6, "name": t.name, "is_bug": False, "check": "platform_reconciliation",
                        "first_fail": "", "detection_delay": "", "found": bool(bad.empty),
                        "comment": "Google Ads > GA4 classified as expected (attribution model, window, click date)"})
            continue
        check, scopes = CATCH[t.event]
        checks = check if isinstance(check, list) else [check]
        check = " + ".join(checks)
        f = rep[rep.check.isin(checks) & (rep.status == "FAIL")]
        if scopes:
            f = f[f.scope.isin(scopes)]
        first = f.period.min() if len(f) else None
        delay = ""
        if first and t.event not in (3, 7):
            start = pd.Timestamp("2026-11-05 02:00") if t.event == 8 else pd.Timestamp(t.start)
            raised = pd.Timestamp(first) + (pd.Timedelta(hours=1) if t.event == 8 else pd.Timedelta(days=1))
            delay = str(raised - start)
        res.append({"event": t.event, "name": t.name, "is_bug": True, "check": check, "first_fail": first or "",
                    "detection_delay": delay, "found": first is not None,
                    "comment": "check runs at the end of the hour/day" if delay else "found by the first run (snapshot / catalogue check)"})
    out = pd.DataFrame(res)
    out.to_csv(OUT / "detection_summary.csv", index=False)
    print(f"planted events found: {int(out.found.sum())}/8")


if __name__ == "__main__":
    main()
