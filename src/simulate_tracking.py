"""Simulate 12 weeks of tracking data for a fictional client, "Client M" (SIMULATED).

Client M is a fictional multinational e-commerce brand present on 8 markets. Nothing here describes a real
company or any real client of SouthWatts. Seed 42: every run gives the same tables.

Period: 2026-09-01 -> 2026-11-23 (84 days). Sessions are drawn per market and day, with an hourly profile,
public holidays (date.nager.at, data/reference/holidays_2026.csv) and a weekday pattern.

Tables written to data/sim/*.parquet:
  ga4_events            reduced GA4 export schema (session_start, add_to_cart, begin_checkout, purchase)
  server_events         server-side container deliveries (ga4, meta_capi, google_ads, linkedin_capi)
  pixel_events          browser-side tags (meta_pixel, google_ads_tag, linkedin_insight)
  platform_conversions  what each ad platform reports (google_ads, meta, linkedin, cm360)
  orders_backend        the truth: every order, with the channel the order system recorded
  utm_catalogue         campaign links deposited by the 3 media agencies
  product_feed          product feed sent to the ad platforms (one row per SKU x market)
  deploy_log            container / site / feed releases
and data/_hidden_truth.csv (the 8 planted events; local only, never published).

Calibration (orders of magnitude, see docs/assumptions.md): purchase rate per session and share of
purchases without a usable transaction id are close to the public GA4 sample; attribution windows and
models are documented hypotheses, not platform defaults read from documentation.

    python src/simulate_tracking.py
"""
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SIM = ROOT / "data" / "sim"
REF = ROOT / "data" / "reference"
SEED = 42
rng = np.random.default_rng(SEED)

START, END = pd.Timestamp("2026-09-01"), pd.Timestamp("2026-11-23")
DAYS = pd.date_range(START, END, freq="D")
SHOP = "shop.clientm.example"
PSP = "pay.psp-example.com"

# market: base sessions/day, currency, fx vs EUR, consent acceptance, purchase-rate factor, LinkedIn active
MARKETS = {
    "FR": (900, "EUR", 1.00, 0.68, 1.00, True),
    "DE": (850, "EUR", 1.00, 0.62, 1.05, True),
    "ES": (560, "EUR", 1.00, 0.75, 0.95, False),
    "IT": (560, "EUR", 1.00, 0.72, 0.95, False),
    "UK": (760, "GBP", 0.86, 0.78, 1.05, True),
    "NL": (380, "EUR", 1.00, 0.70, 1.00, True),
    "PL": (330, "PLN", 4.30, 0.80, 0.90, False),
    "US": (650, "USD", 1.08, 0.95, 1.10, True),
}
SCALE = 10    # sessions multiplier (Client M is a multinational: ~48k sessions per day over 8 markets)
DOW = np.array([1.00, 1.02, 1.00, 0.98, 0.95, 0.85, 0.90])
HOURLY = np.array([1, .6, .4, .3, .3, .5, 1, 2, 3.5, 4.5, 5, 5.2, 5.5, 5.3, 5, 5, 5.2, 5.6, 6, 6.5, 6.8, 6, 4, 2])
HOURLY = HOURLY / HOURLY.sum()

CHANNELS = ["organic", "direct", "paid_search", "shopping", "paid_social", "linkedin", "display", "email", "referral"]
MIX = np.array([0.27, 0.20, 0.14, 0.05, 0.13, 0.03, 0.05, 0.07, 0.06])
CAL = 0.72   # scales purchase rates so Client M buys ~1.24 times per 100 sessions, like the public GA4 sample
P_BUY = dict(organic=.016, direct=.020, paid_search=.022, shopping=.025, paid_social=.014,
             linkedin=.006, display=.004, email=.030, referral=.012)
PLATFORM_OF = {"paid_search": "google_ads", "shopping": "google_ads", "paid_social": "meta",
               "linkedin": "linkedin", "display": "cm360"}
AGENCY_OF = {"google_ads": "AGY1", "meta": "AGY2", "linkedin": "AGY2", "cm360": "AGY3"}
CONVENTION = {"google_ads": ("google", "cpc"), "meta": ("meta", "paid_social"),
              "linkedin": ("linkedin", "paid_social"), "cm360": ("cm360", "display")}

# planted events (dates are local market dates)
D = pd.Timestamp
DE_V41, DE_V42, DE_V43 = D("2026-10-14"), D("2026-10-28"), D("2026-11-18")
META_BUG = D("2026-10-07")
UK_PSP = D("2026-10-28")
FEED_BUG = D("2026-10-16")
OUTAGE_START, OUTAGE_END = D("2026-11-05 02:00"), D("2026-11-05 09:00")   # UTC


def utc_offset(market: str, day: pd.Timestamp) -> int:
    if market == "US":
        return -4 if day < D("2026-11-01") else -5
    summer = day < D("2026-10-25")
    return (1 if summer else 0) if market == "UK" else (2 if summer else 1)


def h(prefix: str, values) -> list[str]:
    """Pseudonymous id: truncated SHA-256 (synthetic inputs only)."""
    return [hashlib.sha256(f"{prefix}{v}".encode()).hexdigest()[:20] for v in values]


def hex_ids(n: int, prefix: str) -> np.ndarray:
    return np.array([f"{prefix}{x:016x}" for x in rng.integers(0, 2**63, n)])


def build_campaigns() -> pd.DataFrame:
    rows, k = [], 1
    for m, cfg in MARKETS.items():
        types = [("google_ads", "search"), ("google_ads", "shopping"), ("meta", "prospecting"),
                 ("meta", "retargeting"), ("cm360", "display")]
        if cfg[5]:
            types.append(("linkedin", "awareness"))
        for platform, ctype in types:
            rows.append({"campaign_id": f"CMP{k:03d}", "market": m, "platform": platform, "campaign_type": ctype,
                         "agency": AGENCY_OF[platform], "campaign_name": f"{m.lower()}_{ctype}_2026q4"})
            k += 1
    return pd.DataFrame(rows)


def build_utm_catalogue(camps: pd.DataFrame) -> pd.DataFrame:
    rows, k = [], 1
    for c in camps.itertuples():
        for i in range(int(rng.integers(4, 9))):
            src, med = CONVENTION[c.platform]
            rows.append({"link_id": f"LNK{k:04d}", "agency": c.agency, "campaign_id": c.campaign_id,
                         "market": c.market, "platform": c.platform, "utm_source": src, "utm_medium": med,
                         "utm_campaign": c.campaign_name,
                         "created_date": (START - pd.Timedelta(days=int(rng.integers(1, 15)))).date()})
            k += 1
    u = pd.DataFrame(rows)
    # event 3: AGY2 writes the Meta source/medium in many spellings (45% of its Meta links)
    meta_idx = u.index[u.platform.eq("meta")].to_numpy()
    bad = rng.choice(meta_idx, size=round(0.45 * len(meta_idx)), replace=False)
    u.loc[bad, "utm_source"] = rng.choice(["Facebook", "facebook", "fb"], len(bad))
    u.loc[bad, "utm_medium"] = rng.choice(["paid_social", "Paid_Social", "social", "cpc"], len(bad))
    upper = rng.choice(bad, size=len(bad) // 3, replace=False)
    u.loc[upper, "utm_campaign"] = u.loc[upper, "utm_campaign"].str.replace("_", " ").str.upper()
    # event 3: 12% of all links have no utm_medium
    miss = rng.choice(u.index.to_numpy(), size=round(0.12 * len(u)), replace=False)
    u.loc[miss, "utm_medium"] = ""

    def url(r):
        q = [f"utm_source={r.utm_source}"] + ([f"utm_medium={r.utm_medium}"] if r.utm_medium else []) \
            + [f"utm_campaign={r.utm_campaign.replace(' ', '%20')}"]
        return f"https://{SHOP}/{r.market.lower()}/?" + "&".join(q)
    u["url"] = [url(r) for r in u.itertuples()]
    return u


def build_sessions(camps: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    hol = pd.read_csv(REF / "holidays_2026.csv", parse_dates=["date"])
    hol_set = set(zip(hol.market, hol.date))
    parts = []
    for m, (base, cur, fx, consent, buyf, li) in MARKETS.items():
        mix = MIX.copy()
        if not li:                                    # no LinkedIn campaigns: its share goes to Meta
            mix[4] += mix[5]
            mix[5] = 0
        for d in DAYS:
            lam = SCALE * base * DOW[d.dayofweek] * (0.8 if (m, d) in hol_set else 1.0) * (1 + 0.0005 * (d - START).days)
            n = rng.poisson(lam)
            ch = rng.choice(CHANNELS, n, p=mix)
            if m in ("PL", "UK") and d >= FEED_BUG:   # event 7: disapproved products -> fewer Shopping clicks
                keep = ~((ch == "shopping") & (rng.random(n) < 0.12))
                ch = ch[keep]
                n = len(ch)
            hour = rng.choice(24, n, p=HOURLY)
            sec = rng.integers(0, 3600, n)
            ts_local = d + pd.to_timedelta(hour * 3600 + sec, unit="s")
            parts.append(pd.DataFrame({"market": m, "date": d, "channel": ch,
                                       "ts": ts_local - pd.Timedelta(hours=utc_offset(m, d)),
                                       "granted": rng.random(n) < consent,
                                       "p": [P_BUY[c] * buyf * CAL for c in ch]}))
    s = pd.concat(parts, ignore_index=True)
    n = len(s)
    s["sid"] = np.arange(n)
    s["purchase"] = rng.random(n) < s.p
    s["atc"] = s.purchase | (rng.random(n) < s.p * 4.5)
    s["checkout"] = s.purchase | (s.atc & (rng.random(n) < 0.35))
    # campaign and link for paid sessions
    s["campaign_id"], s["link_id"] = None, None
    ctype = {"paid_search": "search", "shopping": "shopping", "display": "display", "linkedin": "awareness"}
    for (m, ch), idx in s[s.channel.isin(PLATFORM_OF)].groupby(["market", "channel"]).groups.items():
        if ch == "paid_social":
            pool = camps[(camps.market == m) & (camps.platform == "meta")].campaign_id.to_numpy()
        else:
            pool = camps[(camps.market == m) & (camps.campaign_type == ctype[ch])].campaign_id.to_numpy()
        cid = rng.choice(pool, len(idx))
        s.loc[idx, "campaign_id"] = cid
        by_c = links.groupby("campaign_id").link_id.apply(np.array).to_dict()
        s.loc[idx, "link_id"] = [rng.choice(by_c[c]) for c in cid]
    # users: a pool per market, so some users come back
    s["user_idx"] = 0
    for m, idx in s.groupby("market").groups.items():
        s.loc[idx, "user_idx"] = rng.integers(0, int(len(idx) * 0.75), len(idx))
    s["user_pseudo_id"] = h("u", s.market + s.user_idx.astype(str))
    s["value"] = 0.0
    fx = s.market.map({m: v[2] for m, v in MARKETS.items()})
    s.loc[s.purchase, "value"] = np.round(rng.lognormal(np.log(70), 0.55, s.purchase.sum()) * fx[s.purchase], 2)
    s["currency"] = s.market.map({m: v[1] for m, v in MARKETS.items()})
    return s.drop(columns="p")


def source_medium(s: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame:
    src = np.select([s.channel.eq("organic"), s.channel.eq("direct"), s.channel.eq("email"), s.channel.eq("referral")],
                    ["google", "(direct)", "newsletter", "partner-blog.example"], default="")
    med = np.select([s.channel.eq("organic"), s.channel.eq("direct"), s.channel.eq("email"), s.channel.eq("referral")],
                    ["organic", "(none)", "email", "referral"], default="")
    out = pd.DataFrame({"source": src, "medium": med, "campaign": "(not set)"}, index=s.index)
    out.loc[s.channel.eq("email"), "campaign"] = "newsletter_weekly"
    paid = s.link_id.notna()
    lk = links.set_index("link_id").loc[s.loc[paid, "link_id"]]
    out.loc[paid, "source"] = lk.utm_source.to_numpy()
    out.loc[paid, "medium"] = lk.utm_medium.replace("", "(not set)").to_numpy()
    out.loc[paid, "campaign"] = lk.utm_campaign.to_numpy()
    google = s.channel.isin(["paid_search", "shopping"])      # auto-tagging (gclid) wins over UTM in GA4
    out.loc[google, ["source", "medium"]] = ["google", "cpc"]
    return out


def main() -> None:
    SIM.mkdir(parents=True, exist_ok=True)
    camps = build_campaigns()
    links = build_utm_catalogue(camps)
    s = build_sessions(camps, links)
    sm = source_medium(s, links)
    s = s.join(sm)
    n = len(s)
    s["ga_session_id"] = (s.ts.astype("int64") // 10**9).astype(str)
    s["local_date"] = s.date.dt.date

    # ---------- GA4 recording (consent + event 1) ----------
    de = s.market.eq("DE")
    v41 = de & (s.date >= DE_V41) & (s.date < DE_V42)
    v42 = de & (s.date >= DE_V42) & (s.date < DE_V43)
    leaked = v41 & ~s.granted & (rng.random(n) < 0.29)            # hits sent before the consent choice
    recorded = (s.granted & ~(v42 & (rng.random(n) > 0.65))) | leaked
    s["consent_state"] = np.where(leaked, "pre_choice", np.where(s.granted, "granted", "denied"))

    # event ids pushed to the dataLayer (shared by pixel and server tags when the setup is right)
    for e in ("atc", "checkout", "purchase"):
        s[f"eid_{e}"] = hex_ids(n, "evt_")
    s["ts_atc"] = s.ts + pd.to_timedelta(rng.integers(60, 600, n), unit="s")
    s["ts_checkout"] = s.ts_atc + pd.to_timedelta(rng.integers(60, 600, n), unit="s")
    s["ts_purchase"] = s.ts_checkout + pd.to_timedelta(rng.integers(60, 600, n), unit="s")

    # orders (truth)
    o = s[s.purchase].copy()
    o["order_id"] = ["CM" + m + f"{i:07d}" for m, i in zip(o.market, range(1, len(o) + 1))]
    s.loc[o.index, "order_id"] = o.order_id
    orders = pd.DataFrame({"order_id": o.order_id, "ts": o.ts_purchase, "order_date": o.local_date,
                           "market": o.market, "value": o.value, "currency": o.currency,
                           "channel_claimed": o.channel, "campaign_id": o.campaign_id,
                           "consent_state": np.where(o.granted, "granted", "denied")})

    # ---------- GA4 events ----------
    def ga4_rows(mask, name, ts_col, with_tx=False):
        x = s[mask]
        df = pd.DataFrame({"event_date": x.local_date, "event_ts": x[ts_col], "event_name": name,
                           "user_pseudo_id": x.user_pseudo_id, "ga_session_id": x.ga_session_id,
                           "source": x.source, "medium": x.medium, "campaign": x.campaign,
                           "transaction_id": x.order_id if with_tx else None,
                           "value": x.value if with_tx else np.nan, "currency": x.currency if with_tx else None,
                           "market": x.market, "consent_state": x.consent_state})
        return df
    full = recorded & ~leaked
    ev = [ga4_rows(recorded, "session_start", "ts"), ga4_rows(full & s.atc, "add_to_cart", "ts_atc"),
          ga4_rows(full & s.checkout, "begin_checkout", "ts_checkout")]
    buy = full & s.purchase
    # event 5: UK, a payment provider without cross-domain linking -> purchase lands in a new session
    psp = buy & s.market.eq("UK") & (s.date >= UK_PSP) & (rng.random(n) < 0.70)
    p_normal = ga4_rows(buy & ~psp, "purchase", "ts_purchase", True)
    p_psp = ga4_rows(psp, "purchase", "ts_purchase", True)
    self_ref = rng.random(len(p_psp)) < 0.40
    p_psp["source"] = np.where(self_ref, SHOP, PSP)
    p_psp["medium"], p_psp["campaign"] = "referral", "(referral)"
    p_psp["ga_session_id"] = (p_psp.event_ts.astype("int64") // 10**9 - 30).astype(str)
    p_psp_start = p_psp.assign(event_name="session_start", transaction_id=None, value=np.nan, currency=None,
                               event_ts=p_psp.event_ts - pd.Timedelta(seconds=30))
    # event 4: Italy, the confirmation page is reloaded -> same transaction_id sent twice
    p_all = pd.concat([p_normal, p_psp], ignore_index=True)
    dup = p_all[p_all.market.eq("IT") & (rng.random(len(p_all)) < 0.06)].copy()
    dup["event_ts"] = dup.event_ts + pd.to_timedelta(rng.integers(20, 600, len(dup)), unit="s")
    ga4 = pd.concat(ev + [p_all, p_psp_start, dup], ignore_index=True).sort_values("event_ts", ignore_index=True)

    # ---------- browser pixels and server container ----------
    g = s[s.granted]
    blocked = rng.random(len(g)) < 0.12                      # ad blockers / browser restrictions
    meta_names = {"atc": "AddToCart", "checkout": "InitiateCheckout", "purchase": "Purchase"}
    li_mk = [m for m, v in MARKETS.items() if v[5]]
    pix, srv = [], []
    for e, mname in meta_names.items():
        x = g[g[e]]
        xb = ~blocked[g[e].to_numpy()]
        pix.append(pd.DataFrame({"event_id": x[f"eid_{e}"], "event_name": mname, "ts": x[f"ts_{e}"],
                                 "destination": "meta_pixel", "market": x.market, "order_id": x.order_id})[xb])
        ga4name = {"atc": "add_to_cart", "checkout": "begin_checkout", "purchase": "purchase"}[e]
        srv.append(pd.DataFrame({"event_id": x[f"eid_{e}"], "event_name": ga4name, "ts": x[f"ts_{e}"],
                                 "destination": "ga4", "market": x.market, "order_id": x.order_id}))
        capi = pd.DataFrame({"event_id": x[f"eid_{e}"], "event_name": mname, "ts": x[f"ts_{e}"],
                             "destination": "meta_capi", "market": x.market, "order_id": x.order_id})
        if e == "purchase":   # event 2: v40 gives the server Purchase a new event_id on FR and ES
            bug = x.market.isin(["FR", "ES"]).to_numpy() & (x.date >= META_BUG).to_numpy()
            capi.loc[bug, "event_id"] = hex_ids(int(bug.sum()), "srv_")
        srv.append(capi)
        if e == "purchase":
            pix.append(pd.DataFrame({"event_id": x.eid_purchase, "event_name": "purchase", "ts": x.ts_purchase,
                                     "destination": "google_ads_tag", "market": x.market, "order_id": x.order_id})[xb])
            srv.append(pd.DataFrame({"event_id": x.eid_purchase, "event_name": "purchase", "ts": x.ts_purchase,
                                     "destination": "google_ads", "market": x.market, "order_id": x.order_id}))
            xl = x[x.market.isin(li_mk)]
            xlb = xb[x.market.isin(li_mk).to_numpy()]
            pix.append(pd.DataFrame({"event_id": xl.eid_purchase, "event_name": "purchase", "ts": xl.ts_purchase,
                                     "destination": "linkedin_insight", "market": xl.market, "order_id": xl.order_id})[xlb])
            srv.append(pd.DataFrame({"event_id": xl.eid_purchase, "event_name": "purchase", "ts": xl.ts_purchase,
                                     "destination": "linkedin_capi", "market": xl.market, "order_id": xl.order_id}))
    pixel = pd.concat(pix, ignore_index=True)
    server = pd.concat(srv, ignore_index=True)
    base_err = server.destination.map({"ga4": .004, "meta_capi": .006, "google_ads": .005, "linkedin_capi": .010})
    err = rng.random(len(server)) < base_err
    outage = server.destination.eq("meta_capi") & (server.ts >= OUTAGE_START) & (server.ts < OUTAGE_END)  # event 8
    err = err | outage
    server["status"] = np.where(outage, "error_503", np.where(err, "error_timeout", "ok"))
    server["latency_ms"] = np.where(err, np.where(outage, rng.integers(5, 40, len(server)), 5000),
                                    np.round(rng.lognormal(np.log(120), 0.35, len(server)))).astype(int)
    server = server.sort_values("ts", ignore_index=True)
    pixel = pixel.sort_values("ts", ignore_index=True)

    # ---------- platform conversions ----------
    od = orders.merge(s[["order_id", "date", "granted"]], on="order_id")
    pc = []
    # Google Ads: data-driven credit, 30-day click window, reported on click date (hypotheses)
    ga = od[od.channel_claimed.isin(["paid_search", "shopping"]) & od.granted].copy()
    ga["credit"] = 1.22 * rng.normal(1, 0.08, len(ga))
    lag = rng.choice([0, 1, 2, 3, 5, 7, 10, 14, 21], len(ga), p=[.55, .15, .08, .06, .05, .04, .03, .02, .02])
    ga["day"] = ga.date - pd.to_timedelta(lag, unit="D")
    ga["cv"] = ga.value * ga.credit
    a = ga.groupby(["day", "campaign_id", "market"], as_index=False).agg(conversions=("credit", "sum"),
                                                                         conversion_value=("cv", "sum"))
    pc.append(a.assign(platform="google_ads", attribution_window="30d_click", model="data_driven"))
    # Meta: unique event_ids received per attributed order (pixel and CAPI, deduplicated on event_id)
    got = pd.concat([pixel[pixel.destination.eq("meta_pixel") & pixel.event_name.eq("Purchase")][["order_id", "event_id"]],
                     server[server.destination.eq("meta_capi") & server.event_name.eq("Purchase") & server.status.eq("ok")]
                     [["order_id", "event_id"]]])
    nid = got.groupby("order_id").event_id.nunique()
    meta_c = camps[camps.platform.eq("meta")]
    att = od[od.granted & od.channel_claimed.eq("paid_social")].copy()
    vt = od[od.granted & ~od.channel_claimed.eq("paid_social") & (rng.random(len(od)) < 0.02)].copy()   # view-through
    vt["campaign_id"] = [rng.choice(meta_c[meta_c.market.eq(m)].campaign_id.to_numpy()) for m in vt.market]
    att = pd.concat([att, vt])
    att["n"] = att.order_id.map(nid).fillna(0)
    att["cv"] = att.value * att.n
    a = att.groupby(["date", "campaign_id", "market"], as_index=False).agg(conversions=("n", "sum"), conversion_value=("cv", "sum"))
    pc.append(a.rename(columns={"date": "day"}).assign(platform="meta", attribution_window="7d_click_1d_view", model="meta_default"))
    # LinkedIn: 30-day click / 7-day view, more credit than last click (hypothesis)
    li = od[od.granted & od.channel_claimed.eq("linkedin")].groupby(["date", "campaign_id", "market"], as_index=False) \
        .agg(n=("order_id", "size"), v=("value", "mean"))
    li["conversions"] = rng.poisson(1.3 * li.n)
    li["conversion_value"] = li.conversions * li.v
    pc.append(li.rename(columns={"date": "day"}).drop(columns=["n", "v"]).assign(
        platform="linkedin", attribution_window="30d_click_7d_view", model="last_touch"))
    # CM360: post-view conversions dominate (hypothesis)
    disp = camps[camps.platform.eq("cm360")].set_index("market").campaign_id
    cm = od[od.granted].groupby(["date", "market"], as_index=False).agg(n=("order_id", "size"), v=("value", "mean"))
    dc = od[od.granted & od.channel_claimed.eq("display")].groupby(["date", "market"]).size()
    cm["conversions"] = rng.poisson(0.05 * cm.n) + cm.set_index(["date", "market"]).index.map(dc).fillna(0).astype(int)
    cm["conversion_value"] = cm.conversions * cm.v
    cm["campaign_id"] = cm.market.map(disp)
    pc.append(cm.rename(columns={"date": "day"}).drop(columns=["n", "v"]).assign(
        platform="cm360", attribution_window="30d_click_30d_view", model="last_interaction"))
    plat = pd.concat(pc, ignore_index=True)
    plat = plat[(plat.day >= START) & (plat.day <= END)]
    plat["date"] = plat.day.dt.date
    plat["currency"] = plat.market.map({m: v[1] for m, v in MARKETS.items()})
    plat["conversions"] = plat.conversions.round(2)
    plat["conversion_value"] = plat.conversion_value.round(2)
    plat = plat[["date", "platform", "campaign_id", "market", "conversions", "conversion_value", "currency",
                 "attribution_window", "model"]].sort_values(["date", "platform", "campaign_id"], ignore_index=True)

    # ---------- product feed (event 7) ----------
    skus = [f"SKU{i:04d}" for i in range(1, 301)]
    cats = rng.choice(["Lamp", "Chair", "Desk", "Shelf", "Rug", "Mirror", "Clock", "Vase"], len(skus))
    base_price = np.round(rng.lognormal(np.log(60), 0.6, len(skus)), 2)
    gtin12 = rng.integers(10**11, 10**12, len(skus))

    def gtin13(x):
        d = [int(c) for c in f"{x:012d}"]
        chk = (10 - sum(v * (3 if i % 2 else 1) for i, v in enumerate(d)) % 10) % 10
        return f"{x:012d}{chk}"
    gt = [gtin13(x) for x in gtin12]
    feed = []
    for m, v in MARKETS.items():
        f = pd.DataFrame({"sku": skus, "market": m, "title": [f"{c} {s[-4:]} - Client M" for c, s in zip(cats, skus)],
                          "price": np.round(base_price * v[2], 2), "currency": v[1],
                          "availability": rng.choice(["in_stock", "out_of_stock", "preorder", "backorder"], len(skus),
                                                     p=[.85, .10, .03, .02]),
                          "link": [f"https://{SHOP}/{m.lower()}/p/{s.lower()}" for s in skus],
                          "image_link": [f"https://img.clientm.example/{s.lower()}.jpg" for s in skus], "gtin": gt})
        if m in ("PL", "UK"):
            wrong = rng.choice(len(f), round(0.07 * len(f)), replace=False)
            f.loc[wrong, "currency"] = "EUR"
            free = np.setdiff1d(np.arange(len(f)), wrong)
            f.loc[rng.choice(free, round(0.03 * len(f)), replace=False), "availability"] = None
        feed.append(f)
    feed = pd.concat(feed, ignore_index=True)

    deploy = pd.DataFrame([
        ("web-v38", "2026-08-28", "web", "ALL", "Baseline container: GA4, Google Ads, Meta pixel, LinkedIn Insight, Consent Mode"),
        ("server-v11", "2026-08-28", "server", "ALL", "Server container: GA4, Meta CAPI, Google Ads, LinkedIn CAPI clients and tags"),
        ("web-v39", "2026-09-22", "web", "ALL", "Add begin_checkout to Meta (InitiateCheckout) and LinkedIn"),
        ("web-v40", "2026-10-07", "web", "FR,ES", "Move Meta Purchase to the server container (new CAPI tag)"),
        ("web-v41", "2026-10-14", "web", "DE", "New consent banner template"),
        ("feed-2026-10-16", "2026-10-16", "feed", "PL,UK", "New PIM export for the product feed"),
        ("site-2026-10-28", "2026-10-28", "site", "UK", "New payment provider (redirect checkout)"),
        ("web-v42", "2026-10-28", "web", "DE", "Consent hotfix: block all Google tags until consent update"),
        ("server-v12", "2026-11-04", "server", "ALL", "Autoscaling settings changed on the server container"),
        ("web-v43", "2026-11-18", "web", "DE", "Consent fix: default denied, update on choice"),
    ], columns=["version", "date", "container", "market_scope", "change"])

    truth = pd.DataFrame([
        (1, "consent_mode_misdeployed", "DE", "2026-10-14", "2026-11-17", True, "consent_state + deploy_log (web-v41, web-v42)"),
        (2, "meta_double_counting", "FR,ES", "2026-10-07", "2026-11-23", True, "pixel vs CAPI event_id match rate"),
        (3, "utm_non_compliance", "ALL", "2026-09-01", "2026-11-23", True, "UTM validator + Unassigned share"),
        (4, "duplicate_purchases", "IT", "2026-09-01", "2026-11-23", True, "duplicate transaction_id rate"),
        (5, "cross_domain_broken", "UK", "2026-10-28", "2026-11-23", True, "PSP referral / self-referral share of purchases"),
        (6, "google_ads_vs_ga4_gap", "ALL", "2026-09-01", "2026-11-23", False, "NOT a bug: attribution model, window, click date"),
        (7, "feed_currency_availability", "PL,UK", "2026-10-16", "2026-11-23", True, "feed validator (Merchant Center spec)"),
        (8, "server_container_outage", "ALL", "2026-11-05", "2026-11-05", True, "hourly server error rate (meta_capi)"),
    ], columns=["event", "name", "markets", "start", "end", "is_bug", "detected_by"])

    for name, df in {"ga4_events": ga4, "server_events": server, "pixel_events": pixel,
                     "platform_conversions": plat, "orders_backend": orders, "utm_catalogue": links,
                     "product_feed": feed, "deploy_log": deploy, "campaigns": camps}.items():
        df.to_parquet(SIM / f"{name}.parquet", index=False)
    truth.to_csv(ROOT / "data" / "_hidden_truth.csv", index=False)

    paid = s[s.channel.isin(PLATFORM_OF) & recorded]
    unassigned = ~(paid.source + "/" + paid.medium).isin(["google/cpc", "meta/paid_social", "linkedin/paid_social", "cm360/display"])
    print(f"sessions {n:,} | GA4 rows {len(ga4):,} | orders {len(orders):,} | server {len(server):,} | pixel {len(pixel):,}")
    print(f"paid sessions Unassigned share: {unassigned.mean():.1%} | links missing medium: {(links.utm_medium == '').mean():.1%}")


if __name__ == "__main__":
    main()
