"""Write and execute notebooks/tracking_audit.ipynb (one notebook, short outputs).
Order: real audit -> rulebook -> tracking plan -> simulation -> reconciliation -> anomalies -> monitoring.
It reads data/out (SQL, validator and monitoring outputs), so it runs without the raw GA4 extract.

    python src/build_notebook.py
"""
import subprocess
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks" / "tracking_audit.ipynb"

cells = [
    ("md", "# SouthWatts case study: a tracking stack you can trust\n"
           "Independent case study. **PUBLIC DATA**: Google's obfuscated GA4 sample (Google Merchandise Store, Nov 2020 - Jan 2021). "
           "**SIMULATED**: 12 weeks of a fictional multinational, Client M (8 markets, 5 platforms). "
           "All tables below are read from `data/out`, produced by `src/run_sql.py`, the validators and `src/monitoring.py`."),
    ("code", "import json, pandas as pd\nfrom pathlib import Path\nOUT = Path('..') / 'data' / 'out'\n"
             "pd.set_option('display.width', 140); pd.set_option('display.max_columns', 12)\n"
             "k = json.loads((OUT / 'key_numbers.json').read_text())\ncsv = lambda n: pd.read_csv(OUT / f'{n}.csv')"),
    ("md", "## 1. Real audit of the GA4 sample (PUBLIC DATA)\nQueries: `sql/01_ga4_real_audit.sql`, `sql/02_ga4_sessions_channels.sql`."),
    ("code", "csv('real_audit_summary')"),
    ("code", "csv('real_audit_revenue_impact')"),
    ("code", "csv('real_channels').head(6)"),
    ("md", "Reading: 906 purchases cannot be deduplicated (no id), 326 ids are sent twice (6.2% of revenue counted twice, "
           "mostly within one minute: reloads), and self-referral sessions hold almost a third of purchases."),
    ("md", "## 2. Rulebook: official sources read on 2026-11-25"),
    ("code", "csv_ref = pd.read_csv(Path('..') / 'data' / 'reference' / 'sources.csv')\n"
             "csv_ref[~csv_ref.source.str.startswith('nager')][['source', 'http_status', 'read_on', 'keywords_found']]"),
    ("code", "k['iab']"),
    ("md", "## 3. Tracking plan\n`tracking/tracking_plan.xlsx`, `tracking/datalayer.schema.json`, GTM templates. Tested by `tests/test_datalayer.py`."),
    ("code", "plan = pd.read_excel(Path('..') / 'tracking' / 'tracking_plan.xlsx')\nplan.groupby('event').parameter.count().rename('parameters')"),
    ("md", "## 4. Simulation (SIMULATED, Client M)"),
    ("code", "k['sim_rows']"),
    ("md", "## 5. Reconciliation: expected vs anomalous gaps"),
    ("code", "csv('reconciliation_headline')"),
    ("code", "csv('reconciliation_summary')[['platform', 'category', 'explanation', 'market_weeks', 'mean_ratio']]"),
    ("md", "Google Ads stays about 23% above GA4 in the baseline weeks: attribution model, 30-day window, click date. "
           "It is explained to the client, not fixed."),
    ("md", "## 6. Anomalies"),
    ("code", "csv('consent_breaks')[['market', 'dir', 'start_date', 'end_date', 'mean_deviation', 'release_at_start']]"),
    ("code", "csv('dedup_meta_breaks')"),
    ("code", "csv('utm_unassigned_summary')"),
    ("code", "csv('dedup_ga4_market').head(3)"),
    ("code", "csv('feed_validation_summary')"),
    ("code", "csv('server_alerts')"),
    ("md", "## 7. Monitoring"),
    ("code", "csv('monitoring_report').status.value_counts()"),
    ("code", "p = OUT / 'detection_summary.csv'\n"
             "csv('detection_summary')[['event', 'name', 'check', 'first_fail', 'detection_delay', 'found']] if p.exists() else 'answer key not available'"),
    ("code", "csv('tests_results')[['name', 'passed']]"),
]


def main():
    nb = nbf.v4.new_notebook()
    nb.cells = [nbf.v4.new_markdown_cell(c) if t == "md" else nbf.v4.new_code_cell(c) for t, c in cells]
    nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"}}
    NB.parent.mkdir(exist_ok=True)
    nbf.write(nb, NB)
    subprocess.run([sys.executable, "-m", "nbconvert", "--to", "notebook", "--execute", "--inplace", str(NB)], check=True,
                   cwd=NB.parent, capture_output=True)
    print(f"notebook executed -> {NB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
