# Product feed checklist (ad platforms)

Rules from the Merchant Center "Product data specification" (<https://support.google.com/merchants/answer/7052112?hl=en>,
read 2026-11-25), plus Client M's own rules. Only the rules listed here are checked by
[`src/feed_validator.py`](../src/feed_validator.py); it is not a full Merchant Center review.

## Before each feed change

- [ ] Required attributes present on every product: `id`, `title`, `link`, `image_link`, `price`, `availability`
      (and `gtin` when the product has one).
- [ ] `price` carries an ISO 4217 currency, and the currency is the **market's** currency (EUR, GBP, PLN, USD).
- [ ] `availability` is one of `in_stock`, `out_of_stock`, `preorder`, `backorder`.
- [ ] `title` at most 150 characters; no promotional text in the title.
- [ ] `link` and `image_link` on https, landing on the right market.
- [ ] GTIN check digit valid.
- [ ] The same `id` is used in the feed and in the dataLayer `item_id` (needed for dynamic remarketing and reporting).
- [ ] Prices in the feed match the price on the landing page.

## After each feed change

- [ ] Run the validator on the new export before it is sent.
- [ ] Next day: product status in the platform (approved / disapproved), by market.
- [ ] Next 3 days: Shopping clicks and conversions by market vs the previous weeks.

## Simulation result (fictional Client M)

A new export from the product system on 2026-10-16 broke PL and UK: **42** rows with EUR instead of PLN/GBP (7% of each
market) and **18** rows without `availability` (3%). **10%** of the products of each market are at risk of disapproval.
The other six markets are clean.
