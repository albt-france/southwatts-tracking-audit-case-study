# Implementation guide: from the browser to the server and the ad platforms

Template for a fictional multi-market client ("Client M"). Every id is a placeholder. Each technical rule is
cited with its official page and the date it was read (2026-11-25). Nothing here is legal advice.

## 1. Architecture

See [`tracking/architecture.md`](../tracking/architecture.md) for the diagram.

1. **dataLayer** (site code): the website pushes the events of [`tracking/tracking_plan.md`](../tracking/tracking_plan.md),
   validated by [`tracking/datalayer.schema.json`](../tracking/datalayer.schema.json) and tested automatically
   ([`tests/test_datalayer.py`](../tests/test_datalayer.py)).
2. **Web container (GTM, client side)**: Consent Mode default, Google tag, GA4 events, Google Ads conversion and
   conversion linker, Meta pixel and LinkedIn Insight Tag. Template: [`tracking/gtm_container_client.json`](../tracking/gtm_container_client.json).
3. **Server container (GTM, server side)** on a first-party subdomain (for example `metrics.<client domain>`):
   receives GA4 hits and forwards them to GA4, Google Ads, Meta Conversions API and LinkedIn Conversions API.
   Template: [`tracking/gtm_container_server.json`](../tracking/gtm_container_server.json).
4. **Google tag gateway for advertisers**: serves the Google tag from the site's own domain. Google describes it as
   deploying "a Google tag using your own first-party infrastructure, hosted on your website's domain", set up
   on an existing CDN, load balancer or web server (<https://developers.google.com/tag-platform/tag-manager/gateway>).
   It is configured on the infrastructure, not inside the container.

## 2. Client side

- Consent defaults are set **before** any tag, on the Consent Initialization trigger, all types `denied`;
  the consent banner sends an update. The demo shop shows the exact sequence.
- `ecommerce` is cleared (`{ecommerce: null}`) before each ecommerce push.
- `purchase`: once per `transaction_id` (localStorage guard). Google Ads conversion uses `orderId = transaction_id`.
- Every conversion event carries an `event_id` generated in the browser.

## 3. Server side and Conversions APIs

- The server container forwards the browser `event_id` unchanged. Meta deduplicates a pixel event and a
  Conversions API event when they share the same `event_id` (`eventID` in the pixel) and the same event name;
  Meta's page states that events with the same keys sent to the same pixel within 48 hours are discarded after the first
  (<https://developers.facebook.com/docs/marketing-api/conversions-api/deduplicate-pixel-and-server-events>).
- A server tag must **never** generate its own `event_id` for an event that the browser also sends: that is
  exactly the double-counting case of the simulation (FR, ES).
- GA4 Measurement Protocol is a server-to-server way to send events to GA4
  (<https://developers.google.com/analytics/devguides/collection/protocol/ga4>). It needs a measurement id and an
  API secret. This project documents them in `.env.example` but **never calls the endpoint**.
- Monitor every destination hourly (error rate, latency): see [`monitoring_runbook.md`](monitoring_runbook.md).

## 4. Consent Mode

- Consent types: `ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization`.
- Each tag declares the consent it needs (`consentSettings` in the templates).
- CNIL (<https://www.cnil.fr/fr/cookies-et-autres-traceurs/regles/cookies>, read 2026-11-25): users must be informed
  and give consent **before** certain trackers are placed or read, while others are exempt. The legal analysis
  of which tracker is exempt belongs to the client's DPO or lawyer. **Not legal advice.**
- IAB TCF Global Vendor List v3 (read 2026-11-25): version 186, updated 2026-11-19, **1,240 vendors** and 11 purposes.
  It shows how many partners a CMP may have to list: one more reason to keep the tag list short.
- Release rule: any change to the consent setup ships with a before/after check of sessions and of
  hits sent before the choice (simulation, Germany: +19% sessions with hits before the choice, then −33% after an
  over-strict hotfix).

## 5. Cross-domain measurement

- List every domain of the journey (shop, checkout, **payment provider**) in the linker settings.
- Exclude own domains and the payment provider as referrals.
- Test the full payment journey in preview mode after every payment-provider change (simulation, UK: 70% of
  purchases landed in a new session from the provider or from the shop itself after a provider change).

## 6. Acceptance checklist (before publishing a container version)

- [ ] `python -m pytest tests` green: schema, order of events, `ecommerce: null`, `event_id`, single `purchase` after reload.
- [ ] Preview mode: each tag fires once on its trigger and is **blocked** when its consent is denied.
- [ ] No hit before the consent choice (Network tab, filter on `collect`).
- [ ] Pixel `eventID` = server `event_id` on a test purchase (Meta test events tool).
- [ ] Google Ads conversion has `orderId`.
- [ ] Payment journey keeps the session (no new session, no self-referral).
- [ ] Release note written: what changed, which markets, rollback version.
- [ ] Monitoring watched for 24 h after publishing (sessions vs baseline, pre-consent hits, server errors).
