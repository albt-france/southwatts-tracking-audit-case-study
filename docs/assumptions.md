# Assumptions (simulation of the fictional Client M)

Everything below is **SIMULATED** (`src/simulate_tracking.py`, seed 42). Client M is fictional. No internal data of
SouthWatts or of any of its clients is used or guessed.

## Scope

- 8 markets (FR, DE, ES, IT, UK, NL, PL, US), 84 days (2026-09-01 to 2026-11-23), about 48,000 sessions a day in total
  (4.08 million sessions, 52,768 orders, 3.35 million GA4 events, 769,944 server deliveries).
- 5 platforms: GA4, Google Ads, Meta, LinkedIn (5 markets), CM360. 3 agencies: AGY1 (Google), AGY2 (Meta, LinkedIn), AGY3 (CM360).

## Calibration

- Purchase rate: 1.29 orders per 100 sessions, close to the public GA4 sample (1.24 purchase sessions per 100 sessions).
- Consent acceptance by market between 62% (DE) and 95% (US); GA4 and ad tags only record sessions with consent
  (simplified basic Consent Mode; no modelling).
- Browser pixels blocked for 12% of consented sessions (ad blockers, browser restrictions).
- Weekday pattern, hourly profile in local time (summer/winter time handled), public holidays (`date.nager.at`, −20%).

## Platform rules (hypotheses, not defaults read in documentation)

| Platform | Window | Model | Simulated effect |
|---|---|---|---|
| Google Ads | 30-day click | data-driven | 1.22 conversion credit per consented paid-search order, reported on click date (lag 0-21 days) |
| Meta | 7-day click, 1-day view | platform default | one conversion per distinct `event_id` received for an attributed order; view-through on 2% of other orders |
| LinkedIn | 30-day click, 7-day view | last touch | 1.3 × consented LinkedIn orders |
| CM360 | 30-day click, 30-day view | last interaction | display orders + 5% of all consented orders (post-view) |

## Planted events (answer key kept out of the repository)

Eight events are planted (consent release, Meta double counting, UTMs, duplicate purchases, cross-domain, an
**expected** Google Ads gap, feed errors, server outage). Their effects are described in the PDF and in
`docs/monitoring_runbook.md`; the answer key file used to score detection is local only.

## Thresholds

Monitoring thresholds and the 3-standard-error rule of the reconciliation are starting points chosen for this
study, documented in `docs/monitoring_runbook.md` and `sql/03_platform_reconciliation.sql`.
