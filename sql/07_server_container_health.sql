-- 07 - Server container health: error rate and latency per destination and hour (SIMULATED, Client M)
-- Alert rule (docs/monitoring_runbook.md): error rate > 20% in an hour with at least 10 events -> FAIL
-- (below 10 events an hour, two timeouts already make 20%: too noisy to page anyone).

-- output: server_hourly
SELECT date_trunc('hour', ts) AS hour_utc, destination, COUNT(*) AS events,
       COUNT(*) FILTER (WHERE status <> 'ok') AS errors,
       ROUND(COUNT(*) FILTER (WHERE status <> 'ok') / COUNT(*), 4) AS error_rate,
       QUANTILE_CONT(latency_ms, 0.95) AS p95_latency_ms
FROM server_events GROUP BY ALL ORDER BY 1, 2;

-- output: server_alerts
SELECT destination, MIN(hour_utc) AS first_alert_hour, MAX(hour_utc) AS last_alert_hour, COUNT(*) AS alert_hours,
       SUM(errors) AS failed_events,
       MIN(hour_utc) + INTERVAL 1 HOUR AS alert_raised_at   -- the check runs at the end of each hour
FROM read_csv_auto('data/out/server_hourly.csv')
WHERE error_rate > 0.20 AND events >= 10
GROUP BY 1 ORDER BY 2;

-- output: server_availability
SELECT destination, COUNT(*) AS active_hours,
       ROUND(100.0 * AVG((error_rate < 0.05)::INT), 2) AS pct_hours_healthy,
       ROUND(100.0 * SUM(events - errors) / SUM(events), 2) AS pct_events_delivered,
       ROUND(MEDIAN(p95_latency_ms)) AS median_p95_latency_ms
FROM read_csv_auto('data/out/server_hourly.csv') GROUP BY 1 ORDER BY 1;

-- output: meta_daily_vs_outage
-- what a daily-only view shows on the outage day: Meta conversions vs the same weekday of the 2 previous weeks
WITH d AS (SELECT date, SUM(conversions) AS meta_conversions FROM platform_conversions WHERE platform = 'meta' GROUP BY 1)
SELECT d.date, d.meta_conversions,
       ROUND((SELECT AVG(meta_conversions) FROM d d2 WHERE d2.date IN (d.date - 7, d.date - 14)), 1) AS same_weekday_avg,
       ROUND(d.meta_conversions / (SELECT AVG(meta_conversions) FROM d d2 WHERE d2.date IN (d.date - 7, d.date - 14)) - 1, 3) AS deviation
FROM d WHERE d.date BETWEEN DATE '2026-10-29' AND DATE '2026-11-12' ORDER BY 1;
