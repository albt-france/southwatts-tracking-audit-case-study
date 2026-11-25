# UTM governance

**Goal**: every paid session lands in the right channel. In the simulation (fictional Client M), **19.1%** of paid
sessions fall in "Unassigned" because of free-form UTMs; for agency AGY2 (paid social) it is **46.1%**.

## Convention

| Parameter | Rule | Example |
|---|---|---|
| `utm_source` | lowercase platform name, from the list | `google`, `meta`, `linkedin`, `cm360`, `newsletter` |
| `utm_medium` | lowercase, one of the approved pairs below | `cpc`, `paid_social`, `display`, `email` |
| `utm_campaign` | `<market>_<campaign type>_<year>q<quarter>` | `fr_prospecting_2026q4` |
| `utm_content` | optional, lowercase, creative id | `video_15s_a` |

Approved source/medium pairs: `google/cpc`, `meta/paid_social`, `linkedin/paid_social`, `cm360/display`,
`newsletter/email`. Google Ads uses auto-tagging (`gclid`); GA4 then takes the source/medium from the click,
so a missing medium on a Google Ads link does no harm, but the link is still fixed for consistency.

## Channel rules used in this study

Client M uses its own **custom channel group**: only the approved pairs map to a channel; anything else is
"Unassigned" (simplified rules written for this study, not Google's default channel group). With Google's default
grouping, some of these variants would land in other channels (for example organic social) instead of Unassigned:
the reporting error is the same.

## Mapping table (variants found → value to use)

| Found | Use |
|---|---|
| `Facebook`, `facebook`, `fb`, `instagram`, `ig` | `meta` |
| `Paid_Social`, `paidsocial`, `paid-social`, `social` (with a social source) | `paid_social` |
| `ppc` | `cpc` |
| missing medium | the platform's medium |
| campaign with spaces or capitals | lowercase, `_` instead of spaces |

Full list in `utm/utm_builder.xlsx` (sheet `mapping`) and in [`src/utm_validator.py`](../src/utm_validator.py).

## Process: no link without validation

1. The agency builds the link in `utm/utm_builder.xlsx` (drop-down lists, URL built by formula, PASS/FAIL check).
2. Before the campaign starts, the agency sends its links file; `python src/utm_validator.py` (or a scheduled run)
   gives PASS/FAIL per link with the corrected value.
3. Only PASS links go live. A FAIL found during the campaign is fixed in the ad platform within one working day.
4. Weekly: the monitoring check `paid_unassigned_share` (WARN > 5%, FAIL > 10% per market).

## Simulation result

266 links: 68 FAIL (74.4% compliant). AGY1 87.5%, **AGY2 57.6%**, AGY3 93.3%. Twelve percent of all links have no
medium. Fixing AGY2's Meta links alone removes most of the Unassigned traffic.
