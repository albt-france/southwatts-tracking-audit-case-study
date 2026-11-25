-- 06 - Consent and releases: dated breaks in GA4 sessions, matched with the deploy log (SIMULATED, Client M)
-- Baseline = median sessions for the same market and weekday over the 4 weeks before 2026-10-05
-- (before any risky release). A break = 3+ consecutive non-holiday days at more than 12% from baseline.
-- Consent principles (CNIL, read 2026-11-25): information and consent before non-exempt trackers are
-- placed or read. Not legal advice.

CREATE OR REPLACE TEMP VIEW sess AS
SELECT event_date AS date, market, COUNT(*) AS sessions,
       COUNT(*) FILTER (WHERE consent_state = 'pre_choice') AS pre_choice_sessions
FROM ga4_events WHERE event_name = 'session_start' GROUP BY ALL;

CREATE OR REPLACE TEMP VIEW base AS
SELECT market, dayofweek(date) AS dow, MEDIAN(sessions) AS baseline
FROM sess s WHERE date BETWEEN DATE '2026-09-07' AND DATE '2026-10-04'
  AND NOT EXISTS (SELECT 1 FROM holidays h WHERE h.market = s.market AND h.date = s.date)
GROUP BY ALL;

-- output: consent_daily
SELECT s.date, s.market, s.sessions, s.pre_choice_sessions,
       ROUND(s.pre_choice_sessions / s.sessions, 4) AS pre_choice_share,
       b.baseline, ROUND(s.sessions / b.baseline - 1, 4) AS deviation,
       EXISTS (SELECT 1 FROM holidays h WHERE h.market = s.market AND h.date = s.date) AS holiday
FROM sess s JOIN base b ON b.market = s.market AND b.dow = dayofweek(s.date)
ORDER BY 1, 2;

-- output: consent_breaks
WITH d AS (
  SELECT *, CASE WHEN NOT holiday AND deviation > 0.12 THEN 'up' WHEN NOT holiday AND deviation < -0.12 THEN 'down' END AS dir
  FROM read_csv_auto('data/out/consent_daily.csv')),
runs AS (
  SELECT *, SUM(CASE WHEN dir IS DISTINCT FROM prev THEN 1 ELSE 0 END) OVER (PARTITION BY market ORDER BY date) AS grp
  FROM (SELECT *, LAG(dir) OVER (PARTITION BY market ORDER BY date) AS prev FROM d WHERE NOT holiday)),
br AS (
  SELECT market, dir, MIN(date) AS start_date, MAX(date) AS end_date, COUNT(*) AS days,
         ROUND(AVG(deviation), 3) AS mean_deviation, ROUND(AVG(pre_choice_share), 3) AS mean_pre_choice_share
  FROM runs WHERE dir IS NOT NULL GROUP BY market, dir, grp HAVING COUNT(*) >= 3)
SELECT br.*,
       (SELECT STRING_AGG(version || ' (' || change || ')', '; ') FROM deploy_log dl
         WHERE dl.container IN ('web', 'site') AND (dl.market_scope = 'ALL' OR dl.market_scope LIKE '%' || br.market || '%')
           AND CAST(dl.date AS DATE) BETWEEN br.start_date - 1 AND br.start_date) AS release_at_start
FROM br ORDER BY market, start_date;
