-- 05 - UTM compliance (SIMULATED, Client M)
-- Convention (docs/utm_governance.md): lowercase everywhere; approved source/medium pairs only;
-- utm_campaign = <market>_<campaign type>_<year>q<quarter>, e.g. fr_prospecting_2026q4.

CREATE OR REPLACE TEMP VIEW approved_pairs AS
SELECT * FROM (VALUES ('google', 'cpc'), ('meta', 'paid_social'), ('linkedin', 'paid_social'), ('cm360', 'display'),
                      ('newsletter', 'email')) t(source, medium);

-- output: utm_links_check
SELECT link_id, agency, campaign_id, market, platform, utm_source, utm_medium, utm_campaign,
       utm_source = LOWER(utm_source)                                       AS source_lowercase,
       utm_medium <> ''                                                     AS medium_present,
       utm_medium = LOWER(utm_medium)                                       AS medium_lowercase,
       (utm_source, utm_medium) IN (SELECT (source, medium) FROM approved_pairs) AS pair_approved,
       regexp_matches(utm_campaign, '^[a-z]{2}_[a-z]+_20[0-9]{2}q[1-4]$')   AS campaign_convention,
       (utm_source = LOWER(utm_source) AND utm_medium <> '' AND utm_medium = LOWER(utm_medium)
        AND (utm_source, utm_medium) IN (SELECT (source, medium) FROM approved_pairs)
        AND regexp_matches(utm_campaign, '^[a-z]{2}_[a-z]+_20[0-9]{2}q[1-4]$')) AS compliant
FROM utm_catalogue ORDER BY link_id;

-- output: utm_by_agency
SELECT agency, COUNT(*) AS links,
       ROUND(100.0 * AVG(compliant::INT), 1)             AS pct_compliant,
       COUNT(*) FILTER (WHERE NOT medium_present)        AS missing_medium,
       COUNT(*) FILTER (WHERE NOT source_lowercase OR NOT medium_lowercase) AS not_lowercase,
       COUNT(*) FILTER (WHERE NOT pair_approved)         AS pair_not_approved,
       COUNT(*) FILTER (WHERE NOT campaign_convention)   AS campaign_name_off
FROM (SELECT * FROM read_csv_auto('data/out/utm_links_check.csv'))
GROUP BY 1 ORDER BY 1;

-- output: utm_variants
-- every spelling found for each platform, with the normalised value the mapping table proposes
SELECT platform, utm_source, utm_medium, COUNT(*) AS links,
       CASE platform WHEN 'google_ads' THEN 'google' WHEN 'meta' THEN 'meta' WHEN 'linkedin' THEN 'linkedin' ELSE 'cm360' END AS source_normalised,
       CASE platform WHEN 'google_ads' THEN 'cpc' WHEN 'cm360' THEN 'display' ELSE 'paid_social' END AS medium_normalised
FROM utm_catalogue GROUP BY ALL ORDER BY platform, links DESC, utm_source, utm_medium;

CREATE OR REPLACE TEMP VIEW paid_sessions AS
SELECT e.event_date, e.market, e.source, e.medium, e.campaign, c.agency, c.platform,
       (e.source, e.medium) NOT IN (SELECT (source, medium) FROM approved_pairs) AS unassigned
FROM ga4_events e
JOIN campaigns c ON c.campaign_name = LOWER(REPLACE(e.campaign, ' ', '_'))
WHERE e.event_name = 'session_start';

-- output: utm_unassigned_summary
SELECT 'ALL' AS agency, COUNT(*) AS paid_sessions, ROUND(100.0 * AVG(unassigned::INT), 1) AS pct_unassigned FROM paid_sessions
UNION ALL
SELECT agency, COUNT(*), ROUND(100.0 * AVG(unassigned::INT), 1) FROM paid_sessions GROUP BY agency
ORDER BY agency;

-- output: utm_unassigned_weekly
SELECT date_trunc('week', event_date) AS week, market, COUNT(*) AS paid_sessions,
       ROUND(100.0 * AVG(unassigned::INT), 1) AS pct_unassigned
FROM paid_sessions GROUP BY ALL ORDER BY 1, 2;
