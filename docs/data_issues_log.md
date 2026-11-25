# Data issues log

| # | Source | Issue | Impact | Handling |
|---|---|---|---|---|
| 1 | GA4 public sample | Obfuscated on purpose (`<Other>`, `(data deleted)`), partial | Counts describe the sample only | Stated on every visual (PUBLIC DATA) and in the limits |
| 2 | GA4 public sample | Read from a flattened mirror on Hugging Face (MIT licence of the mirror), not from BigQuery | Column names differ from the official export (`ep_source` = `event_params.source`) | BigQuery versions of queries 01 and 02 written for the official schema (`sql/bigquery/`, not executed: no account) |
| 3 | GA4 public sample | 906 purchases without id, 326 duplicated ids | Revenue deduplication impossible for 15.9% of purchase events | Distinct counts use only usable ids; extra rows reported separately |
| 4 | GA4 public sample | 4,451 distinct usable ids (4,452 if `(not set)` is counted as an id) | Small difference with naive counts | Empty and `(not set)` are treated as missing |
| 5 | GA4 public sample | `source`/`medium` are event parameters present on some events only | Event-level channel counts are wrong | Session source = first non-empty value of the session (query 02) |
| 6 | Simulation | Weekly volumes per market are small for LinkedIn and CM360 | Weekly ratios too noisy | Reconciled over the whole period per market |
| 7 | Simulation | Google Ads reports on click date | Last 2 weeks look low vs GA4 | Classified as expected (reporting lag) when the ratio is low in the last two weeks |
| 8 | Simulation | The Meta CAPI outage happens at night | Invisible in daily Meta totals | Hourly error-rate check (documented in the runbook) |
| 9 | Documentation pages | Pages change over time | A cited rule may move | Every rule cited with URL and read date (2026-11-25); `data/reference/sources.csv` keeps HTTP status and keyword checks |
| 10 | Holidays | `date.nager.at`, global holidays only | Regional holidays ignored | Accepted: holidays only reduce the sessions baseline noise |
