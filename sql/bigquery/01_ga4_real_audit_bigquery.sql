-- BigQuery version of sql/01_ga4_real_audit.sql, for the OFFICIAL GA4 export schema.
-- Not executed here (no Google Cloud account): written against the export schema documentation
-- (https://support.google.com/analytics/answer/7029846, read 2026-11-25).
-- Dataset: bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_* (2020-11-01 -> 2021-01-31).

-- 1. Purchases without a usable transaction_id, duplicated ids, extra rows
WITH purchases AS (
  SELECT event_date, event_timestamp,
         NULLIF(NULLIF(TRIM(ecommerce.transaction_id), ''), '(not set)') AS tx,
         ecommerce.purchase_revenue_in_usd AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131' AND event_name = 'purchase'
),
tx_counts AS (SELECT tx, COUNT(*) AS n FROM purchases WHERE tx IS NOT NULL GROUP BY tx)
SELECT
  (SELECT COUNT(*) FROM purchases)                         AS purchase_events,
  (SELECT COUNT(DISTINCT tx) FROM purchases)               AS distinct_transaction_ids,
  (SELECT COUNTIF(tx IS NULL) FROM purchases)              AS purchases_without_id,
  (SELECT COUNTIF(n > 1) FROM tx_counts)                   AS duplicated_ids,
  (SELECT SUM(n - 1) FROM tx_counts WHERE n > 1)           AS extra_purchase_rows;

-- 2. Self-referral and missing medium on page_view (source/medium are event parameters)
SELECT
  COUNT(*) AS page_views,
  COUNTIF((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source') LIKE '%googlemerchandisestore%') AS self_referral,
  COUNTIF((SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium') IS NULL)                        AS missing_medium
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131' AND event_name = 'page_view';
