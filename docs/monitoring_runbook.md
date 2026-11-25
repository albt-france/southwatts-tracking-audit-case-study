# Monitoring runbook

Checks run by [`src/monitoring.py`](../src/monitoring.py) on the simulated data of the fictional Client M.
Output: `data/out/monitoring_report.csv` (PASS / WARN / FAIL per check, period and scope). Thresholds are
starting values: tune them after a month of history.

| Check | Grain | WARN | FAIL | Who is alerted | First things to look at |
|---|---|---|---|---|---|
| `sessions_vs_baseline` | day × market | ±12% | ±25% | tracking specialist | deploy log of the day, consent share, holidays |
| `pre_consent_hits` | day × market | - | any | tracking specialist + privacy contact | last web container version, consent banner release |
| `ga4_duplicate_purchases` | day × market | > 1% | > 3% | tracking specialist | confirmation page reload, guard on `transaction_id` |
| `meta_event_id_match` | day × market | < 98% | < 90% | tracking specialist + media agency | server tag `event_id` mapping, last server/web release |
| `purchase_self_referral` | day × market | > 2% | > 5% | tracking specialist | payment provider change, linker domains, referral exclusions |
| `paid_unassigned_share` | week × market | > 5% | > 10% | agency owning the links | UTM validator output for the agency |
| `platform_reconciliation` | week × market × platform | - | anomalous | tracking specialist | `reconciliation_weekly.csv`: which signal fired |
| `server_error_rate` | hour × destination | > 5% | > 20% (≥ 10 events) | on-call tracking + hosting | server container logs, last server release, platform status |
| `feed_quality` | snapshot × market | - | any disapproval risk | feed owner | validator output, last product-system export |

## Rules

- An expected gap (for example Google Ads above GA4 because of attribution) is **PASS** with its explanation:
  alerts are for things someone must fix.
- Hourly check for the server container: a daily total hides night incidents. In the simulation, the Meta CAPI outage
  of 5 Nov (02:00-09:00 UTC) leaves the day's Meta conversions at +12.8% vs the same weekday, inside the normal
  daily range (−26% to +24%); the hourly check raised it at **03:00**, one hour after the start.
- Each FAIL gets an owner and a ticket; closing the ticket requires the check back to PASS.
- After any container release: watch `sessions_vs_baseline`, `pre_consent_hits` and `server_error_rate` for 24 h.

## Simulation result

10,607 checks over 12 weeks: 357 FAIL, 171 WARN. All 8 planted events are found; the Google Ads gap is correctly
**not** raised as a bug. Detection time: same hour for the server outage, one day for the daily checks.
