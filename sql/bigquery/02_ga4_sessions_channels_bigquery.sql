-- BigQuery version of sql/02_ga4_sessions_channels.sql, for the OFFICIAL GA4 export schema.
-- Not executed here (no Google Cloud account). Session = user_pseudo_id + ga_session_id (event parameter).
-- Session source/medium = first non-null value in the session. Output is aggregated: no user_pseudo_id leaves the query.

WITH ev AS (
  SELECT user_pseudo_id, event_timestamp, event_name,
         (SELECT value.int_value    FROM UNNEST(event_params) WHERE key = 'ga_session_id') AS ga_session_id,
         (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'source')        AS source,
         (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'medium')        AS medium,
         NULLIF(NULLIF(ecommerce.transaction_id, ''), '(not set)')                          AS tx
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE _TABLE_SUFFIX BETWEEN '20201101' AND '20210131'
),
sessions AS (
  SELECT CONCAT(user_pseudo_id, '-', CAST(ga_session_id AS STRING)) AS session_key,
         ARRAY_AGG(source IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS source,
         ARRAY_AGG(medium IGNORE NULLS ORDER BY event_timestamp LIMIT 1)[SAFE_OFFSET(0)] AS medium,
         COUNT(DISTINCT IF(event_name = 'purchase', tx, NULL)) AS purchases
  FROM ev WHERE ga_session_id IS NOT NULL
  GROUP BY session_key
)
SELECT CASE
         WHEN source LIKE '%googlemerchandisestore%' THEN 'Self-referral (bug)'
         WHEN source = '(direct)' AND medium IN ('(none)', '(not set)') THEN 'Direct'
         WHEN medium = 'organic' THEN 'Organic Search'
         WHEN medium IN ('cpc', 'ppc') THEN 'Paid Search'
         WHEN medium = 'referral' THEN 'Referral'
         WHEN source IS NULL AND medium IS NULL THEN 'No source on any event'
         ELSE 'Other / Unassigned' END AS channel,
       COUNT(*) AS sessions, SUM(purchases) AS purchases
FROM sessions GROUP BY channel ORDER BY sessions DESC;

-- Example asked in interviews: unique purchases by session source (deduplicated on transaction_id)
-- SELECT s.source, COUNT(DISTINCT e.tx) AS unique_purchases
-- FROM ev e JOIN sessions s ON s.session_key = CONCAT(e.user_pseudo_id, '-', CAST(e.ga_session_id AS STRING))
-- WHERE e.event_name = 'purchase' AND e.tx IS NOT NULL GROUP BY s.source ORDER BY unique_purchases DESC;
