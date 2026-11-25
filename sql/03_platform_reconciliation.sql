-- 03 - Platform reconciliation: back office vs GA4 vs ad platforms (SIMULATED, Client M)
-- Grain: market x full week (2026-09-07 -> 2026-11-22) for Google Ads and Meta; market x whole period for
-- LinkedIn and CM360 (too few conversions per week to read a weekly ratio).
-- Comparison: Google Ads vs GA4 (what clients compare), Meta / LinkedIn / CM360 vs back-office orders.
-- Expected ratio r0 = pooled ratio of the 4 baseline weeks (before 2026-10-05). A gap is "expected" when the
-- ratio stays within 3 standard errors of r0 (Poisson error on both counts). A gap beyond 2 standard errors
-- in the direction a diagnostic signal predicts (same market and week) is "anomalous" and takes that cause;
-- beyond 3 standard errors with no signal it would be "unexplained". Outside the band the gap is
-- "anomalous" and gets the cause given by an independent diagnostic signal of the same market and week.
-- A gap with no signal would stay "unexplained" (99_tests.sql requires 0).

CREATE OR REPLACE TEMP VIEW plat_map AS
SELECT * FROM (VALUES ('paid_search','google_ads'), ('shopping','google_ads'), ('paid_social','meta'),
                      ('linkedin','linkedin'), ('display','cm360')) t(channel, platform);

CREATE OR REPLACE TEMP VIEW ga4_p AS
SELECT market, date_trunc('week', event_date) AS week,
       CASE WHEN LOWER(source) = 'google' AND LOWER(medium) = 'cpc' THEN 'google_ads'
            WHEN LOWER(source) IN ('meta', 'facebook', 'fb') THEN 'meta'
            WHEN LOWER(source) = 'linkedin' THEN 'linkedin'
            WHEN LOWER(source) = 'cm360' THEN 'cm360' END AS platform,
       COUNT(DISTINCT transaction_id) AS ga4_purchases          -- deduplicated on transaction_id
FROM ga4_events WHERE event_name = 'purchase' GROUP BY ALL;

CREATE OR REPLACE TEMP VIEW bo_p AS
SELECT o.market, date_trunc('week', o.order_date) AS week, m.platform, COUNT(*) AS backend_orders
FROM orders_backend o JOIN plat_map m ON m.channel = o.channel_claimed GROUP BY ALL;

CREATE OR REPLACE TEMP VIEW pf_p AS
SELECT market, date_trunc('week', date) AS week, platform, SUM(conversions) AS platform_conversions
FROM platform_conversions GROUP BY ALL;

CREATE OR REPLACE TEMP VIEW weekly AS
SELECT b.market, b.week, b.platform, b.backend_orders, COALESCE(g.ga4_purchases, 0) AS ga4_purchases,
       COALESCE(p.platform_conversions, 0) AS platform_conversions
FROM bo_p b LEFT JOIN ga4_p g USING (market, week, platform) LEFT JOIN pf_p p USING (market, week, platform)
WHERE b.week BETWEEN DATE '2026-09-07' AND DATE '2026-11-16';

-- diagnostic signals, computed without looking at the platforms
-- (same definitions as 04_dedup_checks.sql and 06_consent_and_deploys.sql, recomputed here so 03 runs on its own)
CREATE OR REPLACE TEMP VIEW sig_sess AS
SELECT event_date AS date, market, COUNT(*) AS sessions, AVG((consent_state = 'pre_choice')::INT) AS pre_choice
FROM ga4_events WHERE event_name = 'session_start' GROUP BY ALL;

CREATE OR REPLACE TEMP VIEW sig_base AS
SELECT market, dayofweek(date) AS dow, MEDIAN(sessions) AS baseline
FROM sig_sess x WHERE date BETWEEN DATE '2026-09-07' AND DATE '2026-10-04'
  AND NOT EXISTS (SELECT 1 FROM holidays h WHERE h.market = x.market AND h.date = x.date)
GROUP BY ALL;

CREATE OR REPLACE TEMP VIEW signals AS
WITH c AS (
  SELECT market, date_trunc('week', event_date) AS week,
         ABS(COUNT(*) FILTER (WHERE event_name = 'session_start') * 1.0) AS sessions,
         AVG(CASE WHEN event_name = 'purchase' AND (source LIKE '%clientm.example' OR source LIKE 'pay.%') THEN 1.0
                  WHEN event_name = 'purchase' THEN 0.0 END) AS psp_or_self_ref_share
  FROM ga4_events GROUP BY ALL),
s AS (
  SELECT x.market, date_trunc('week', x.date) AS week, AVG(ABS(x.sessions / b.baseline - 1)) AS consent_dev, AVG(x.pre_choice) AS pre_choice
  FROM sig_sess x JOIN sig_base b ON b.market = x.market AND b.dow = dayofweek(x.date)
  WHERE NOT EXISTS (SELECT 1 FROM holidays h WHERE h.market = x.market AND h.date = x.date) GROUP BY ALL),
d AS (
  SELECT p.market, date_trunc('week', p.ts) AS week, AVG((p.event_id = s.event_id)::INT) AS meta_match
  FROM pixel_events p
  JOIN server_events s ON s.order_id = p.order_id AND s.destination = 'meta_capi' AND s.event_name = 'Purchase'
  WHERE p.destination = 'meta_pixel' AND p.event_name = 'Purchase' GROUP BY ALL),
e AS (
  SELECT market, date_trunc('week', ts) AS week, AVG((status <> 'ok')::INT) AS capi_error_rate
  FROM server_events WHERE destination = 'meta_capi' GROUP BY ALL)
SELECT c.market, c.week, c.psp_or_self_ref_share, s.consent_dev, s.pre_choice, d.meta_match, e.capi_error_rate
FROM c LEFT JOIN s USING (market, week) LEFT JOIN d USING (market, week) LEFT JOIN e USING (market, week);

CREATE OR REPLACE TEMP VIEW scored AS
WITH x AS (
  SELECT *, platform_conversions AS num,
         CASE WHEN platform = 'google_ads' THEN ga4_purchases ELSE backend_orders END AS den,
         CASE WHEN platform = 'google_ads' THEN 'GA4 purchases' ELSE 'back-office orders' END AS compared_with
  FROM weekly WHERE platform IN ('google_ads', 'meta')),
r0 AS (SELECT platform, SUM(num) / SUM(den) AS r0 FROM x WHERE week < DATE '2026-10-05' GROUP BY 1)
SELECT x.*, r0.r0, ROUND(x.num / NULLIF(x.den, 0), 3) AS ratio,
       (x.num / NULLIF(x.den, 0) - r0.r0) / (r0.r0 * SQRT(1.0 / GREATEST(x.den, 1) + 1.0 / GREATEST(x.num, 1))) AS z
FROM x JOIN r0 USING (platform);

-- output: reconciliation_weekly
SELECT s.market, s.week, s.platform, s.backend_orders, s.ga4_purchases, s.platform_conversions, s.compared_with,
       s.ratio, ROUND(s.r0, 3) AS expected_ratio, ROUND(s.z, 2) AS z,
       CASE WHEN s.platform = 'google_ads' AND s.z > 2 AND (g.consent_dev > 0.12 OR g.psp_or_self_ref_share > 0.05) THEN 'anomalous'
            WHEN s.platform = 'meta' AND s.z > 2 AND g.meta_match < 0.90 THEN 'anomalous'
            WHEN s.platform = 'meta' AND s.z < -2 AND g.capi_error_rate > 0.02 THEN 'anomalous'
            WHEN ABS(s.z) <= 3 THEN 'expected'
            WHEN s.platform = 'google_ads' AND s.z < -3 AND s.week >= DATE '2026-11-09' THEN 'expected'
            ELSE 'unexplained' END AS category,
       CASE WHEN s.platform = 'google_ads' AND s.z > 2 AND g.psp_or_self_ref_share > 0.05 THEN 'GA4 side broken: cross-domain (payment provider / self-referral)'
            WHEN s.platform = 'google_ads' AND s.z > 2 AND g.consent_dev > 0.12 THEN 'GA4 side broken: consent mode release (see consent_breaks)'
            WHEN s.platform = 'meta' AND s.z > 2 AND g.meta_match < 0.90 THEN 'Meta side broken: pixel and CAPI event_id differ (double counting)'
            WHEN s.platform = 'meta' AND s.z < -2 AND g.capi_error_rate > 0.02 THEN 'Meta side broken: server container outage'
            WHEN ABS(s.z) <= 3 AND s.platform = 'google_ads' THEN 'attribution model (data-driven vs last non-direct click), 30-day window, click date'
            WHEN ABS(s.z) <= 3 AND s.platform = 'meta' THEN 'view-through credit and consent: within normal range'
            WHEN s.platform = 'google_ads' AND s.z < -3 AND s.week >= DATE '2026-11-09' THEN 'recent clicks: conversions still arriving (click-date reporting)'
            ELSE 'no diagnostic signal' END AS explanation,
       ROUND(g.consent_dev, 3) AS signal_consent_dev, ROUND(g.psp_or_self_ref_share, 3) AS signal_psp_share,
       ROUND(g.meta_match, 3) AS signal_meta_match, ROUND(g.capi_error_rate, 4) AS signal_capi_errors
FROM scored s LEFT JOIN signals g USING (market, week)
ORDER BY s.platform, s.market, s.week;

-- output: reconciliation_period
-- LinkedIn and CM360: whole period per market (view-through windows make them far above back office by design)
WITH x AS (
  SELECT market, platform, SUM(backend_orders) AS backend_orders, SUM(ga4_purchases) AS ga4_purchases,
         SUM(platform_conversions) AS platform_conversions
  FROM weekly WHERE platform IN ('linkedin', 'cm360') GROUP BY ALL),
r0 AS (SELECT platform, SUM(platform_conversions) / SUM(backend_orders) AS r0 FROM x GROUP BY 1)
SELECT x.*, ROUND(platform_conversions / backend_orders, 3) AS ratio_vs_backend, ROUND(r0, 3) AS expected_ratio,
       ROUND((platform_conversions / backend_orders - r0) / (r0 * SQRT(1.0 / backend_orders + 1.0 / GREATEST(platform_conversions, 1))), 2) AS z,
       CASE WHEN ABS((platform_conversions / backend_orders - r0) / (r0 * SQRT(1.0 / backend_orders + 1.0 / GREATEST(platform_conversions, 1)))) <= 3
            THEN 'expected' ELSE 'unexplained' END AS category,
       CASE platform WHEN 'linkedin' THEN 'consented orders only, longer window (30-day click / 7-day view): noisy at low volume'
                     ELSE 'post-view conversions: display gets credit for orders it did not drive' END AS explanation
FROM x JOIN r0 USING (platform) ORDER BY platform, market;

-- output: reconciliation_summary
SELECT platform, category, explanation, COUNT(*) AS market_weeks,
       ROUND(AVG(ratio), 3) AS mean_ratio, MIN(ratio) AS min_ratio, MAX(ratio) AS max_ratio
FROM read_csv_auto('data/out/reconciliation_weekly.csv')
GROUP BY ALL ORDER BY platform, category, market_weeks DESC;

-- output: reconciliation_headline
SELECT platform,
       ROUND(SUM(platform_conversions) FILTER (WHERE category = 'expected') / SUM(CASE WHEN platform = 'google_ads' THEN ga4_purchases ELSE backend_orders END) FILTER (WHERE category = 'expected') - 1, 3) AS gap_when_expected,
       COUNT(*) FILTER (WHERE category = 'anomalous') AS anomalous_market_weeks,
       COUNT(*) FILTER (WHERE category = 'unexplained') AS unexplained_market_weeks,
       COUNT(*) AS market_weeks
FROM read_csv_auto('data/out/reconciliation_weekly.csv') GROUP BY 1 ORDER BY 1;
