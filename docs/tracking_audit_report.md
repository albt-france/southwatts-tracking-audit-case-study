# Tracking audit report: public GA4 sample (PUBLIC DATA)

**Data**: Google Merchandise Store, obfuscated GA4 sample (BigQuery public dataset `ga4_obfuscated_sample_ecommerce`,
1 Nov 2020 to 31 Jan 2021), read from a flattened public mirror on Hugging Face (2,065,852 events kept:
`session_start`, `first_visit`, `page_view`, `add_to_cart`, `begin_checkout`, `purchase`). This is Google's
public demo dataset. It is **not** a client and says nothing about SouthWatts or its clients.
Queries: [`sql/01_ga4_real_audit.sql`](../sql/01_ga4_real_audit.sql), [`sql/02_ga4_sessions_channels.sql`](../sql/02_ga4_sessions_channels.sql)
and the BigQuery versions in [`sql/bigquery/`](../sql/bigquery/).

**Rulebook**: GA4 recommended events reference (`purchase` carries a unique `transaction_id`), GA4 BigQuery export
schema (read 2026-11-25).

## Findings

| # | Finding | Count | Severity | What it distorts | Fix |
|---|---|---|---|---|---|
| 1 | `purchase` without a usable `transaction_id` (empty or `(not set)`) | **906** of 5,692 purchase events (15.9%) | High | Revenue cannot be deduplicated or joined to the back office; Google Ads `order_id` deduplication impossible | Make `transaction_id` required in the dataLayer schema; block the tag when it is empty (trigger condition) |
| 2 | Same `transaction_id` sent more than once | **326** ids, 335 extra events; 288 of the 326 within one minute | High | Purchases and revenue overstated: **6.23%** of purchase revenue counted twice (USD 22,577 of 362,165) | Fire `purchase` once per id (localStorage guard on the confirmation page), deduplicate in reporting queries |
| 3 | Self-referral: the shop's own domains as traffic source | **206,005** page views (15.3%); 35,065 sessions (9.7%) start this way and hold **29.7%** of purchases | High | Conversions are credited to "referral from ourselves" instead of the real channel; paid media under-credited | Add own domains (and payment provider) to the list of unwanted referrals; set up cross-domain measurement; check redirects that drop the `_gl` linker |
| 4 | `page_view` without `medium` | 866,938 (64.2%) | Low (by design) | Analysts who read source/medium on every event get wrong channel splits | Attribution is session-scoped: take the first non-empty source/medium of the session (as in query 02) |
| 5 | `(data deleted)` medium | 8,811 page views | Info | Small, unrecoverable gap | Document it; exclude from trend comparisons |
| 6 | Obfuscated values (`<Other>`) | 6.9% of sessions | Info | The sample is obfuscated on purpose | Not a tracking bug: a property of the public sample |

## Reading

- The duplicate pattern (most copies within one minute) points to **reloads of the confirmation page**,
  not to back-end re-sends: the fix belongs in the tag (once per `transaction_id`), not in the order system.
- Self-referral is the most expensive finding: almost **one purchase in three** sits in a session whose source is
  the shop itself. Whatever channel brought those users loses the credit, which then shows up as a
  "GA4 vs ad platform" gap.
- Self-referral is not constant: it is 22.1% of page views until 29 Dec 2020 and 1.6% after. A break on one day
  is the signature of a configuration change (referral exclusion, linker, redirect); its cause is not in the data.
  This is exactly what daily monitoring should date and match with a release log.
- Finding 4 is a reminder of the GA4 data model: `event_params` are event-scoped, and only some events carry
  `source`/`medium`. Not a bug, but a common cause of wrong reports.

## Limits

The sample is obfuscated and partial (Google says so); counts are about the sample, not about a real store's
current setup. The mirror is a flattened copy of the official table, used because the official one needs a
Google Cloud account.
