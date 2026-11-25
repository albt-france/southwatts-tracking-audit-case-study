-- 01 - Data-quality audit of the public GA4 sample (PUBLIC DATA)
-- Source: Google Merchandise Store obfuscated sample (BigQuery public dataset ga4_obfuscated_sample_ecommerce,
-- 2020-11-01 -> 2021-01-31), read from a flattened mirror (one row per event, event_params unnested).
-- Rulebook: GA4 recommended events - purchase must carry a unique transaction_id (Google documentation, read 2026-11-25).
-- No user_pseudo_id leaves this file: every output is aggregated.

CREATE OR REPLACE TEMP VIEW purchases AS
SELECT event_date, event_timestamp, ecom_revenue_usd AS revenue,
       NULLIF(NULLIF(TRIM(ecom_transaction_id), ''), '(not set)') AS tx
FROM ga4_real WHERE event_name = 'purchase';

CREATE OR REPLACE TEMP VIEW tx_counts AS
SELECT tx, COUNT(*) AS n, SUM(revenue) AS revenue FROM purchases WHERE tx IS NOT NULL GROUP BY tx;

-- output: real_audit_summary
SELECT * FROM (VALUES
  ('purchase_events',               (SELECT COUNT(*) FROM purchases)),
  ('distinct_transaction_ids',      (SELECT COUNT(DISTINCT tx) FROM purchases)),
  ('purchases_without_id',          (SELECT COUNT(*) FROM purchases WHERE tx IS NULL)),
  ('duplicated_ids',                (SELECT COUNT(*) FROM tx_counts WHERE n > 1)),
  ('extra_purchase_rows',           (SELECT SUM(n - 1) FROM tx_counts WHERE n > 1)),
  ('page_views',                    (SELECT COUNT(*) FROM ga4_real WHERE event_name = 'page_view')),
  ('page_views_self_referral',      (SELECT COUNT(*) FROM ga4_real WHERE event_name = 'page_view' AND ep_source ILIKE '%googlemerchandisestore%')),
  ('page_views_missing_medium',     (SELECT COUNT(*) FROM ga4_real WHERE event_name = 'page_view' AND (ep_medium IS NULL OR ep_medium = ''))),
  ('page_views_medium_data_deleted',(SELECT COUNT(*) FROM ga4_real WHERE event_name = 'page_view' AND ep_medium = '(data deleted)')),
  ('sessions',                      (SELECT COUNT(DISTINCT user_pseudo_id || '-' || ga_session_id) FROM ga4_real WHERE ga_session_id IS NOT NULL))
) t(metric, value);

-- output: real_audit_revenue_impact
SELECT ROUND(SUM(revenue), 2)                                            AS revenue_all_purchase_rows,
       ROUND(SUM(revenue) FILTER (WHERE tx IS NULL), 2)                  AS revenue_rows_without_id,
       ROUND((SELECT SUM(revenue - revenue / n) FROM tx_counts WHERE n > 1), 2) AS revenue_counted_twice,
       ROUND(100.0 * (SELECT SUM(revenue - revenue / n) FROM tx_counts WHERE n > 1) / SUM(revenue), 2) AS pct_revenue_counted_twice
FROM purchases;

-- output: real_audit_self_referral_sources
SELECT ep_source AS source, COUNT(*) AS page_views
FROM ga4_real WHERE event_name = 'page_view' AND ep_source ILIKE '%googlemerchandisestore%'
GROUP BY 1 ORDER BY 2 DESC;

-- output: real_audit_daily
WITH p AS (
  SELECT event_date, COUNT(*) AS purchases, COUNT(*) FILTER (WHERE tx IS NULL) AS without_id
  FROM purchases GROUP BY 1),
d AS (
  SELECT event_date, COUNT(*) - COUNT(DISTINCT tx) - COUNT(*) FILTER (WHERE tx IS NULL) AS extra_rows_same_day
  FROM purchases GROUP BY 1),
v AS (
  SELECT event_date, COUNT(*) AS page_views,
         COUNT(*) FILTER (WHERE ep_source ILIKE '%googlemerchandisestore%') AS self_referral,
         COUNT(*) FILTER (WHERE ep_medium IS NULL OR ep_medium = '') AS missing_medium
  FROM ga4_real WHERE event_name = 'page_view' GROUP BY 1)
SELECT strptime(v.event_date, '%Y%m%d')::DATE AS date, v.page_views,
       ROUND(v.self_referral / v.page_views, 4)  AS self_referral_share,
       ROUND(v.missing_medium / v.page_views, 4) AS missing_medium_share,
       COALESCE(p.purchases, 0) AS purchases, COALESCE(p.without_id, 0) AS purchases_without_id,
       COALESCE(d.extra_rows_same_day, 0) AS duplicate_rows_same_day
FROM v LEFT JOIN p USING (event_date) LEFT JOIN d USING (event_date)
ORDER BY 1;

-- output: real_audit_duplicate_gap
-- how far apart the copies of one transaction_id are (reloads are seconds/minutes, re-sends are days)
WITH x AS (
  SELECT tx, (MAX(event_timestamp) - MIN(event_timestamp)) / 1e6 AS gap_s
  FROM purchases WHERE tx IS NOT NULL GROUP BY tx HAVING COUNT(*) > 1)
SELECT CASE WHEN gap_s < 60 THEN '1: < 1 min' WHEN gap_s < 3600 THEN '2: 1-60 min'
            WHEN gap_s < 86400 THEN '3: 1-24 h' ELSE '4: > 1 day' END AS gap_bucket,
       COUNT(*) AS duplicated_ids
FROM x GROUP BY 1 ORDER BY 1;
