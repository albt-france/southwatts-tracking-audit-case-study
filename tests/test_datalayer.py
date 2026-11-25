"""Automated checks of the demo shop dataLayer against the tracking plan (SIMULATED client, no tag active).

Journey: product list -> product -> add to cart -> cart -> checkout -> payment -> order -> confirmation -> reload.
Every ecommerce push is validated with tracking/datalayer.schema.json (JSON Schema 2020-12).

    python -m pytest tests
"""
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "tracking" / "datalayer.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
PLAN_EVENTS = ["view_item_list", "view_item", "add_to_cart", "begin_checkout", "add_payment_info", "purchase"]

DL_JS = """() => window.dataLayer.map(e => (e && e.length !== undefined && typeof e !== 'string')
                                       ? {gtag: Array.from(e)} : e)"""


def events(dl):
    return [e for e in dl if isinstance(e, dict) and e.get("event") in PLAN_EVENTS]


def journey(page, url, bug=False):
    page.goto(url)
    if bug:
        page.check("#bug-toggle")
    page.click("#consent-accept")
    page.click("[data-testid=open-SKU0002]")
    page.click("[data-testid=add-to-cart]")
    page.click("#cart-link")
    page.click("[data-testid=go-checkout]")
    page.click("[data-testid=pay-card]")
    page.click("[data-testid=place-order]")
    page.wait_for_selector("[data-testid=order-id]")
    return page.evaluate(DL_JS), page.evaluate("() => window.serverPreview")


def test_consent_default_is_denied_before_any_event(page, shop_url):
    page.goto(shop_url)
    dl = page.evaluate(DL_JS)
    first = dl[0]["gtag"]
    assert first[0] == "consent" and first[1] == "default"
    assert all(first[2][k] == "denied" for k in ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization"))
    assert dl.index(dl[0]) < min(i for i, e in enumerate(dl) if isinstance(e, dict) and e.get("event"))


def test_journey_pushes_every_plan_event_valid_against_schema(page, shop_url, capture):
    dl, _ = journey(page, shop_url)
    evs = events(dl)
    capture("normal journey", [e for e in dl if isinstance(e, dict)])
    assert [e["event"] for e in evs] == PLAN_EVENTS
    errors = {e["event"]: [m.message for m in VALIDATOR.iter_errors(e)] for e in evs}
    assert all(not v for v in errors.values()), errors


def test_ecommerce_cleared_before_each_push(page, shop_url):
    dl, _ = journey(page, shop_url)
    for i, e in enumerate(dl):
        if isinstance(e, dict) and e.get("event") in PLAN_EVENTS:
            assert dl[i - 1] == {"ecommerce": None}, f"{e['event']} not preceded by ecommerce: null"


def test_event_ids_present_unique_and_shared_with_server(page, shop_url):
    dl, srv = journey(page, shop_url)
    ids = [e["event_id"] for e in events(dl) if "event_id" in e]
    assert len(ids) == len(set(ids)) == 5
    assert all(s["event_id"] == s["browser_event_id"] for s in srv), "server copy must reuse the browser event_id"


def test_purchase_once_per_transaction_after_reload(page, shop_url):
    dl, _ = journey(page, shop_url)
    tx = [e["ecommerce"]["transaction_id"] for e in events(dl) if e["event"] == "purchase"]
    assert len(tx) == 1
    page.reload()
    page.wait_for_selector("[data-testid=order-id]")
    again = [e for e in events(page.evaluate(DL_JS)) if e["event"] == "purchase"]
    assert again == [], "reload must not send purchase twice"


def test_bug_mode_is_caught_by_the_same_checks(page, shop_url, capture):
    dl, srv = journey(page, shop_url, bug=True)
    page.reload()
    page.wait_for_selector("[data-testid=order-id]")
    dl2 = page.evaluate(DL_JS)
    srv2 = page.evaluate("() => window.serverPreview")
    capture("bug mode after reload", {"dataLayer": [e for e in dl2 if isinstance(e, dict)], "serverPreview": srv2})
    tx = [e["ecommerce"]["transaction_id"] for e in events(dl) + events(dl2) if e["event"] == "purchase"]
    assert len(tx) == 2 and len(set(tx)) == 1, "bug 4 reproduced: same transaction_id sent twice"
    purchase_srv = [s for s in srv + srv2 if s["event_name"] == "Purchase"]
    assert purchase_srv and all(s["event_id"] != s["browser_event_id"] for s in purchase_srv), "bug 2 reproduced: event_id mismatch"


def test_no_request_leaves_the_browser(page, shop_url):
    journey(page, shop_url)
    assert page.external_requests == []


def test_schema_rejects_bad_purchases():
    good = {"event": "purchase", "event_id": "evt_0123456789abcdef",
            "ecommerce": {"transaction_id": "CMFR0000001", "value": 10.0, "currency": "EUR",
                          "items": [{"item_id": "SKU0001", "item_name": "Lamp", "price": 10.0, "quantity": 1}]}}
    assert VALIDATOR.is_valid(good)
    for patch in [{"transaction_id": "(not set)"}, {"currency": "eur"}, {"value": -1}, {"items": []}]:
        bad = json.loads(json.dumps(good))
        bad["ecommerce"].update(patch)
        assert not VALIDATOR.is_valid(bad), patch
    no_id = json.loads(json.dumps(good))
    del no_id["event_id"]
    assert not VALIDATOR.is_valid(no_id)
