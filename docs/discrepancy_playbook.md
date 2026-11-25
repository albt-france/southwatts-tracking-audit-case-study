# Discrepancy playbook: "GA4 does not match the ad platform"

A gap between GA4 and an ad platform is **normal** until proven otherwise. The job is to separate the expected
part (different rules) from the broken part (a tracking bug), and to say which is which with evidence.

## Step 0: frame the question

- Same metric? (GA4 `purchase` / key event vs platform "conversions", which may include several actions.)
- Same dates? Platforms often report on **click / impression date**, GA4 on **event date**.
- Same scope? (market, campaign, currency, time zone of each account.)
- Compare to the **back office** (orders), the only source that is not a model.

## Step 1: is the gap stable?

Compute the ratio platform / GA4 (or platform / back office) per week and market, and compare to a baseline
(4 clean weeks). A ratio that is stable over time is a rules difference; a ratio that **moves** at a date is
a change: look for the release.

## Step 2: diagnostic tree

| Question | How to check | If yes |
|---|---|---|
| Different attribution model? | Platform data-driven / view-through vs GA4 last non-direct click | **Expected**: explain, do not fix |
| Different window? | Platform 30-day click / 1-day view vs GA4 lookback | **Expected** |
| Click date vs event date? | Recent weeks lower on the platform, catch up later | **Expected** (wait or compare older weeks) |
| Consent? | Share of hits before the choice; sessions vs baseline around a consent release | **Bug** if hits go out before the choice or everything is blocked |
| Deduplication (platform side)? | Pixel `eventID` vs server `event_id` on the same order | **Bug** if they differ: double counting |
| Deduplication (GA4 side)? | Same `transaction_id` sent twice | **Bug**: purchase fired on reload |
| Cross-domain? | Share of purchases whose source is the shop or the payment provider | **Bug**: credit stolen from paid channels |
| UTM? | Share of paid sessions in Unassigned, by agency | **Bug** (process): fix links, add mapping |
| Time zone? | Accounts in different time zones: day totals shift | **Expected**: compare weeks, not days |
| Currency? | Value in account currency vs GA4 reporting currency | **Expected** if converted; **bug** if a feed or tag sends the wrong currency |
| Server container down? | Hourly error rate per destination | **Bug**: incident, replay if the platform allows it |

## Step 3: classify and write it down

For each market-week: `expected` (with the reason) or `anomalous` (with the signal that proves it). A ratio
far from the baseline with **no** signal is `unexplained` and stays open. Query: [`sql/03_platform_reconciliation.sql`](../sql/03_platform_reconciliation.sql).

## Step 4: tell the client

- Expected gaps: a short note (why the numbers differ, which number to use for what) and the reconciliation table.
- Bugs: what, since when, which markets, impact in conversions, fix, how we will know it is fixed.

## Exercise

The simulated data of this repository contains a Meta double-counting case. Try to find it with this playbook
(start from `data/out/reconciliation_weekly.csv` and `data/out/dedup_meta_daily.csv`) before reading the answer in
the PDF report, page 4.

<details>
<summary><b>Solution of the exercise (read after trying)</b></summary>

1. **Symptom**: from the week of 5 October, Meta ÷ back-office orders jumps in FR and ES (about 0.83 → 1.59, ×1.9)
   while the other markets stay near the baseline (0.87). GA4 and the back office do not move: the extra conversions
   exist only on the Meta side.
2. **Not expected**: attribution, window or consent would move all markets and would not start on one day.
3. **Signal**: `dedup_meta_daily.csv`: for orders seen by both the pixel and the Conversions API, the share with the
   same `event_id` falls from 100% to 0% on 2026-10-07, in FR and ES only.
4. **Cause**: the deploy log shows `web-v40` on 2026-10-07 for FR and ES: "Move Meta Purchase to the server container
   (new CAPI tag)". The new server tag generates its own id instead of forwarding the browser `event_id`, so Meta
   cannot deduplicate and counts the purchase twice when both paths deliver.
5. **Fix**: map `event_id` in the server tag to the incoming event data (`{{ED - event_id}}`), check in the Meta
   test events tool that browser and server events show as deduplicated, and keep the daily `meta_event_id_match`
   check (FAIL under 90%).
6. **Tell the client**: Meta purchases in FR and ES were overstated by about 90% from 7 October; trend back to normal
   after the fix; back-office orders were never affected.

</details>
