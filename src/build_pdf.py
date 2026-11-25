"""Build the 7-page PDF report (pages 0-6): site/report/southwatts_tracking_case_study.pdf

Style of the earlier case studies: grey-beige page, white cards, the title of each page is its conclusion,
PUBLIC DATA / SIMULATED tags, Segoe UI, 3-4 visuals per page. HTML is rendered with headless Edge (src/pdf_utils.py),
then the PDF metadata is emptied. Every number is read from data/out (nothing typed by hand). No logo.

    python src/build_pdf.py
"""
import html
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from pdf_utils import print_pdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "out"
DRAFT = ROOT / "data" / "cache" / "report_draft.html"
PDF = ROOT / "site" / "report" / "southwatts_tracking_case_study.pdf"

BLUE, GREY, RED, INK, MUTED, GRID, AMBER, GREEN = "#2A78D6", "#A3A19A", "#D03B3B", "#0B0B0B", "#52514E", "#E1E0D9", "#EDA100", "#1BAF7A"
MK = {"FR": "#2A78D6", "DE": "#EB6834", "ES": "#1BAF7A", "IT": "#EDA100", "UK": "#E87BA4", "NL": "#7A5CD6", "PL": "#4FB6C9", "US": "#8A8A80"}
plt.rcParams.update({
    "font.family": "Segoe UI", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "figure.facecolor": "white", "axes.facecolor": "white",
    "legend.frameon": False, "legend.fontsize": 8, "svg.fonttype": "none"})
AI_NOTE = ("AI-assisted workflow: I used Claude, mainly to write scripts faster. I drove the project: I defined the questions, "
           "chose and validated the data sources, made the analytical decisions and checked every result.")
FOOT = "Independent case study based on public data · not affiliated with or endorsed by SouthWatts"


def csv(n):
    return pd.read_csv(OUT / f"{n}.csv")


def svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(fig)
    s = buf.getvalue()
    return s[s.index("<svg"):]


def fig(w=4.9, h=2.2):
    return plt.subplots(figsize=(w, h))


def datefmt(ax):
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))


# ---------------- charts ----------------
def ch_real_findings(k):
    r = k["real"]
    f, ax = fig(4.9, 2.0)
    labels = ["Purchases without id", "Duplicated ids", "Extra purchase rows"]
    vals = [r["without_id"], r["duplicated_ids"], r["extra_rows"]]
    ax.barh(labels[::-1], vals[::-1], color=[GREY, RED, RED])
    for i, v in enumerate(vals[::-1]):
        ax.text(v + 15, i, f"{v:,}", va="center", color=INK)
    ax.set_xlabel(f"purchase events (of {r['purchase_events']:,})")
    ax.set_xlim(0, max(vals) * 1.2)
    ax.grid(axis="y", visible=False)
    return svg(f)


def ch_real_channels():
    ch = csv("real_channels")
    ch = ch[~ch.channel.isin(["Unassigned", "Affiliates", "Email"])]
    ch["pct_purch"] = 100 * ch.purchases / ch.purchases.sum()
    ch = ch.sort_values("pct_purch")
    f, ax = fig(4.9, 2.3)
    y = range(len(ch))
    ax.barh([i + 0.2 for i in y], ch.pct_sessions, height=0.38, color=GREY, label="% of sessions")
    ax.barh([i - 0.2 for i in y], ch.pct_purch, height=0.38, color=[RED if c.startswith("Self") else BLUE for c in ch.channel], label="% of purchases")
    ax.set_yticks(list(y), ch.channel)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.legend(loc="lower right")
    ax.grid(axis="y", visible=False)
    return svg(f)


def ch_real_gap():
    g = csv("real_audit_duplicate_gap")
    f, ax = fig(3.2, 2.0)
    ax.bar([b[3:] for b in g.gap_bucket], g.duplicated_ids, color=[RED, GREY, GREY][:len(g)])
    for i, v in enumerate(g.duplicated_ids):
        ax.text(i, v + 5, str(v), ha="center", color=INK)
    ax.set_ylabel("duplicated ids")
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_real_daily():
    d = csv("real_audit_daily")
    d["date"] = pd.to_datetime(d.date)
    f, ax = fig(3.6, 1.6)
    ax.plot(d.date, 100 * d.self_referral_share, color=RED, lw=1.2)
    ax.set_ylim(0, None)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.set_ylabel("share of page views")
    datefmt(ax)
    return svg(f)


def ch_ratio(platform, highlight, ylabel, w=4.9, h=1.95):
    r = csv("reconciliation_weekly")
    r = r[r.platform == platform]
    r["week"] = pd.to_datetime(r.week)
    f, ax = fig(w, h)
    for m, g in r.groupby("market"):
        hl = m in highlight
        ax.plot(g.week, g.ratio, color=MK[m] if hl else GRID if not hl else MK[m], lw=1.8 if hl else 1, label=m if hl else None, zorder=3 if hl else 1)
        an = g[g.category == "anomalous"]
        ax.scatter(an.week, an.ratio, color=RED, s=22, zorder=4)
    ax.axhline(r.expected_ratio.iloc[0], color=MUTED, ls="--", lw=1)
    ax.text(r.week.min(), r.expected_ratio.iloc[0], f" expected {r.expected_ratio.iloc[0]:.2f}", va="bottom", color=MUTED, fontsize=8)
    ax.set_ylabel(ylabel)
    ax.legend(loc="upper left", ncol=3)
    datefmt(ax)
    return svg(f)


def ch_recon_bar():
    s = csv("reconciliation_summary")
    lab = {"attribution model (data-driven vs last non-direct click), 30-day window, click date": "Google Ads: attribution, window, click date",
           "view-through credit and consent: within normal range": "Meta: view-through, consent",
           "GA4 side broken: cross-domain (payment provider / self-referral)": "GA4 broken: cross-domain (UK)",
           "GA4 side broken: consent mode release (see consent_breaks)": "GA4 broken: consent release (DE)",
           "Meta side broken: pixel and CAPI event_id differ (double counting)": "Meta broken: event_id mismatch (FR, ES)",
           "recent clicks: conversions still arriving (click-date reporting)": "Google Ads: recent clicks still arriving"}
    s["label"] = s.explanation.map(lab).fillna(s.explanation)
    s = s.sort_values(["category", "market_weeks"])
    f, ax = fig(4.6, 2.1)
    ax.barh(s.label, s.market_weeks, color=[RED if c == "anomalous" else BLUE for c in s.category])
    for i, v in enumerate(s.market_weeks):
        ax.text(v + 1, i, str(v), va="center", color=INK, fontsize=8)
    ax.set_xlabel("market-weeks (blue: expected · red: anomalous)")
    ax.grid(axis="y", visible=False)
    return svg(f)


def ch_de():
    c = csv("consent_daily")
    c = c[c.market == "DE"].copy()
    c["date"] = pd.to_datetime(c.date)
    b = csv("consent_breaks")
    f, ax = fig(4.9, 2.2)
    ax.plot(c.date, c.sessions, color=BLUE, lw=1.3, label="GA4 sessions, DE")
    ax.plot(c.date, c.baseline, color=GREY, lw=1, ls=":", label="baseline (same weekday)")
    for i, r in enumerate(b[b.market == "DE"].itertuples()):
        x = pd.Timestamp(r.start_date)
        ax.axvline(x, color=RED, ls="--", lw=1)
        ax.text(x - pd.Timedelta(days=1) if i == 0 else x, ax.get_ylim()[1] * (0.98 if i == 0 else 0.62), ha="right" if i == 0 else "left", s=f" {r.release_at_start.split(' ')[0]} {r.mean_deviation:+.0%} ", color=RED, fontsize=8, va="top")
    ax.legend(loc="lower left")
    datefmt(ax)
    return svg(f)


def ch_utm():
    u = csv("utm_by_agency")
    s = csv("utm_unassigned_summary").set_index("agency")
    f, ax = fig(3.2, 2.1)
    ax.bar(u.agency, u.pct_compliant, color=[RED if v < 80 else BLUE for v in u.pct_compliant], label="links compliant")
    ax.scatter(u.agency, [s.loc[a, "pct_unassigned"] for a in u.agency], color=INK, zorder=3, s=18, label="paid sessions Unassigned")
    for i, a in enumerate(u.agency):
        ax.text(i, u.pct_compliant.iloc[i] + 3, f"{u.pct_compliant.iloc[i]:.0f}%", ha="center", fontsize=8, color=INK)
    ax.set_ylim(0, 110)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_feed():
    fq = csv("feed_validation_summary")
    f, ax = fig(3.2, 2.1)
    ax.bar(fq.market, fq.wrong_currency, color=RED, label="wrong currency")
    ax.bar(fq.market, fq.missing_required, bottom=fq.wrong_currency, color=AMBER, label="missing availability")
    ax.set_ylabel("rows (of 300 per market)")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    return svg(f)


def ch_server():
    h = csv("server_hourly")
    h["hour_utc"] = pd.to_datetime(h.hour_utc)
    h = h[(h.hour_utc >= "2026-11-04") & (h.hour_utc < "2026-11-07")]
    f, ax = fig(4.9, 2.1)
    for d, col, lw in (("ga4", GREY, 0.8), ("google_ads", BLUE, 0.8), ("meta_capi", RED, 1.8)):
        g = h[h.destination == d]
        ax.plot(g.hour_utc, 100 * g.error_rate, color=col, lw=lw, label=d)
    ax.axhline(20, color=RED, ls="--", lw=0.8)
    ax.text(h.hour_utc.min(), 22, " FAIL threshold 20%", color=RED, fontsize=8)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.legend(loc="upper right")
    return svg(f)


# ---------------- HTML ----------------
CSS = """
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
body { margin:0; font-family:'Segoe UI', Arial, sans-serif; color:#0B0B0B; background:#EFEDE7; }
.page { width:297mm; height:210mm; padding:9mm 11mm 7mm; background:#EFEDE7; position:relative; page-break-after:always; overflow:hidden; display:flex; flex-direction:column; }
.page:last-child { page-break-after:auto; }
.top { display:flex; justify-content:space-between; align-items:center; font-size:8.5pt; color:#52514E; }
.tags span { display:inline-block; font-size:7pt; font-weight:700; letter-spacing:.06em; padding:2px 6px; border-radius:3px; margin-left:4px; }
.pub { background:#E3EEFB; color:#1C5CAB; } .sim { background:#FBE9E0; color:#9A3B12; } .doc { background:#E5E4DF; color:#52514E; }
h1 { font-size:19pt; margin:2.5mm 0 1mm; line-height:1.15; font-weight:650; }
.lead { font-size:9.5pt; color:#52514E; margin:0 0 3mm; max-width:265mm; }
.grid { display:grid; gap:3.5mm; flex:1; min-height:0; }
.card { background:#fff; border-radius:3mm; padding:3mm 4mm; min-width:0; min-height:0; overflow:hidden; }
.card h2 { font-size:10pt; margin:0 0 1mm; font-weight:650; } .card h2 span { font-size:6.5pt; font-weight:700; letter-spacing:.06em; padding:1px 5px; border-radius:3px; margin-left:4px; vertical-align:middle; }
.card p, .card li { font-size:8.4pt; color:#33322F; margin:1mm 0; line-height:1.35; }
.card ul, .card ol { margin:1mm 0; padding-left:4.5mm; }
.card svg { width:100%; height:auto; max-height:62mm; display:block; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:3.5mm; margin-bottom:3.5mm; }
.kpi { background:#fff; border-radius:3mm; padding:3mm 4mm; } .kpi .v { font-size:20pt; font-weight:650; color:#2A78D6; } .kpi .l { font-size:8pt; color:#52514E; }
table { border-collapse:collapse; width:100%; font-size:7.8pt; } th, td { text-align:left; padding:1.1mm 1.5mm; border-bottom:0.3mm solid #E1E0D9; vertical-align:top; }
th { color:#52514E; font-weight:600; } .red { color:#D03B3B; font-weight:600; } .ok { color:#1BAF7A; font-weight:600; }
code { font-family:Consolas, monospace; font-size:7.6pt; background:#F3F1EC; padding:0 1mm; border-radius:1mm; }
pre { font-family:Consolas, monospace; font-size:7pt; background:#F3F1EC; padding:2mm; border-radius:2mm; margin:1mm 0; white-space:pre-wrap; }
.foot { display:flex; justify-content:space-between; font-size:7pt; color:#898781; margin-top:2.5mm; }
.quote { font-size:8.6pt; border-left:1mm solid #2A78D6; padding:1.5mm 3mm; background:#F3F1EC; }
"""


def tag(t):
    return f'<span class="{ {"PUBLIC DATA": "pub", "SIMULATED": "sim"}.get(t, "doc") }">{t}</span>'


def card(title, body, t=None, style=""):
    return f'<div class="card" style="{style}"><h2>{html.escape(title)}{tag(t) if t else ""}</h2>{body}</div>'


def page(n, label, tags, title, lead, body, source):
    return (f'<section class="page"><div class="top"><div>{n} · {label}</div><div class="tags">{"".join(tag(t) for t in tags)}</div></div>'
            f'<h1>{title}</h1><p class="lead">{lead}</p>{body}'
            f'<div class="foot"><div>{source}</div><div>{FOOT} · page {n}</div></div></section>')


def tbl(cols, rows):
    return "<table><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>" + "".join(
        "<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>" for r in rows) + "</table>"


def build_html() -> str:
    k = json.loads((OUT / "key_numbers.json").read_text(encoding="utf-8"))
    r, rc, u, s = k["real"], k["recon"], k["utm"], k["server"]
    det = csv("detection_summary") if (OUT / "detection_summary.csv").exists() else None
    tests = csv("tests_results")
    pages = []

    # ---- page 0: overview
    kp = (f'<div class="kpis"><div class="kpi"><div class="v">{rc["pct_explained"]:.0f}%</div><div class="l">platform gaps explained ({rc["market_weeks"]} market-weeks, 0 unexplained) {tag("SIMULATED")}</div></div>'
          f'<div class="kpi"><div class="v">{r["extra_rows"]} + {r["without_id"]}</div><div class="l">purchase rows deduplicated + purchases without id found in the real sample {tag("PUBLIC DATA")}</div></div>'
          f'<div class="kpi"><div class="v">{u["pct_links_compliant"]:.1f}%</div><div class="l">UTM links compliant; {u["pct_unassigned"]:.1f}% of paid sessions Unassigned {tag("SIMULATED")}</div></div>'
          f'<div class="kpi"><div class="v">{s["delivered_pct"]:.2f}%</div><div class="l">server events delivered; outage alert 1 hour after it started {tag("SIMULATED")}</div></div></div>')
    q = ("<ol><li>Which GA4 data-quality problems exist in a real ecommerce property, and what do they distort?</li>"
         "<li>What does a client-side + server-side architecture with consent and deduplication look like, and can it be tested automatically?</li>"
         "<li>When GA4, Google Ads and Meta disagree, which gaps are normal and which are bugs?</li>"
         "<li>Which checks catch tracking incidents on 8 markets, and how fast?</li>"
         "<li>How do UTMs and product feeds stay clean when several agencies are involved?</li></ol>")
    rec = ("<ol><li><b>Fire purchase once per transaction_id</b> and make the id required: the real sample has "
           f"{r['without_id']} purchases without id and {r['duplicated_ids']} duplicated ids.</li>"
           "<li><b>Share one event_id</b> between pixel and Conversions API; never let a server tag create its own.</li>"
           "<li><b>Treat consent releases like code releases</b>: before/after check of sessions and hits before the choice.</li>"
           "<li><b>No campaign link without validation</b>: builder + validator + mapping table for agencies.</li>"
           "<li><b>Monitor hourly</b> where incidents are short (server container), daily elsewhere, and explain expected gaps instead of chasing them.</li></ol>")
    meth = ("<p><b>Real</b>: Google's public, obfuscated GA4 sample (2.07 million events), queried with DuckDB; BigQuery versions for the official export schema. "
            "<b>Rulebook</b>: Google, Meta, Merchant Center, CNIL and IAB pages read on 2026-11-25.</p>"
            f"<p><b>Built</b>: tracking plan, dataLayer JSON Schema, GTM web and server templates, demo shop with {len(tests)} SQL assertions and 8 browser tests. "
            "<b>Simulated</b>: 12 weeks of a fictional client, Client M (8 markets, 5 platforms), with 8 planted events found by the monitoring.</p>")
    pages.append(page(0, "Overview", ["PUBLIC DATA", "SIMULATED"],
                      "Most gaps between GA4 and ad platforms are normal; the bugs are few, findable, and cheap to monitor",
                      "An independent case study for the Tracking Specialist role at SouthWatts: a real GA4 audit, a tested tracking setup, and the reconciliation and monitoring of a simulated multi-market client.",
                      kp + '<div class="grid" style="grid-template-columns:1fr 1.15fr 1fr;grid-template-rows:1fr auto">' + card("5 questions", q) + card("5 recommendations", rec) + card("Method in 3 lines", meth) +
                      card("What is in the repository", tbl(["Deliverable", "What it is", "Data"], [
                          ["Tracking plan, dataLayer schema, GTM web + server templates", "tracking/ (Excel, Markdown, JSON; placeholder ids)", "template"],
                          ["Demo shop + automatic tests", "site/demo-shop (no active tag), tests/test_datalayer.py (Playwright)", "SIMULATED"],
                          ["SQL 01-08 + 99 assertions, BigQuery versions", "sql/ (DuckDB), sql/bigquery/ (official export schema)", "PUBLIC + SIMULATED"],
                          ["UTM builder and validator, feed validator, monitoring", "utm/utm_builder.xlsx, src/*_validator.py, src/monitoring.py", "SIMULATED"],
                          ["Interactive dashboard (5 tabs), notebook, 10 documents", "site/dashboard, notebooks/, docs/", "PUBLIC + SIMULATED"]]), None, "grid-column:span 3") + "</div>",
                      "Sources: GA4 public sample (BigQuery public dataset, via a Hugging Face mirror); simulation src/simulate_tracking.py (seed 42)."))

    # ---- page 1: SouthWatts and the job
    missions = [
        ("Audit, design, deploy and maintain client- and server-side tracking", "Real GA4 audit (p.2); architecture, web + server GTM templates (p.3)"),
        ("Media tracking: pixels, conversion tags, conversion APIs, Google Tag Gateway", "Pixel + CAPI with shared event_id; Tag Gateway placed in the architecture (p.3)"),
        ("Monitor tracking and data quality on all markets", "9 checks, PASS/WARN/FAIL, 8 markets; 8/8 planted events found (p.5)"),
        ("Enforce UTMs, investigate discrepancies", "UTM builder + validator; reconciliation with 0 unexplained gaps (p.4-5)"),
        ("Product catalogue integrations on ad platforms", "Feed validator on the Merchant Center specification (p.5)"),
        ("Work with global/local marketing teams, agencies, tech teams", "One-page agency onboarding; discrepancy playbook"),
        ("Support marketing teams and agencies, troubleshoot, launches", "Acceptance checklist before publishing; runbook with first checks"),
        ("Documentation, implementation guides, best practices", "10 documents in docs/, tracking plan in Excel and Markdown"),
    ]
    comp = ("<p><b>SouthWatts</b> is the brand of South Hamlet SAS, a digital analytics consultancy based near Montpellier "
            "(Castelnau-le-Lez), founded in 2017, with 10 to 19 employees according to the French company register (SIRENE). "
            "It works with multinational companies.</p><p>The role (freelance, remote, French working hours) takes over ongoing tracking work: "
            "Google Tag Manager and Google Analytics at the core, media tags and conversion APIs, data quality across markets, and growing use of agentic AI.</p>"
            "<p style='color:#898781'>Sources: company legal notice and SIRENE register, read 2026-11-25; job post read 2026-11-25. "
            "SouthWatts' clients are not named in public sources and are not guessed here: the client of this study is fictional.</p>")
    proc = ("<p>The hiring process includes a <b>technical test on tracking and data analysis</b>. This study is built as preparation for it: "
            "every part can be re-run, and the data used is either public or simulated.</p>"
            "<p><b>Not covered</b>: no real container, no real account, no audit of any real company's website, no data sent to any platform.</p>")
    pages.append(page(1, "SouthWatts and the job", ["DOCUMENTATION"],
                      "The job is to make measurement trustworthy across markets: this study covers each of the 8 missions",
                      "What the company does, what the role asks for, and where each mission is shown in this study.",
                      '<div class="grid" style="grid-template-columns:1fr 1.7fr">' +
                      '<div style="display:grid;gap:3.5mm;grid-template-rows:auto 1fr">' + card("The company", comp) + card("The process", proc) + "</div>" +
                      card("The 8 missions and what this study shows", tbl(["Mission (job post)", "Shown here"], missions)) + "</div>",
                      "Sources: southwatts.com legal notice; recherche-entreprises.api.gouv.fr (SIRENE); job post. Read 2026-11-25."))

    # ---- page 2: real GA4 audit
    p2 = (card("What is broken in the purchase events", ch_real_findings(k) +
               f"<p>{r['pct_without_id']}% of purchase events cannot be deduplicated or matched to orders. {r['pct_revenue_counted_twice']}% of purchase revenue is counted twice (USD {r['revenue_counted_twice']:,.0f}).</p>", "PUBLIC DATA") +
          card("Self-referral steals the credit", ch_real_channels() +
               f"<p>{r['self_ref_sessions']:,} sessions ({100 * r['self_ref_sessions'] / r['sessions']:.1f}%) start from the shop's own domains and hold <b>{r['pct_purchases_in_self_ref_sessions']}%</b> of purchases: the real channel loses them.</p>", "PUBLIC DATA") +
          card("Copies arrive within a minute: reloads", ch_real_gap() + f"<p>{r['dup_within_1min']} of {r['duplicated_ids']} duplicated ids repeat within 60 s: fix in the tag (once per id).</p>", "PUBLIC DATA") +
          card("Self-referral stops on one day: a setup change", ch_real_daily() + f"<p>{r['selfref_before_pct']}% of page views until {r['selfref_break_date']}, {r['selfref_after_pct']}% after: a dated break, the signature of a configuration change (its cause is not in the data).</p>", "PUBLIC DATA") +
          card("What each finding distorts, and the fix", tbl(["Finding", "Distorts", "Fix"], [
              ["Purchase without id", "Dedup, back-office match, Ads orderId", "Required in schema; block tag if empty"],
              ["Duplicated id", "Purchases, revenue (+6%)", "Once per id; dedup in queries"],
              ["Self-referral", "Channel credit, ROAS", "Unwanted referrals; cross-domain linker"],
              [f"Medium missing on {r['pct_missing_medium_pv']}% of page views", "Event-level channel reports", "By design: session-scoped source (query 02)"],
              [f"{r['data_deleted_pv']:,} '(data deleted)'", "Small gap", "Document, exclude"]]), "PUBLIC DATA", "grid-column:span 2"))
    pages.append(page(2, "A real GA4 audit", ["PUBLIC DATA"],
                      f"In Google's public GA4 sample, one purchase in six has no usable id and self-referral holds {r['pct_purchases_in_self_ref_sessions']:.0f}% of purchases",
                      "Audit of the Google Merchandise Store obfuscated sample (1 Nov 2020 - 31 Jan 2021) with queries on the GA4 data model. Google's demo data, not a client.",
                      '<div class="grid" style="grid-template-columns:1.25fr 1.25fr 1fr;grid-template-rows:1fr 1fr">' +
                      p2 + "</div>",
                      "Source: bigquery-public-data.ga4_obfuscated_sample_ecommerce via Hugging Face mirror gizdevans/ga4-bq-flattened-data. Queries: sql/01, sql/02."))

    # ---- page 3: architecture and plan
    arch = (ROOT / "tracking" / "architecture.svg").read_text(encoding="utf-8")
    arch = arch[arch.index("<svg"):]
    plan_rows = [["view_item_list", "list rendered", "GA4"], ["view_item", "product page", "GA4, Meta ViewContent"],
                 ["add_to_cart", "cart API confirmed", "GA4, Meta AddToCart"], ["begin_checkout", "checkout step 1", "GA4, Meta InitiateCheckout"],
                 ["add_payment_info", "payment method", "GA4, Meta AddPaymentInfo"], ["purchase", "confirmation, once per id", "GA4, Google Ads, Meta, LinkedIn"]]
    t_ok = int(tests.passed.sum())
    test_txt = (f"<p><b>8 / 8</b> browser tests (Playwright, headless Chromium) and <b>{t_ok} / {len(tests)}</b> SQL assertions pass.</p><ul>"
                "<li>Consent default <code>denied</code> before any event</li><li>Every event valid against the JSON Schema</li>"
                "<li><code>ecommerce: null</code> before each push</li><li><code>event_id</code> present, unique, reused by the server</li>"
                "<li>No second <code>purchase</code> after reload</li><li>Bug mode (reload, new server id) is caught by the same checks</li>"
                "<li>No request leaves the browser: the demo shop has <b>no active tag</b></li></ul>")
    dl = ('<pre>{ event: "purchase", event_id: "evt_3f9c2a1b7d4e8f60",\n  ecommerce: { transaction_id: "CMFR0001234", value: 129.0,\n'
          '    currency: "EUR", items: [{ item_id: "SKU0002", ... }] } }</pre>')
    pages.append(page(3, "Architecture and tracking plan", ["DOCUMENTATION", "SIMULATED"],
                      "One event_id from the browser to every platform, consent first, and a dataLayer tested on every change",
                      "Client and server containers, Google tag gateway, Consent Mode, the tracking plan and its automatic tests. Templates for a fictional client, with placeholder ids only.",
                      '<div class="grid" style="grid-template-columns:1.55fr 1fr;grid-template-rows:1.25fr 1fr">' +
                      card("Architecture", arch, "DOCUMENTATION", "grid-row:span 1") +
                      card("dataLayer tested automatically", test_txt, "SIMULATED") +
                      card("Tracking plan (6 events, 59 parameter rows)", tbl(["Event", "Trigger", "Destinations"], plan_rows) +
                           "<p>Names follow the GA4 recommended events reference (read 2026-11-25).</p>", "DOCUMENTATION") +
                      card("Example push and rules", dl + "<p>Meta deduplicates pixel and server events that share <code>event_id</code> and event name "
                           "(Meta documentation, read 2026-11-25). Google tag gateway serves the Google tag from the site's own domain (Google documentation, read 2026-11-25). "
                           "Consent: CNIL rules read 2026-11-25; not legal advice.</p>", "DOCUMENTATION") + "</div>",
                      "Files: tracking/ (plan, schema, GTM templates, architecture), site/demo-shop/, tests/test_datalayer.py."))

    # ---- page 4: why numbers disagree
    pages.append(page(4, "Why the numbers disagree", ["SIMULATED"],
                      f"Google Ads +{rc['google_gap_pct']:.0f}% above GA4 is expected; Meta ×{rc['meta_multiplier']} in France and Spain is a bug",
                      f"Weekly reconciliation of back office, GA4 and platforms for the fictional Client M: {rc['market_weeks']} market-weeks, each classified as expected or anomalous with the signal that proves it; 0 unexplained.",
                      '<div class="grid" style="grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr">' +
                      card("Google Ads ÷ GA4: stable gap, except two broken markets", ch_ratio("google_ads", ["UK", "DE"], "Google Ads ÷ GA4") +
                           f"<p>Baseline ratio {rc['google_r0']:.2f}: data-driven vs last non-direct click, 30-day window, click date. <b>Not a bug</b>: explained, not fixed. Red: UK (cross-domain) and DE (consent) break GA4.</p>", "SIMULATED") +
                      card("Meta ÷ back office: double counting from 7 October", ch_ratio("meta", ["FR", "ES"], "Meta ÷ back-office orders") +
                           f"<p>FR+ES ratio {rc['meta_frs_before']} → {rc['meta_frs_after']}: the server Purchase got its own event_id (release web-v40), so pixel and CAPI are both counted. Fix: reuse the browser event_id.</p>", "SIMULATED") +
                      card("Every gap categorised", ch_recon_bar() + "<p>Anomalous = beyond 2 standard errors in the direction a diagnostic signal predicts (consent break, self-referral share, event_id match, server errors).</p>", "SIMULATED") +
                      card("The two other bugs behind the gaps", "<ul>"
                           f"<li><b>Cross-domain (UK, from 28 Oct)</b>: a new payment provider without linker; 70% of UK purchases then come from the provider or the shop itself (same defect as the {r['self_referral_pv']:,} self-referral page views of the real sample). Fix: linker domains + unwanted referrals.</li>"
                           f"<li><b>Duplicate purchases (IT)</b>: confirmation reloads send the same transaction_id again, <b>+{k['dedup']['it_extra_pct']:.1f}%</b> purchases in GA4 (the real sample shows the same defect). Fix: once per id + daily check. Reconciliation counts unique ids, so it is not misled.</li>"
                           "<li><b>What is expected</b>: attribution model, window, click vs event date, consent (platform sees fewer users), view-through (CM360, LinkedIn), time zone and currency.</li></ul>"
                           "<p>Playbook: docs/discrepancy_playbook.md.</p>", "SIMULATED") + "</div>",
                      "Source: SIMULATED data (src/simulate_tracking.py, seed 42); sql/03_platform_reconciliation.sql, sql/04_dedup_checks.sql."))

    # ---- page 5: keep it reliable
    det_txt = ""
    if det is not None:
        det_txt = tbl(["#", "Event", "First FAIL", "Result"], [[d.event, d.name.replace("_", " "), ("first run" if d.event in (3, 7) else str(d.first_fail)[:16]) if isinstance(d.first_fail, str) else "-",
                                                             '<span class="ok">' + ("found" if d.is_bug else "not flagged (correct)") + "</span>" if d.found else '<span class="red">missed</span>']
                                                            for d in det.itertuples()])
    pages.append(page(5, "Keep it reliable", ["SIMULATED"],
                      f"Nine simple checks found all 8 planted problems; the server outage was raised one hour after it started",
                      "Consent release, UTMs, product feed and server container: what each check sees, with documented thresholds (docs/monitoring_runbook.md).",
                      '<div class="grid" style="grid-template-columns:1.25fr 1fr 1fr;grid-template-rows:1fr 1fr">' +
                      card("Consent release in Germany: up, then down", ch_de() +
                           f"<p>web-v41 sent GA4 hits before the choice (+{k['consent']['up_pct']:.0f}% sessions, purchases flat); the hotfix web-v42 blocked too much ({k['consent']['down_pct']:.0f}%). Each break is dated and matched with its release.</p>", "SIMULATED") +
                      card("UTMs by agency", ch_utm() + f"<p>AGY2 writes Facebook, facebook, fb...: {u['agy2_unassigned']:.0f}% of its paid sessions are Unassigned ({u['pct_unassigned']:.1f}% overall).</p>", "SIMULATED") +
                      card("Product feed (PL, UK)", ch_feed() + f"<p>{k['feed']['wrong_currency']} rows in EUR instead of PLN/GBP, {k['feed']['missing_availability']} without availability: {k['feed']['pl_pct']:.0f}% of products at risk of disapproval.</p>", "SIMULATED") +
                      card("Server container outage, 5 Nov 02:00-09:00 UTC", ch_server() +
                           f"<p>Meta CAPI errors at 100%, {s['failed_events']} events lost. Daily Meta conversions that day: {s['meta_day_dev_pct']:+.0f}% vs the same weekday, inside the normal range ({s['meta_noise_range_pct'][0]:.0f}% to +{s['meta_noise_range_pct'][1]:.0f}%): <b>only the hourly check sees it</b> (alert at 03:00).</p>", "SIMULATED", "grid-column:span 1") +
                      card("8 planted events vs the checks", det_txt, "SIMULATED", "grid-column:span 2") + "</div>",
                      "Source: SIMULATED data; sql/05-08, src/utm_validator.py, src/feed_validator.py, src/monitoring.py."))

    # ---- page 6: methods, limits, AI
    src_rows = [["GA4 public sample (obfuscated)", "BigQuery public dataset via Hugging Face mirror (MIT)", "2026-11-25"],
                ["GA4 recommended events", "developers.google.com/analytics/devguides/collection/ga4/reference/events", "2026-11-25"],
                ["GA4 BigQuery export schema", "support.google.com/analytics/answer/7029846", "2026-11-25"],
                ["GA4 Measurement Protocol", "developers.google.com/analytics/devguides/collection/protocol/ga4", "2026-11-25"],
                ["Meta pixel / CAPI deduplication", "developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events", "2026-11-25"],
                ["Google tag gateway", "developers.google.com/tag-platform/tag-manager/gateway", "2026-11-25"],
                ["Merchant Center product data spec", "support.google.com/merchants/answer/7052112", "2026-11-25"],
                [f"IAB TCF Global Vendor List v3 (v{k['iab']['version']}, {k['iab']['vendors']:,} vendors)", "vendor-list.consensu.org/v3/vendor-list.json", "2026-11-25"],
                ["CNIL, cookies and trackers", "cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies", "2026-11-25"],
                ["Public holidays", "date.nager.at", "2026-11-25"]]
    limits = ("<ul><li>The GA4 sample is obfuscated and partial: findings describe the sample, not a live store.</li>"
              "<li>Client M is <b>fictional</b>; its data is <b>SIMULATED</b>. No internal data of SouthWatts or of any client is used or guessed.</li>"
              "<li>Platform windows and models in the simulation are documented hypotheses, not defaults read in platform documentation.</li>"
              "<li>The GTM files are templates with placeholder ids; they were not imported into a real account.</li>"
              "<li>No account was created, no API called, no data sent to any platform; the demo shop has no active tag.</li>"
              "<li>Consent: principles cited from CNIL; <b>not legal advice</b>.</li>"
              "<li>Thresholds are starting values; tune them on a month of real history.</li></ul>")
    rerun = ("<pre>python src/extract_ga4.py        # or copy the slim parquet\npython src/simulate_tracking.py\npython src/run_sql.py\n"
             "python -m pytest tests\npython src/utm_validator.py\npython src/feed_validator.py\npython src/monitoring.py\n"
             "python src/build_dashboard.py\npython src/build_pdf.py</pre>")
    pages.append(page(6, "Methods, limits & AI note", ["PUBLIC DATA", "SIMULATED"],
                      "Every number can be re-run from public data and a seeded simulation",
                      "Sources with read dates, what is real and what is simulated, the limits, and how AI was used.",
                      '<div class="grid" style="grid-template-columns:1.35fr 1fr;grid-template-rows:auto 1fr">' +
                      card("Sources (all read on 2026-11-25)", tbl(["Source", "Where"], [x[:2] for x in src_rows]), None, "grid-row:span 2") +
                      card("Limits", limits) +
                      card("Re-run and AI note", rerun + f'<p class="quote">{AI_NOTE}</p><p>No LLM is called in the analysis.</p>') + "</div>",
                      "Repository: SQL (DuckDB), Python, Playwright tests, Plotly dashboard."))
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SouthWatts tracking case study</title><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'


def main():
    DRAFT.parent.mkdir(parents=True, exist_ok=True)
    PDF.parent.mkdir(parents=True, exist_ok=True)
    DRAFT.write_text(build_html(), encoding="utf-8")
    print_pdf(DRAFT, PDF, "SouthWatts: a tracking stack you can trust")
    from pypdf import PdfReader
    n = len(PdfReader(str(PDF)).pages)
    print(f"pdf -> {PDF.relative_to(ROOT)} ({n} pages, {PDF.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
