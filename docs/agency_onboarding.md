# Media agencies: tracking rules in one page

For agencies running campaigns for the fictional Client M. Questions go to the tracking specialist.

**1. Links.** Build every link in `utm/utm_builder.xlsx`. Lowercase only. Approved pairs: `google/cpc`,
`meta/paid_social`, `linkedin/paid_social`, `cm360/display`. Campaign name: `<market>_<type>_<year>q<quarter>`
(e.g. `fr_prospecting_2026q4`). Send the links file before launch: only PASS links go live.

**2. Google Ads.** Keep auto-tagging on. The purchase conversion uses the order id: do not create a second
purchase conversion action.

**3. Meta and LinkedIn.** Purchase is sent by the browser **and** the server with the same `event_id`.
Do not add a pixel or a Conversions API integration of your own (partner integration, plugin): it would double count.

**4. Before a launch.** Tell us the markets, dates, landing pages and any new domain (landing page builder,
payment page): new domains need cross-domain settings first.

**5. Reading results.** Platform numbers are higher than GA4 by design (attribution model, window, click date).
Compare trends, not totals; use the reconciliation table for the expected ratio per platform.

**6. Something looks wrong?** Send: platform, market, campaign, dates, screenshot of the platform number and of
GA4 for the same period. We answer within one working day.
