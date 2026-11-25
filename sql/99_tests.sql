-- 99 - Assertions. Any failed test stops src/run_sql.py with an error (DuckDB error()).
-- Run after 01-08. Reads repository files with relative paths (run_sql.py runs from the repository root).

CREATE OR REPLACE TEMP TABLE tests (name VARCHAR, passed BOOLEAN, detail VARCHAR);

-- 1. Public GA4 audit facts are reproduced (PUBLIC DATA)
INSERT INTO tests
SELECT 'real_audit_facts',
       MAX(value) FILTER (WHERE metric = 'purchase_events') = 5692
   AND MAX(value) FILTER (WHERE metric = 'purchases_without_id') = 906
   AND MAX(value) FILTER (WHERE metric = 'duplicated_ids') = 326
   AND MAX(value) FILTER (WHERE metric = 'page_views_self_referral') = 206005,
       'purchases 5692 / without id 906 / duplicated ids 326 / self-referral page views 206005'
FROM read_csv_auto('data/out/real_audit_summary.csv');

-- 2. Every reconciliation gap is categorised (0 unexplained)
INSERT INTO tests
SELECT 'reconciliation_100pct_explained',
       (SELECT COUNT(*) FROM read_csv_auto('data/out/reconciliation_weekly.csv') WHERE category = 'unexplained')
     + (SELECT COUNT(*) FROM read_csv_auto('data/out/reconciliation_period.csv') WHERE category = 'unexplained') = 0,
       'weekly + period rows with category unexplained';

-- 3. The Google Ads vs GA4 gap is treated as expected, not as a bug
INSERT INTO tests
SELECT 'google_ads_gap_is_expected',
       (SELECT MIN(expected_ratio) BETWEEN 1.10 AND 1.35 FROM read_csv_auto('data/out/reconciliation_weekly.csv') WHERE platform = 'google_ads')
   AND (SELECT COUNT(*) FROM read_csv_auto('data/out/reconciliation_weekly.csv')
         WHERE platform = 'google_ads' AND category = 'anomalous' AND explanation LIKE 'attribution%') = 0,
       'baseline ratio within 1.10-1.35 and never flagged as a bug';

-- 4. Each planted problem is visible in its own check
INSERT INTO tests SELECT 'consent_breaks_dated',
  (SELECT COUNT(*) FROM read_csv_auto('data/out/consent_breaks.csv') WHERE market = 'DE' AND release_at_start IS NOT NULL) = 2,
  'DE: one rise and one fall, each matched with a release';
INSERT INTO tests SELECT 'meta_event_id_breaks',
  (SELECT COUNT(*) FROM read_csv_auto('data/out/dedup_meta_breaks.csv') WHERE market IN ('FR', 'ES') AND match_rate_after < 0.5) = 2,
  'FR and ES: event_id match rate collapses';
INSERT INTO tests SELECT 'utm_unassigned_visible',
  (SELECT pct_unassigned FROM read_csv_auto('data/out/utm_unassigned_summary.csv') WHERE agency = 'ALL') > 10,
  'share of paid sessions in Unassigned';
INSERT INTO tests SELECT 'duplicate_purchases_visible',
  (SELECT MAX(pct_extra_purchases) FROM read_csv_auto('data/out/dedup_ga4_market.csv')) > 3,
  'one market with more than 3% extra purchase events';
INSERT INTO tests SELECT 'cross_domain_visible',
  (SELECT COUNT(*) FROM read_csv_auto('data/out/reconciliation_weekly.csv') WHERE explanation LIKE '%cross-domain%') > 0,
  'Google Ads vs GA4 anomaly explained by cross-domain';
INSERT INTO tests SELECT 'feed_issues_visible',
  (SELECT SUM(wrong_currency) + SUM(missing_availability) FROM read_csv_auto('data/out/feed_quality_market.csv')) > 0,
  'feed rows breaking the Merchant Center rules';
INSERT INTO tests SELECT 'server_outage_alert_within_1h',
  (SELECT COUNT(*) FROM read_csv_auto('data/out/server_alerts.csv')
    WHERE destination = 'meta_capi' AND alert_raised_at <= first_alert_hour + INTERVAL 1 HOUR) = 1,
  'hourly check raises the alert at the end of the first failing hour';

-- 5. Privacy: no pseudonymous user id in any output
INSERT INTO tests
SELECT 'no_user_pseudo_id_in_outputs', COUNT(*) = 0, 'outputs containing the pseudonymous user id column'
FROM read_text('data/out/*.csv') WHERE filename NOT LIKE '%tests_results.csv' AND content ILIKE '%user_pseudo_id%';

-- 6. No real measurement id in the repository: only obvious placeholders are allowed
INSERT INTO tests
SELECT 'only_placeholder_measurement_ids', COUNT(*) = 0, 'files with a GTM-/G-/AW- id that is not a placeholder'
FROM read_text(['tracking/*.json', 'tracking/*.md', 'tracking/*.svg', 'docs/*.md', 'src/*.py', 'site/demo-shop/*', 'README.md'])
WHERE regexp_matches(regexp_replace(content, 'GTM-XXXXXXX|GTM-SRVXXXX|G-DEMO000000|AW-000000000', '', 'g'),
                     'GTM-[A-Z0-9]{6,}|G-[A-Z0-9]{8,}|AW-[0-9]+');

-- 7. The demo shop loads no third-party script
INSERT INTO tests
SELECT 'demo_shop_no_external_script', COUNT(*) = 0, 'external <script src> in site/demo-shop'
FROM read_text('site/demo-shop/*') WHERE regexp_matches(content, '<script[^>]+src="(https?:)?//');

-- output: tests_results
SELECT * FROM tests ORDER BY name;

SELECT error('FAILED TESTS: ' || STRING_AGG(name, ', ')) FROM tests WHERE NOT passed HAVING COUNT(*) > 0;
