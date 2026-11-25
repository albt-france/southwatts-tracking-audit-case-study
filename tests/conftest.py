"""Fixtures for the dataLayer tests: a local static server for site/demo-shop and a headless Chromium.
Also writes tests/report.html (one row per test, plus the dataLayer captured during the journey)."""
import functools
import html
import http.server
import json
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHOP = ROOT / "site" / "demo-shop"
REPORT = ROOT / "tests" / "report.html"
RESULTS, CAPTURES = [], {}


@pytest.fixture(scope="session")
def shop_url():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SHOP))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    srv.shutdown()


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    external = []
    pg.on("request", lambda r: external.append(r.url) if not r.url.startswith("http://127.0.0.1") else None)
    pg.external_requests = external
    yield pg
    ctx.close()


@pytest.fixture
def capture():
    def _cap(name, data):
        CAPTURES[name] = data
    return _cap


def pytest_runtest_logreport(report):
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        RESULTS.append((report.nodeid.split("::")[-1], report.outcome, (report.longreprtext or "")[-600:]))


def pytest_sessionfinish(session, exitstatus):
    rows = "".join(f"<tr class='{o}'><td>{html.escape(n)}</td><td>{o.upper()}</td><td><pre>{html.escape(d)}</pre></td></tr>"
                   for n, o, d in RESULTS)
    caps = "".join(f"<h3>{html.escape(k)}</h3><pre>{html.escape(json.dumps(v, indent=1)[:6000])}</pre>" for k, v in CAPTURES.items())
    passed = sum(o == "passed" for _, o, _ in RESULTS)
    REPORT.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>dataLayer test report</title>
<style>body{{font-family:'Segoe UI',sans-serif;background:#F3F1EC;margin:24px;color:#0B0B0B}}table{{border-collapse:collapse;background:#fff}}
td,th{{border:1px solid #E1E0D9;padding:6px 10px;vertical-align:top}}.passed td:nth-child(2){{color:#1BAF7A}}.failed td:nth-child(2){{color:#D03B3B}}
pre{{white-space:pre-wrap;font-size:12px;margin:0}}</style></head><body>
<h1>dataLayer test report - demo shop (SIMULATED)</h1>
<p>{passed} / {len(RESULTS)} tests passed. Headless Chromium (Playwright) against site/demo-shop served on 127.0.0.1.
Each ecommerce push is validated against tracking/datalayer.schema.json.</p>
<table><tr><th>Test</th><th>Result</th><th>Detail</th></tr>{rows}</table><h2>Captured dataLayer</h2>{caps}
<p>Independent case study based on public data · not affiliated with or endorsed by SouthWatts</p></body></html>""", encoding="utf-8")
