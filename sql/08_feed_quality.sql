-- 08 - Product feed quality against the Merchant Center product data specification (SIMULATED, Client M)
-- Rules used (Merchant Center "Product data specification", read 2026-11-25): id, title, link, image_link,
-- price and availability are required; price carries an ISO 4217 currency; availability is one of
-- in_stock, out_of_stock, preorder, backorder. The market -> currency rule is Client M's own setup.

CREATE OR REPLACE TEMP VIEW market_currency AS
SELECT * FROM (VALUES ('FR','EUR'),('DE','EUR'),('ES','EUR'),('IT','EUR'),('NL','EUR'),('UK','GBP'),('PL','PLN'),('US','USD')) t(market, currency);

CREATE OR REPLACE TEMP VIEW feed_checks AS
SELECT f.*, mc.currency AS expected_currency,
       f.currency <> mc.currency                                                    AS wrong_currency,
       f.availability IS NULL OR f.availability = ''                                AS missing_availability,
       f.availability IS NOT NULL AND f.availability NOT IN ('in_stock','out_of_stock','preorder','backorder') AS invalid_availability,
       f.price IS NULL OR f.price <= 0                                              AS invalid_price,
       f.title IS NULL OR LENGTH(f.title) > 150                                     AS invalid_title,
       NOT regexp_matches(f.link, '^https://')                                      AS invalid_link,
       NOT regexp_matches(f.image_link, '^https://')                                AS invalid_image_link
FROM product_feed f JOIN market_currency mc USING (market);

-- output: feed_quality_market
SELECT market, COUNT(*) AS products,
       SUM(wrong_currency::INT) AS wrong_currency, SUM(missing_availability::INT) AS missing_availability,
       SUM(invalid_availability::INT) AS invalid_availability, SUM(invalid_price::INT) AS invalid_price,
       SUM(invalid_title::INT + invalid_link::INT + invalid_image_link::INT) AS other_issues,
       ROUND(100.0 * AVG((wrong_currency OR missing_availability OR invalid_availability OR invalid_price
                          OR invalid_title OR invalid_link OR invalid_image_link)::INT), 1) AS pct_products_at_risk
FROM feed_checks GROUP BY 1 ORDER BY 1;

-- output: feed_issues
SELECT sku, market, currency, expected_currency, availability,
       CASE WHEN wrong_currency THEN 'wrong_currency' WHEN missing_availability THEN 'missing_availability'
            WHEN invalid_availability THEN 'invalid_availability' ELSE 'other' END AS issue
FROM feed_checks
WHERE wrong_currency OR missing_availability OR invalid_availability OR invalid_price OR invalid_title OR invalid_link OR invalid_image_link
ORDER BY market, sku;
