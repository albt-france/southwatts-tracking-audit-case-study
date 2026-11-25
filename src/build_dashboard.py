"""Self-contained interactive dashboard (one HTML file, Plotly embedded, works offline): site/dashboard/index.html

Tabs: (1) Overview, (2) Real GA4 audit (PUBLIC DATA), (3) Platform reconciliation (SIMULATED),
(4) UTM & catalog quality (SIMULATED), (5) Monitoring (SIMULATED). Every chart carries its data label.
All numbers come from data/out (SQL, validators, monitoring); nothing is typed by hand.

    python src/build_dashboard.py
"""
import json
from pathlib import Path

import pandas as pd
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "out"
DEST = ROOT / "site" / "dashboard" / "index.html"


def rec(name, cols=None, query=None):
    d = pd.read_csv(OUT / f"{name}.csv")
    if query:
        d = d.query(query)
    if cols:
        d = d[cols]
    return json.loads(d.to_json(orient="records", date_format="iso"))


def data():
    k = json.loads((OUT / "key_numbers.json").read_text(encoding="utf-8"))
    mon = pd.read_csv(OUT / "monitoring_report.csv")
    mon["week"] = pd.to_datetime(mon.period.str[:10]).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    heat = mon[mon.status == "FAIL"].groupby(["check", "week"]).size().rename("fails").reset_index()
    hourly = pd.read_csv(OUT / "server_hourly.csv")
    hourly = hourly[(hourly.hour_utc >= "2026-11-03") & (hourly.hour_utc < "2026-11-08")]
    det = OUT / "detection_summary.csv"
    return {
        "k": k,
        "detect": rec("detection_summary", ["event", "name", "is_bug", "check", "first_fail", "detection_delay", "found"]) if det.exists() else [],
        "heat": json.loads(heat.to_json(orient="records")),
        "real_daily": rec("real_audit_daily"),
        "real_channels": rec("real_channels"),
        "real_gap": rec("real_audit_duplicate_gap"),
        "recon": rec("reconciliation_weekly", ["market", "week", "platform", "backend_orders", "ga4_purchases", "platform_conversions",
                                               "ratio", "expected_ratio", "z", "category", "explanation"]),
        "recon_period": rec("reconciliation_period"),
        "utm_agency": rec("utm_by_agency"),
        "utm_unassigned": rec("utm_unassigned_summary"),
        "utm_weekly": rec("utm_unassigned_weekly"),
        "utm_variants": rec("utm_variants"),
        "feed": rec("feed_validation_summary"),
        "consent": rec("consent_daily", ["date", "market", "sessions", "baseline", "deviation", "pre_choice_share", "holiday"]),
        "consent_breaks": rec("consent_breaks"),
        "meta_match": rec("dedup_meta_daily", query="market in ['FR','ES','DE','IT']"),
        "dup_daily": rec("dedup_ga4_daily", ["date", "market", "duplicate_rate"]),
        "hourly": json.loads(hourly.to_json(orient="records")),
        "selfref": rec("monitoring_report", ["period", "scope", "value"], "check == 'purchase_self_referral'"),
        "status": rec("monitoring_status", ["check", "scope", "period", "value", "status", "note"]),
    }


HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SouthWatts tracking dashboard</title>
<meta name="description" content="Independent case study: tracking audit, platform reconciliation, UTM and catalog quality, monitoring. Public GA4 sample + simulated client.">
<style>
:root { color-scheme: light; --bg:#F3F1EC; --card:#FFFFFF; --line:#E1E0D9; --ink:#0B0B0B; --muted:#52514E; --accent:#2A78D6; --red:#D03B3B; --grey:#A3A19A;
        --pub:#E3EEFB; --pubt:#1C5CAB; --sim:#FBE9E0; --simt:#9A3B12; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme: dark; --bg:#141413; --card:#1D1D1B; --line:#33322F; --ink:#F0EFEC; --muted:#C3C2B7; --accent:#3987E5; --red:#E66767; --grey:#77756E; --pub:#1C2E45; --pubt:#9CC3F2; --sim:#40261A; --simt:#F2B89C; } }
:root[data-theme="dark"] { color-scheme: dark; --bg:#141413; --card:#1D1D1B; --line:#33322F; --ink:#F0EFEC; --muted:#C3C2B7; --accent:#3987E5; --red:#E66767; --grey:#77756E; --pub:#1C2E45; --pubt:#9CC3F2; --sim:#40261A; --simt:#F2B89C; }
* { box-sizing:border-box; }
body { margin:0; font-family:'Segoe UI', Arial, sans-serif; background:var(--bg); color:var(--ink); }
.wrap { max-width:1280px; margin:0 auto; padding:20px 16px 40px; }
h1 { font-size:24px; margin:0 0 4px; } .sub { color:var(--muted); margin:0 0 14px; font-size:14px; }
nav { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:12px; }
nav button { border:1px solid var(--line); background:var(--card); color:var(--ink); padding:7px 12px; border-radius:6px; cursor:pointer; font:inherit; font-size:14px; }
nav button.on { border-color:var(--accent); color:var(--accent); font-weight:600; }
.tab { display:none; } .tab.on { display:block; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 380px), 1fr)); gap:12px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px; min-width:0; }
.card h2 { font-size:15px; margin:0 0 6px; } .card p { font-size:13px; color:var(--muted); margin:4px 0; }
.tag { font-size:11px; font-weight:700; letter-spacing:.06em; padding:3px 7px; border-radius:4px; margin-left:6px; vertical-align:middle; white-space:nowrap; }
.pub { background:var(--pub); color:var(--pubt); } .sim { background:var(--sim); color:var(--simt); }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 200px), 1fr)); gap:12px; margin-bottom:12px; }
.kpi .v { font-size:30px; font-weight:600; } .kpi .l { font-size:13px; color:var(--muted); }
.ctrl { display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin:4px 0 8px; font-size:13px; color:var(--muted); }
select { font:inherit; font-size:13px; padding:4px 6px; border:1px solid var(--line); border-radius:5px; background:var(--card); color:var(--ink); }
.tbl { overflow-x:auto; } table { border-collapse:collapse; width:100%; font-size:13px; } th, td { text-align:left; padding:5px 6px; border-bottom:1px solid var(--line); }
th { color:var(--muted); font-weight:600; } .ok { color:#1BAF7A; font-weight:600; } .bad { color:var(--red); font-weight:600; }
.plot { width:100%; height:320px; }
footer { margin-top:24px; font-size:12px; color:var(--muted); text-align:center; }
</style></head><body><div class="wrap">
<h1>SouthWatts: a tracking stack you can trust</h1>
<p class="sub">Independent case study. Real audit on Google's public GA4 sample (PUBLIC DATA) and 12 simulated weeks of a fictional multinational, "Client M", on 8 markets and 5 platforms (SIMULATED).</p>
<nav>
 <button class="on" data-t="t1">Overview</button><button data-t="t2">Real GA4 audit</button><button data-t="t3">Platform reconciliation</button>
 <button data-t="t4">UTM &amp; catalog quality</button><button data-t="t5">Monitoring</button>
</nav>

<section id="t1" class="tab on">
 <div class="kpis" id="kpis"></div>
 <div class="grid">
  <div class="card"><h2>Planted events: found by the checks? <span class="tag sim">SIMULATED</span></h2><p>Event 6 is a trap: an expected gap that must <b>not</b> be raised as a bug.</p><div class="tbl" id="o_detect"></div></div>
  <div class="card"><h2>Failed checks by week <span class="tag sim">SIMULATED</span></h2><div id="o_heat" class="plot"></div></div>
 </div>
</section>

<section id="t2" class="tab">
 <div class="grid">
  <div class="card"><h2>What is broken in the sample <span class="tag pub">PUBLIC DATA</span></h2><div id="r_find" class="plot"></div><p>Google Merchandise Store, obfuscated GA4 sample, 1 Nov 2020 - 31 Jan 2021.</p></div>
  <div class="card"><h2>Sessions and purchases by session channel <span class="tag pub">PUBLIC DATA</span></h2><div id="r_ch" class="plot"></div><p>Self-referral sessions hold almost one purchase in three.</p></div>
  <div class="card"><h2>Self-referral share of page views, by day <span class="tag pub">PUBLIC DATA</span></h2><div id="r_daily" class="plot"></div></div>
  <div class="card"><h2>Time between two copies of the same transaction_id <span class="tag pub">PUBLIC DATA</span></h2><div id="r_gap" class="plot"></div><p>Most copies arrive within a minute: confirmation page reloads.</p></div>
 </div>
</section>

<section id="t3" class="tab">
 <div class="ctrl">Market <select id="m_sel"></select></div>
 <div class="grid">
  <div class="card"><h2>Google Ads ÷ GA4, by week <span class="tag sim">SIMULATED</span></h2><div id="rc_g" class="plot"></div><p>Dashed line: expected ratio from 4 baseline weeks; a week is anomalous beyond 2-3 standard errors with a diagnostic signal. Above GA4 by design: attribution model, 30-day window, click date.</p></div>
  <div class="card"><h2>Meta ÷ back office, by week <span class="tag sim">SIMULATED</span></h2><div id="rc_m" class="plot"></div><p>Red: anomalous weeks, with the diagnostic signal that explains them.</p></div>
 </div>
 <div class="card" style="margin-top:12px"><h2>Every gap categorised <span class="tag sim">SIMULATED</span></h2><div class="tbl" id="rc_tbl"></div></div>
 <div class="card" style="margin-top:12px"><h2>LinkedIn and CM360, whole period <span class="tag sim">SIMULATED</span></h2><div class="tbl" id="rc_p"></div></div>
</section>

<section id="t4" class="tab">
 <div class="grid">
  <div class="card"><h2>UTM compliance by agency <span class="tag sim">SIMULATED</span></h2><div id="u_ag" class="plot"></div></div>
  <div class="card"><h2>Paid sessions in "Unassigned", by week <span class="tag sim">SIMULATED</span></h2><div id="u_wk" class="plot"></div></div>
  <div class="card"><h2>Spellings found in agency links <span class="tag sim">SIMULATED</span></h2><div class="tbl" id="u_var"></div></div>
  <div class="card"><h2>Product feed: rows at risk of disapproval <span class="tag sim">SIMULATED</span></h2><div id="f_mk" class="plot"></div><p>Rules from the Merchant Center product data specification (read 2026-11-25).</p></div>
 </div>
</section>

<section id="t5" class="tab">
 <div class="grid">
  <div class="card"><h2>Germany: sessions vs baseline and releases <span class="tag sim">SIMULATED</span></h2><div id="mo_de" class="plot"></div></div>
  <div class="card"><h2>Meta: pixel and CAPI share the same event_id? <span class="tag sim">SIMULATED</span></h2><div id="mo_meta" class="plot"></div></div>
  <div class="card"><h2>Server container: hourly error rate, 3-7 Nov (UTC) <span class="tag sim">SIMULATED</span></h2><div id="mo_srv" class="plot"></div></div>
  <div class="card"><h2>Duplicate purchases and self-referral, by day <span class="tag sim">SIMULATED</span></h2><div id="mo_dup" class="plot"></div></div>
 </div>
 <div class="card" style="margin-top:12px"><h2>Latest status per check <span class="tag sim">SIMULATED</span></h2><div class="tbl" id="mo_tbl"></div></div>
</section>

<footer>Independent case study based on public data · not affiliated with or endorsed by SouthWatts</footer>
</div>
<script>__PLOTLY__</script>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const C = () => ({ink:css('--ink'), muted:css('--muted'), line:css('--line'), accent:css('--accent'), red:css('--red'), grey:css('--grey')});
const MK = {FR:'#2A78D6', DE:'#EB6834', ES:'#1BAF7A', IT:'#EDA100', UK:'#E87BA4', NL:'#7A5CD6', PL:'#4FB6C9', US:'#8A8A80'};
const layout = (extra) => { const c = C(); return Object.assign({margin:{l:48,r:12,t:10,b:40}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  font:{family:'Segoe UI, Arial', size:12, color:c.muted}, xaxis:{gridcolor:c.line, zeroline:false}, yaxis:{gridcolor:c.line, zeroline:false},
  legend:{orientation:'h', y:-0.18}, hovermode:'closest'}, extra||{}); };
const cfg = {displayModeBar:false, responsive:true};
const fmt = (v, d=0) => v==null ? '' : Number(v).toLocaleString('en-US', {minimumFractionDigits:d, maximumFractionDigits:d});
const table = (el, cols, rows) => { document.getElementById(el).innerHTML = '<table><tr>' + cols.map(c=>'<th>'+c[0]+'</th>').join('') + '</tr>' +
  rows.map(r=>'<tr>'+cols.map(c=>'<td>'+c[1](r)+'</td>').join('')+'</tr>').join('') + '</table>'; };
const drawn = {};
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on', x===b));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on', t.id===b.dataset.t));
  draw(b.dataset.t);
});
const K = D.k;

function t1() {
  const kp = [[fmt(K.recon.pct_explained,0)+'%', 'platform gaps explained ('+K.recon.market_weeks+' market-weeks, 0 unexplained)', 'SIMULATED'],
              [K.monitoring.found+' / 8', 'planted events found (Google Ads gap correctly not flagged)', 'SIMULATED'],
              [fmt(K.utm.pct_links_compliant,1)+'%', 'UTM links compliant (AGY2: '+fmt(K.utm.agy2_compliant,1)+'%)', 'SIMULATED'],
              [fmt(K.server.delivered_pct,2)+'%', 'server events delivered; outage alert 1 h after start', 'SIMULATED'],
              [fmt(K.real.without_id)+' + '+fmt(K.real.duplicated_ids), 'GA4 purchases without id + duplicated ids (real sample)', 'PUBLIC DATA']];
  document.getElementById('kpis').innerHTML = kp.map(x=>'<div class="card kpi"><div class="v">'+x[0]+'</div><div class="l">'+x[1]+
     ' <span class="tag '+(x[2]==='SIMULATED'?'sim':'pub')+'">'+x[2]+'</span></div></div>').join('');
  table('o_detect', [['#', r=>r.event], ['Event', r=>r.name.replaceAll('_',' ')], ['Check', r=>r.check], ['First FAIL', r=>(r.first_fail||'-').slice(0,16)],
        ['Delay', r=>!r.detection_delay ? '-' : r.detection_delay.startsWith('0 days') ? Number(r.detection_delay.slice(7,9))+' h' : r.detection_delay.replace(' 00:00:00','').replace('1 days','1 day')],
        ['Result', r=>r.found ? '<span class="ok">'+(r.is_bug?'found':'not flagged (correct)')+'</span>' : '<span class="bad">missed</span>']], D.detect);
  const checks = [...new Set(D.heat.map(r=>r.check))], weeks = [...new Set(D.heat.map(r=>r.week))].sort();
  const z = checks.map(c => weeks.map(w => (D.heat.find(r=>r.check===c && r.week===w)||{fails:0}).fails));
  Plotly.newPlot('o_heat', [{type:'heatmap', x:weeks, y:checks, z:z, colorscale:[[0,'rgba(0,0,0,0)'],[0.01,'#F4C7C6'],[1,'#D03B3B']], showscale:false,
     hovertemplate:'%{y}<br>week of %{x}: %{z} FAIL<extra></extra>'}], layout({margin:{l:170,r:10,t:10,b:40}}), cfg);
}
function t2() {
  const c = C();
  const f = [['Purchases without id', K.real.without_id], ['Duplicated ids', K.real.duplicated_ids], ['Extra purchase rows', K.real.extra_rows]];
  Plotly.newPlot('r_find', [{type:'bar', x:f.map(x=>x[1]), y:f.map(x=>x[0]), orientation:'h', marker:{color:[c.red,c.red,c.grey]},
     text:f.map(x=>fmt(x[1])), textposition:'outside', hovertemplate:'%{y}: %{x}<extra></extra>'}],
     layout({margin:{l:150,r:40,t:10,b:30}, xaxis:{gridcolor:c.line, title:'purchase events (of '+fmt(K.real.purchase_events)+')'}}), cfg);
  const ch = D.real_channels.filter(r=>r.channel!=='Unassigned');
  Plotly.newPlot('r_ch', [{type:'bar', name:'% of sessions', x:ch.map(r=>r.channel), y:ch.map(r=>r.pct_sessions), marker:{color:c.grey}},
     {type:'bar', name:'% of purchases', x:ch.map(r=>r.channel), y:ch.map(r=>100*r.purchases/ch.reduce((s,x)=>s+x.purchases,0)),
      marker:{color:ch.map(r=>r.channel.startsWith('Self')?c.red:c.accent)}}],
     layout({barmode:'group', margin:{l:40,r:10,t:10,b:110}, yaxis:{gridcolor:c.line, ticksuffix:'%'}}), cfg);
  Plotly.newPlot('r_daily', [{type:'scatter', mode:'lines', x:D.real_daily.map(r=>r.date), y:D.real_daily.map(r=>100*r.self_referral_share),
     line:{color:c.red}, name:'self-referral'}], layout({yaxis:{gridcolor:c.line, ticksuffix:'%', rangemode:'tozero'}}), cfg);
  Plotly.newPlot('r_gap', [{type:'bar', x:D.real_gap.map(r=>r.gap_bucket.slice(3)), y:D.real_gap.map(r=>r.duplicated_ids), marker:{color:c.accent},
     text:D.real_gap.map(r=>r.duplicated_ids), textposition:'outside'}], layout({yaxis:{gridcolor:c.line, title:'duplicated ids'}}), cfg);
}
function t3() {
  const sel = document.getElementById('m_sel');
  if (!sel.options.length) { ['ALL','FR','DE','ES','IT','UK','NL','PL','US'].forEach(m => sel.add(new Option(m==='ALL'?'All markets':m, m))); sel.onchange = t3; }
  const m = sel.value || 'ALL', c = C();
  const plot = (el, platform) => {
    const rows = D.recon.filter(r=>r.platform===platform && (m==='ALL' || r.market===m));
    const mk = [...new Set(rows.map(r=>r.market))];
    const r0 = rows.length ? rows[0].expected_ratio : 1;
    const tr = mk.map(k => { const rr = rows.filter(r=>r.market===k); return {type:'scatter', mode:'lines+markers', name:k, x:rr.map(r=>r.week), y:rr.map(r=>r.ratio),
       line:{color:MK[k], width:1.5}, marker:{size:rr.map(r=>r.category==='anomalous'?11:6), color:rr.map(r=>r.category==='anomalous'?c.red:MK[k])},
       customdata:rr.map(r=>[r.category, r.explanation]), hovertemplate:k+' %{x}<br>ratio %{y:.2f}<br>%{customdata[0]}: %{customdata[1]}<extra></extra>'}; });
    Plotly.newPlot(el, tr, layout({shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:r0, y1:r0, line:{color:c.grey, dash:'dash'}}],
       yaxis:{gridcolor:c.line, title:platform==='google_ads'?'Google Ads ÷ GA4':'Meta ÷ back office'}}), cfg);
  };
  plot('rc_g', 'google_ads'); plot('rc_m', 'meta');
  const g = {};
  D.recon.filter(r=>m==='ALL' || r.market===m).forEach(r => { const key = r.platform+'|'+r.category+'|'+r.explanation; g[key] = (g[key]||0)+1; });
  table('rc_tbl', [['Platform', r=>r[0]], ['Category', r=>r[1]==='anomalous'?'<span class="bad">anomalous</span>':'<span class="ok">'+r[1]+'</span>'], ['Explanation', r=>r[2]], ['Market-weeks', r=>r[3]]],
     Object.entries(g).map(([k,v])=>[...k.split('|'), v]).sort((a,b)=>a[0].localeCompare(b[0])||b[3]-a[3]));
  table('rc_p', [['Market', r=>r.market], ['Platform', r=>r.platform], ['Back-office orders', r=>fmt(r.backend_orders)], ['Platform conversions', r=>fmt(r.platform_conversions)],
     ['Ratio', r=>fmt(r.ratio_vs_backend,2)], ['Category', r=>'<span class="ok">'+r.category+'</span>'], ['Why', r=>r.explanation]], D.recon_period.filter(r=>m==='ALL'||r.market===m));
}
function t4() {
  const c = C();
  Plotly.newPlot('u_ag', [{type:'bar', x:D.utm_agency.map(r=>r.agency), y:D.utm_agency.map(r=>r.pct_compliant), marker:{color:D.utm_agency.map(r=>r.pct_compliant<80?c.red:c.accent)},
     text:D.utm_agency.map(r=>fmt(r.pct_compliant,1)+'%'), textposition:'outside'}], layout({yaxis:{gridcolor:c.line, range:[0,105], ticksuffix:'%'}}), cfg);
  const mk = [...new Set(D.utm_weekly.map(r=>r.market))];
  Plotly.newPlot('u_wk', mk.map(k => { const rr = D.utm_weekly.filter(r=>r.market===k); return {type:'scatter', mode:'lines', name:k, x:rr.map(r=>r.week), y:rr.map(r=>r.pct_unassigned), line:{color:MK[k]}}; }),
     layout({yaxis:{gridcolor:c.line, ticksuffix:'%', rangemode:'tozero'}, shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:10, y1:10, line:{color:c.red, dash:'dash'}}]}), cfg);
  table('u_var', [['Platform', r=>r.platform], ['utm_source', r=>r.utm_source], ['utm_medium', r=>r.utm_medium||'<span class="bad">(missing)</span>'], ['Links', r=>r.links],
     ['Use', r=>r.source_normalised+' / '+r.medium_normalised]], D.utm_variants.filter(r=>r.platform==='meta' || !r.utm_medium));
  Plotly.newPlot('f_mk', [{type:'bar', name:'wrong currency', x:D.feed.map(r=>r.market), y:D.feed.map(r=>r.wrong_currency||0), marker:{color:c.red}},
     {type:'bar', name:'missing availability', x:D.feed.map(r=>r.market), y:D.feed.map(r=>r.missing_required||0), marker:{color:'#EDA100'}}],
     layout({barmode:'stack', yaxis:{gridcolor:c.line, title:'rows (of 300 per market)'}}), cfg);
}
function t5() {
  const c = C();
  const de = D.consent.filter(r=>r.market==='DE');
  const br = D.consent_breaks.filter(r=>r.market==='DE');
  Plotly.newPlot('mo_de', [{type:'scatter', mode:'lines', name:'sessions', x:de.map(r=>r.date), y:de.map(r=>r.sessions), line:{color:c.accent}},
     {type:'scatter', mode:'lines', name:'baseline (same weekday)', x:de.map(r=>r.date), y:de.map(r=>r.baseline), line:{color:c.grey, dash:'dot'}}],
     layout({shapes:br.map(b=>({type:'line', x0:b.start_date, x1:b.start_date, yref:'paper', y0:0, y1:1, line:{color:c.red, dash:'dash'}})),
       annotations:br.map((b,i)=>({x:b.start_date, yref:'paper', y:i%2?0.06:1, text:b.release_at_start.split(' ')[0]+' '+(b.mean_deviation>0?'+':'')+Math.round(b.mean_deviation*100)+'%', showarrow:false, xanchor:'left', font:{color:c.red}})),
       yaxis:{gridcolor:c.line}}), cfg);
  const mk = ['FR','ES','DE','IT'];
  Plotly.newPlot('mo_meta', mk.map(k => { const rr = D.meta_match.filter(r=>r.market===k); return {type:'scatter', mode:'lines', name:k, x:rr.map(r=>r.date), y:rr.map(r=>100*r.event_id_match_rate), line:{color:MK[k], width:k==='FR'?4:1.5, dash:k==='FR'?'dot':'solid'}}; }),
     layout({yaxis:{gridcolor:c.line, ticksuffix:'%', range:[-5,105]}, shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:90, y1:90, line:{color:c.red, dash:'dash'}}]}), cfg);
  const dests = ['ga4','meta_capi','google_ads','linkedin_capi'], col = {ga4:c.grey, meta_capi:c.red, google_ads:c.accent, linkedin_capi:'#7A5CD6'};
  Plotly.newPlot('mo_srv', dests.map(d => { const rr = D.hourly.filter(r=>r.destination===d); return {type:'scatter', mode:'lines', name:d, x:rr.map(r=>r.hour_utc), y:rr.map(r=>100*r.error_rate), line:{color:col[d], width:d==='meta_capi'?2.5:1}}; }),
     layout({yaxis:{gridcolor:c.line, ticksuffix:'%'}, shapes:[{type:'line', xref:'paper', x0:0, x1:1, y0:20, y1:20, line:{color:c.red, dash:'dash'}}]}), cfg);
  const it = D.dup_daily.filter(r=>r.market==='IT'), uk = D.selfref.filter(r=>r.scope==='UK');
  Plotly.newPlot('mo_dup', [{type:'scatter', mode:'lines', name:'IT duplicate purchase rate', x:it.map(r=>r.date), y:it.map(r=>100*r.duplicate_rate), line:{color:MK.IT}},
     {type:'scatter', mode:'lines', name:'UK purchases from own domain / payment provider', x:uk.map(r=>r.period), y:uk.map(r=>100*r.value), line:{color:MK.UK}}],
     layout({yaxis:{gridcolor:c.line, ticksuffix:'%'}}), cfg);
  table('mo_tbl', [['Check', r=>r[0]], ['PASS', r=>r[1]], ['WARN', r=>r[2]], ['FAIL', r=>r[3]? '<span class="bad">'+r[3]+'</span>' : 0]],
     Object.entries(D.status.reduce((a,r)=>{a[r.check]=a[r.check]||[0,0,0]; a[r.check][['PASS','WARN','FAIL'].indexOf(r.status)]++; return a;},{})).map(([k,v])=>[k,...v]));
}
function draw(t) { if (drawn[t]) return; drawn[t] = true; ({t1, t2, t3, t4, t5})[t](); }
draw('t1');
</script></body></html>"""


def main():
    import key_numbers                       # refresh data/out/key_numbers.json first (used here and by the PDF)
    (OUT / "key_numbers.json").write_text(json.dumps(key_numbers.build(), indent=1), encoding="utf-8")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    html = HTML.replace("__PLOTLY__", get_plotlyjs()).replace("__DATA__", json.dumps(data(), separators=(",", ":")))
    DEST.write_text(html, encoding="utf-8")
    print(f"dashboard -> {DEST.relative_to(ROOT)} ({DEST.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
