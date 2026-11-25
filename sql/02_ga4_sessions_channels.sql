-- 02 - Sessions and channels rebuilt from events, as in the GA4 BigQuery export (PUBLIC DATA)
-- A session = user_pseudo_id + ga_session_id. Its source/medium = the first non-empty source/medium of the session.
-- Channel rules are a simplified version of a default channel grouping, written for this study (documented in
-- docs/utm_governance.md); they are not Google's exact rules.

CREATE OR REPLACE TEMP VIEW real_sessions AS
SELECT user_pseudo_id || '-' || ga_session_id AS session_key,
       MIN(strptime(event_date, '%Y%m%d')::DATE) AS date,
       ARG_MIN(ep_source, CASE WHEN ep_source IS NOT NULL THEN event_timestamp END) AS source,
       ARG_MIN(ep_medium, CASE WHEN ep_medium IS NOT NULL THEN event_timestamp END) AS medium,
       COUNT(DISTINCT NULLIF(NULLIF(ecom_transaction_id, ''), '(not set)')) FILTER (WHERE event_name = 'purchase') AS purchases
FROM ga4_real WHERE ga_session_id IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE TEMP VIEW real_sessions_ch AS
SELECT *, CASE
    WHEN source ILIKE '%googlemerchandisestore%'          THEN 'Self-referral (bug)'
    WHEN source = '(data deleted)' OR medium = '(data deleted)' THEN 'Data deleted'
    WHEN source = '(direct)' AND medium IN ('(none)', '(not set)') THEN 'Direct'
    WHEN medium = 'organic'                                THEN 'Organic Search'
    WHEN medium IN ('cpc', 'ppc')                          THEN 'Paid Search'
    WHEN medium = 'referral'                               THEN 'Referral'
    WHEN medium IN ('affiliate')                           THEN 'Affiliates'
    WHEN medium IN ('email')                               THEN 'Email'
    WHEN source IS NULL AND medium IS NULL                 THEN 'No source on any event'
    WHEN source = '<Other>' OR medium = '<Other>'          THEN 'Obfuscated (<Other>)'
    ELSE 'Unassigned' END AS channel
FROM real_sessions;

-- output: real_channels
SELECT channel, COUNT(*) AS sessions, SUM(purchases) AS purchases,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_sessions,
       ROUND(100.0 * SUM(purchases) / NULLIF(COUNT(*), 0), 3) AS purchase_rate_pct
FROM real_sessions_ch GROUP BY 1 ORDER BY 2 DESC;

-- output: real_calibration
SELECT COUNT(*) AS sessions, SUM(purchases) AS sessions_purchases,
       ROUND(100.0 * SUM(purchases) / COUNT(*), 3) AS purchases_per_100_sessions
FROM real_sessions;
