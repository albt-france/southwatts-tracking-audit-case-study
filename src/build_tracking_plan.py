"""Build the tracking plan and everything derived from it, from ONE definition (PLAN below):

  tracking/tracking_plan.xlsx      one row per event x parameter, with destinations and consent
  tracking/tracking_plan.md        the same, readable on GitHub
  tracking/datalayer.schema.json   JSON Schema (draft 2020-12) of every dataLayer event
  tracking/gtm_container_client.json  web container TEMPLATE (GTM export format, placeholder ids)
  tracking/gtm_container_server.json  server container TEMPLATE (GTM export format, placeholder ids)

Event and parameter names follow the GA4 recommended events reference
(https://developers.google.com/analytics/devguides/collection/ga4/reference/events, read 2026-11-25).
event_id is our own addition: the same value is sent by the browser pixel and by the Conversions API so the
platform can deduplicate (Meta "Deduplicate pixel and server events", read 2026-11-25).

The GTM files are templates: every id is a placeholder (GTM-XXXXXXX, G-DEMO000000, AW-000000000). They were
NOT imported into a real account by this project: import them into a test container to validate them.

    python src/build_tracking_plan.py
"""
import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tracking"

GTM_WEB, GTM_SERVER = "GTM-XXXXXXX", "GTM-SRVXXXX"
GA4_ID, ADS_ID, ADS_LABEL = "G-DEMO000000", "AW-000000000", "DEMO_LABEL"
META_PIXEL, LI_PARTNER = "000000000000000", "0000000"

ITEM_PARAMS = [("item_id", "string", True, "SKU, same id as the product feed"),
               ("item_name", "string", True, "Product name"),
               ("price", "number", True, "Unit price, tax included"),
               ("quantity", "integer", True, "Units"),
               ("item_category", "string", False, "Main category"),
               ("item_list_name", "string", False, "List the item was selected from")]
# event -> trigger, parameters (name, type, required, note), destinations, consent
COMMON_VALUE = [("currency", "string", True, "ISO 4217, 3 letters"), ("value", "number", True, "Sum of price x quantity")]
PLAN = {
    "view_item_list": {"trigger": "Category or search results page rendered",
                       "params": [("item_list_id", "string", True, "Stable list id"), ("item_list_name", "string", True, "Readable list name")],
                       "items": True, "event_id": False, "dest": {"GA4": "view_item_list", "Google Ads": "-", "Meta": "-", "LinkedIn": "-"},
                       "consent": "analytics_storage"},
    "view_item": {"trigger": "Product page rendered", "params": COMMON_VALUE, "items": True, "event_id": True,
                  "dest": {"GA4": "view_item", "Google Ads": "remarketing (dynamic)", "Meta": "ViewContent", "LinkedIn": "-"},
                  "consent": "analytics_storage; ad_storage for ads"},
    "add_to_cart": {"trigger": "Add-to-cart confirmed by the cart API", "params": COMMON_VALUE, "items": True, "event_id": True,
                    "dest": {"GA4": "add_to_cart", "Google Ads": "-", "Meta": "AddToCart", "LinkedIn": "-"},
                    "consent": "analytics_storage; ad_storage for ads"},
    "begin_checkout": {"trigger": "Checkout page 1 rendered", "params": COMMON_VALUE + [("coupon", "string", False, "Coupon code if any")],
                       "items": True, "event_id": True,
                       "dest": {"GA4": "begin_checkout", "Google Ads": "-", "Meta": "InitiateCheckout", "LinkedIn": "-"},
                       "consent": "analytics_storage; ad_storage for ads"},
    "add_payment_info": {"trigger": "Payment method selected", "params": COMMON_VALUE + [("payment_type", "string", True, "card, paypal, bank_transfer...")],
                         "items": True, "event_id": True,
                         "dest": {"GA4": "add_payment_info", "Google Ads": "-", "Meta": "AddPaymentInfo", "LinkedIn": "-"},
                         "consent": "analytics_storage; ad_storage for ads"},
    "purchase": {"trigger": "Order confirmation page, ONCE per transaction_id (guard in localStorage)",
                 "params": [("transaction_id", "string", True, "Order id from the back office, unique"),
                            ("value", "number", True, "Order value without shipping"), ("currency", "string", True, "ISO 4217"),
                            ("tax", "number", False, "Tax amount"), ("shipping", "number", False, "Shipping amount"),
                            ("coupon", "string", False, "Coupon code if any")],
                 "items": True, "event_id": True,
                 "dest": {"GA4": "purchase", "Google Ads": "conversion (order_id = transaction_id)", "Meta": "Purchase (pixel + CAPI, shared event_id)",
                          "LinkedIn": "conversion (Insight Tag + CAPI, shared event_id)"},
                 "consent": "analytics_storage; ad_storage, ad_user_data for ads"},
}


def plan_rows():
    for ev, p in PLAN.items():
        base = {"event": ev, "trigger": p["trigger"], **{f"dest_{k}": v for k, v in p["dest"].items()}, "consent_required": p["consent"]}
        if p["event_id"]:
            yield {**base, "parameter": "event_id", "type": "string", "required": "yes", "note": "Unique per action; shared by pixel and server (deduplication)"}
        for name, typ, req, note in p["params"]:
            yield {**base, "parameter": f"ecommerce.{name}", "type": typ, "required": "yes" if req else "no", "note": note}
        if p["items"]:
            for name, typ, req, note in ITEM_PARAMS:
                yield {**base, "parameter": f"ecommerce.items[].{name}", "type": typ, "required": "yes" if req else "no", "note": note}


COLS = ["event", "trigger", "parameter", "type", "required", "note", "dest_GA4", "dest_Google Ads", "dest_Meta", "dest_LinkedIn", "consent_required"]


def write_xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "tracking_plan"
    ws.append([c.replace("dest_", "→ ") for c in COLS])
    for r in rows:
        ws.append([r[c] for c in COLS])
    head = PatternFill("solid", fgColor="2A78D6")
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), head
    widths = [18, 34, 30, 9, 9, 44, 16, 26, 30, 30, 30]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    ws2 = wb.create_sheet("ids_placeholders")
    ws2.append(["setting", "placeholder", "where the real value lives"])
    for r in [("GTM web container", GTM_WEB, "client GTM account"), ("GTM server container", GTM_SERVER, "client GTM account"),
              ("GA4 measurement id", GA4_ID, "client GA4 property"), ("Google Ads conversion id", ADS_ID, "client Google Ads account"),
              ("Meta pixel id", META_PIXEL, "client Meta Business Manager"), ("LinkedIn partner id", LI_PARTNER, "client Campaign Manager")]:
        ws2.append(list(r))
    ws2.column_dimensions["A"].width, ws2.column_dimensions["B"].width, ws2.column_dimensions["C"].width = 28, 20, 34
    wb.properties.creator = ""
    wb.properties.lastModifiedBy = ""
    wb.save(OUT / "tracking_plan.xlsx")


def write_md(rows):
    lines = ["# Tracking plan - Client M (fictional client, template)", "",
             "Generated by `src/build_tracking_plan.py` (same source as `datalayer.schema.json` and the GTM templates).",
             "Event and parameter names follow the GA4 recommended events reference (read 2026-11-25). `event_id` is added",
             "for pixel / Conversions API deduplication. Consent types follow Google Consent Mode (`analytics_storage`,",
             "`ad_storage`, `ad_user_data`, `ad_personalization`). Every id is a placeholder.", "",
             "## Events", "", "| Event | Trigger | GA4 | Google Ads | Meta | LinkedIn | Consent |", "|---|---|---|---|---|---|---|"]
    for ev, p in PLAN.items():
        d = p["dest"]
        lines.append(f"| `{ev}` | {p['trigger']} | {d['GA4']} | {d['Google Ads']} | {d['Meta']} | {d['LinkedIn']} | {p['consent']} |")
    lines += ["", "## Parameters", "", "| Event | Parameter | Type | Required | Note |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| `{r['event']}` | `{r['parameter']}` | {r['type']} | {r['required']} | {r['note']} |")
    lines += ["", "## Rules", "",
              "- `ecommerce` is cleared (`dataLayer.push({ecommerce: null})`) before every ecommerce push, so values never leak from one event to the next.",
              "- `purchase` fires once per `transaction_id`: the page stores sent ids in `localStorage` and skips a reload (the GA4 public sample shows 326 duplicated ids, 288 of them within one minute).",
              "- `event_id` is generated once in the browser and forwarded to the server container, which reuses it for Meta CAPI and LinkedIn CAPI.",
              "- Consent default is `denied` for every type and is set before any tag (Consent Initialization trigger); the banner then sends `consent update`.",
              "- No personal data in the dataLayer. Hashed e-mail for enhanced conversions is added server-side only, with `ad_user_data` granted."]
    (OUT / "tracking_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_schema():
    item = {"type": "object", "required": [n for n, _, req, _ in ITEM_PARAMS if req],
            "properties": {n: {"type": t} for n, t, _, _ in ITEM_PARAMS}}
    item["properties"]["price"]["minimum"] = 0
    item["properties"]["quantity"]["minimum"] = 1
    defs = {"item": item}
    for ev, p in PLAN.items():
        eco = {"type": "object", "required": [n for n, _, req, _ in p["params"] if req] + ["items"],
               "properties": {n: {"type": t} for n, t, _, _ in p["params"]}}
        eco["properties"]["items"] = {"type": "array", "minItems": 1, "items": {"$ref": "#/$defs/item"}}
        if "currency" in eco["properties"]:
            eco["properties"]["currency"]["pattern"] = "^[A-Z]{3}$"
        if "value" in eco["properties"]:
            eco["properties"]["value"]["minimum"] = 0
        if "transaction_id" in eco["properties"]:
            eco["properties"]["transaction_id"]["minLength"] = 1
            eco["properties"]["transaction_id"]["not"] = {"enum": ["(not set)", "undefined", "null"]}
        req = ["event", "ecommerce"] + (["event_id"] if p["event_id"] else [])
        props = {"event": {"const": ev}, "ecommerce": eco}
        if p["event_id"]:
            props["event_id"] = {"type": "string", "pattern": "^evt_[0-9a-f]{16}$"}
        defs[ev] = {"type": "object", "required": req, "properties": props}
    schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
              "$id": "https://example.com/client-m/datalayer.schema.json",
              "title": "Client M dataLayer ecommerce events (template)",
              "description": "One branch per event of tracking_plan.md. Names follow the GA4 recommended events reference (read 2026-11-25).",
              "oneOf": [{"$ref": f"#/$defs/{ev}"} for ev in PLAN], "$defs": defs}
    (OUT / "datalayer.schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")


# ---------------- GTM export templates ----------------
def T(key, value, typ="TEMPLATE"):
    return {"type": typ, "key": key, "value": value}


def dlv(vid, name, path):
    return {"accountId": "0", "containerId": "0", "variableId": str(vid), "name": name, "type": "v",
            "parameter": [T("dataLayerVersion", "2", "INTEGER"), T("setDefaultValue", "false", "BOOLEAN"), T("name", path)]}


def custom_event_trigger(tid, name, event):
    return {"accountId": "0", "containerId": "0", "triggerId": str(tid), "name": name, "type": "CUSTOM_EVENT",
            "customEventFilter": [{"type": "EQUALS", "parameter": [T("arg0", "{{_event}}"), T("arg1", event)]}]}


def consent(*types):
    return {"consentStatus": "NEEDED", "consentType": {"type": "LIST", "list": [{"type": "TEMPLATE", "value": t} for t in types]}}


def container(name, public_id, usage, tags, triggers, variables, clients=None):
    c = {"exportFormatVersion": 2, "exportTime": "2026-11-25 00:00:00",
         "containerVersion": {"path": "accounts/0/containers/0/versions/0", "accountId": "0", "containerId": "0",
                              "containerVersionId": "0", "name": "template v1",
                              "description": "TEMPLATE for a fictional client. Placeholder ids. Validate by importing into a TEST container (merge, new workspace).",
                              "container": {"path": "accounts/0/containers/0", "accountId": "0", "containerId": "0", "name": name,
                                            "publicId": public_id, "usageContext": [usage]},
                              "tag": tags, "trigger": triggers, "variable": variables}}
    if clients:
        c["containerVersion"]["client"] = clients
    return c


def write_gtm():
    ALL_PAGES, CONSENT_INIT = "2147479553", "2147479572"     # GTM built-in trigger ids
    ecommerce_events = [e for e in PLAN]
    triggers = [custom_event_trigger(100 + i, f"CE - {e}", e) for i, e in enumerate(ecommerce_events)]
    tid = {e: str(100 + i) for i, e in enumerate(ecommerce_events)}
    triggers.append({"accountId": "0", "containerId": "0", "triggerId": "199", "name": "CE - all ecommerce events", "type": "CUSTOM_EVENT",
                     "customEventFilter": [{"type": "MATCH_REGEX", "parameter": [T("arg0", "{{_event}}"),
                                                                                 T("arg1", "^(" + "|".join(ecommerce_events) + ")$")]}]})
    variables = [dlv(10, "DLV - event_id", "event_id"), dlv(11, "DLV - ecommerce.transaction_id", "ecommerce.transaction_id"),
                 dlv(12, "DLV - ecommerce.value", "ecommerce.value"), dlv(13, "DLV - ecommerce.currency", "ecommerce.currency"),
                 dlv(14, "DLV - ecommerce.items", "ecommerce.items"),
                 {"accountId": "0", "containerId": "0", "variableId": "15", "name": "CONST - GA4 measurement id", "type": "c",
                  "parameter": [T("value", GA4_ID)]},
                 {"accountId": "0", "containerId": "0", "variableId": "16", "name": "CONST - server container URL", "type": "c",
                  "parameter": [T("value", "https://metrics.clientm.example")]}]
    tags = [
        {"accountId": "0", "containerId": "0", "tagId": "1", "name": "Consent Mode - default denied", "type": "html",
         "parameter": [T("html", "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}"
                                 "gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied',ad_user_data:'denied',"
                                 "ad_personalization:'denied',wait_for_update:500});</script>"),
                       T("supportDocumentWrite", "false", "BOOLEAN")],
         "firingTriggerId": [CONSENT_INIT], "tagFiringOption": "ONCE_PER_LOAD",
         "notes": "In production, replace by the CMP's own Consent Mode template (Template Gallery)."},
        {"accountId": "0", "containerId": "0", "tagId": "2", "name": "Google tag - GA4", "type": "googtag",
         "parameter": [T("tagId", "{{CONST - GA4 measurement id}}"),
                       {"type": "LIST", "key": "configSettingsTable", "list": [
                           {"type": "MAP", "map": [T("parameter", "server_container_url"), T("parameterValue", "{{CONST - server container URL}}")]}]}],
         "firingTriggerId": [ALL_PAGES], "consentSettings": consent("analytics_storage"), "tagFiringOption": "ONCE_PER_EVENT",
         "notes": "Sends to the server container on the first-party subdomain. Google tag gateway (serving the Google tag from the site's own domain) is configured on the CDN / load balancer, not in this file."},
        {"accountId": "0", "containerId": "0", "tagId": "3", "name": "GA4 - ecommerce events", "type": "gaawe",
         "parameter": [T("eventName", "{{Event}}"), T("measurementIdOverride", "{{CONST - GA4 measurement id}}"),
                       T("sendEcommerceData", "true", "BOOLEAN"), T("getEcommerceDataFrom", "dataLayer"),
                       {"type": "LIST", "key": "eventSettingsTable", "list": [
                           {"type": "MAP", "map": [T("parameter", "event_id"), T("parameterValue", "{{DLV - event_id}}")]}]}],
         "firingTriggerId": ["199"], "consentSettings": consent("analytics_storage"), "tagFiringOption": "ONCE_PER_EVENT"},
        {"accountId": "0", "containerId": "0", "tagId": "4", "name": "Google Ads - conversion linker", "type": "gclidw",
         "parameter": [T("enableCrossDomain", "true", "BOOLEAN"), T("linkerDomains", "clientm.example,pay.psp-example.com"),
                       T("enableUrlPassthrough", "false", "BOOLEAN")],
         "firingTriggerId": [ALL_PAGES], "consentSettings": consent("ad_storage"), "tagFiringOption": "ONCE_PER_EVENT",
         "notes": "Cross-domain list includes the payment provider (see discrepancy_playbook.md, cross-domain)."},
        {"accountId": "0", "containerId": "0", "tagId": "5", "name": "Google Ads - purchase conversion", "type": "awct",
         "parameter": [T("conversionId", ADS_ID.replace("AW-", "")), T("conversionLabel", ADS_LABEL),
                       T("conversionValue", "{{DLV - ecommerce.value}}"), T("currencyCode", "{{DLV - ecommerce.currency}}"),
                       T("orderId", "{{DLV - ecommerce.transaction_id}}"), T("enableEnhancedConversion", "false", "BOOLEAN")],
         "firingTriggerId": [tid["purchase"]], "consentSettings": consent("ad_storage", "ad_user_data"), "tagFiringOption": "ONCE_PER_EVENT",
         "notes": "orderId = transaction_id lets Google Ads drop duplicate conversions."},
        {"accountId": "0", "containerId": "0", "tagId": "6", "name": "Meta pixel - Purchase (browser side)", "type": "html",
         "parameter": [T("html", "<script>/* Meta pixel base code loads here in production (pixel id " + META_PIXEL + ") */\n"
                                 "if (window.fbq) { fbq('track', 'Purchase', {value: {{DLV - ecommerce.value}}, currency: '{{DLV - ecommerce.currency}}'},"
                                 " {eventID: '{{DLV - event_id}}'}); }</script>"),
                       T("supportDocumentWrite", "false", "BOOLEAN")],
         "firingTriggerId": [tid["purchase"]], "consentSettings": consent("ad_storage", "ad_user_data"), "tagFiringOption": "ONCE_PER_EVENT",
         "notes": "eventID MUST equal the event_id sent by the server-side Conversions API tag (deduplication)."},
        {"accountId": "0", "containerId": "0", "tagId": "7", "name": "LinkedIn Insight - purchase conversion", "type": "html",
         "parameter": [T("html", "<script>/* LinkedIn Insight Tag base code loads here in production (partner id " + LI_PARTNER + ") */\n"
                                 "if (window.lintrk) { lintrk('track', {conversion_id: 0, event_id: '{{DLV - event_id}}'}); }</script>"),
                       T("supportDocumentWrite", "false", "BOOLEAN")],
         "firingTriggerId": [tid["purchase"]], "consentSettings": consent("ad_storage", "ad_user_data"), "tagFiringOption": "ONCE_PER_EVENT"},
    ]
    web = container("Client M - web (template)", GTM_WEB, "WEB", tags, triggers, variables)
    (OUT / "gtm_container_client.json").write_text(json.dumps(web, indent=2), encoding="utf-8")

    s_clients = [{"accountId": "0", "containerId": "0", "clientId": "1", "name": "GA4 client", "type": "gaaw_client",
                  "parameter": [T("activateDefaultPaths", "true", "BOOLEAN")], "priority": 0}]
    s_triggers = [{"accountId": "0", "containerId": "0", "triggerId": "300", "name": "Client = GA4 client", "type": "ALWAYS",
                   "filter": [{"type": "EQUALS", "parameter": [T("arg0", "{{Client Name}}"), T("arg1", "GA4 client")]}]},
                  {"accountId": "0", "containerId": "0", "triggerId": "301", "name": "Event = purchase", "type": "ALWAYS",
                   "filter": [{"type": "EQUALS", "parameter": [T("arg0", "{{Event Name}}"), T("arg1", "purchase")]}]}]
    s_vars = [{"accountId": "0", "containerId": "0", "variableId": "30", "name": "ED - event_id", "type": "ed",
               "parameter": [T("keyPath", "event_id")]},
              {"accountId": "0", "containerId": "0", "variableId": "31", "name": "ED - transaction_id", "type": "ed",
               "parameter": [T("keyPath", "transaction_id")]}]
    s_tags = [
        {"accountId": "0", "containerId": "0", "tagId": "20", "name": "GA4 - forward all events", "type": "sgtmgaaw",
         "parameter": [T("redactVisitorIp", "true", "BOOLEAN")], "firingTriggerId": ["300"]},
        {"accountId": "0", "containerId": "0", "tagId": "21", "name": "Google Ads - purchase conversion (server)", "type": "sgtmadsct",
         "parameter": [T("conversionId", ADS_ID.replace("AW-", "")), T("conversionLabel", ADS_LABEL), T("orderId", "{{ED - transaction_id}}")],
         "firingTriggerId": ["301"]},
    ]
    server = container("Client M - server (template)", GTM_SERVER, "SERVER", s_tags, s_triggers, s_vars, s_clients)
    server["containerVersion"]["description"] += (" Meta Conversions API and LinkedIn Conversions API tags come from the server Template Gallery:"
                                                  " add them after import, with event_id = {{ED - event_id}} and the same event name as the pixel.")
    (OUT / "gtm_container_server.json").write_text(json.dumps(server, indent=2), encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    rows = list(plan_rows())
    write_xlsx(rows)
    write_md(rows)
    write_schema()
    write_gtm()
    print(f"tracking plan: {len(PLAN)} events, {len(rows)} parameter rows -> tracking/")


if __name__ == "__main__":
    main()
