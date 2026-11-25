-- 04 - Deduplication checks (SIMULATED, Client M)
-- GA4: one purchase per transaction_id (GA4 recommended events, read 2026-11-25).
-- Meta: pixel and Conversions API events of the same action must share event_id (and event_name) to be
-- deduplicated (Meta documentation "Deduplicate pixel and server events", read 2026-11-25).

-- output: dedup_ga4_daily
SELECT event_date AS date, market,
       COUNT(*) AS purchase_events,
       COUNT(DISTINCT transaction_id) AS unique_transactions,
       COUNT(*) - COUNT(DISTINCT transaction_id) AS duplicate_rows,
       ROUND((COUNT(*) - COUNT(DISTINCT transaction_id)) / COUNT(*), 4) AS duplicate_rate
FROM ga4_events WHERE event_name = 'purchase'
GROUP BY ALL ORDER BY 1, 2;

-- output: dedup_ga4_market
SELECT market, COUNT(*) AS purchase_events, COUNT(DISTINCT transaction_id) AS unique_transactions,
       ROUND(100.0 * (COUNT(*) - COUNT(DISTINCT transaction_id)) / COUNT(DISTINCT transaction_id), 2) AS pct_extra_purchases,
       COUNT(*) FILTER (WHERE transaction_id IS NULL) AS without_transaction_id
FROM ga4_events WHERE event_name = 'purchase' GROUP BY 1 ORDER BY 4 DESC, 1;

CREATE OR REPLACE TEMP VIEW meta_pairs AS
SELECT p.order_id, p.market, CAST(p.ts AS DATE) AS date, p.event_id AS pixel_event_id, s.event_id AS capi_event_id
FROM pixel_events p
JOIN server_events s ON s.order_id = p.order_id AND s.destination = 'meta_capi' AND s.event_name = 'Purchase'
WHERE p.destination = 'meta_pixel' AND p.event_name = 'Purchase';

-- output: dedup_meta_daily
SELECT date, market, COUNT(*) AS orders_seen_by_both,
       COUNT(*) FILTER (WHERE pixel_event_id = capi_event_id) AS same_event_id,
       ROUND(COUNT(*) FILTER (WHERE pixel_event_id = capi_event_id) / COUNT(*), 4) AS event_id_match_rate
FROM meta_pairs GROUP BY ALL ORDER BY 1, 2;

-- output: dedup_meta_breaks
-- first day where the match rate falls under 90% and stays there (per market)
WITH d AS (
  SELECT market, date, SUM(same_event_id) / SUM(orders_seen_by_both) AS rate
  FROM (SELECT date, market, COUNT(*) AS orders_seen_by_both,
               COUNT(*) FILTER (WHERE pixel_event_id = capi_event_id) AS same_event_id
        FROM meta_pairs GROUP BY ALL) GROUP BY ALL),
low AS (SELECT market, MIN(date) AS first_low_day, COUNT(*) AS low_days FROM d WHERE rate < 0.90 GROUP BY 1)
SELECT l.market, l.first_low_day, l.low_days,
       ROUND((SELECT AVG(rate) FROM d WHERE d.market = l.market AND d.date < l.first_low_day), 3) AS match_rate_before,
       ROUND((SELECT AVG(rate) FROM d WHERE d.market = l.market AND d.date >= l.first_low_day), 3) AS match_rate_after,
       (SELECT STRING_AGG(version || ' (' || change || ')', '; ') FROM deploy_log
         WHERE (market_scope = 'ALL' OR market_scope LIKE '%' || l.market || '%')
           AND CAST(date AS DATE) BETWEEN l.first_low_day - 1 AND l.first_low_day) AS release_same_day
FROM low l ORDER BY 1;
