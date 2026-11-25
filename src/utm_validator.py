"""UTM validator and builder (SIMULATED links of the fictional Client M).

Rules (docs/utm_governance.md):
  - utm_source, utm_medium, utm_campaign present and lowercase, no spaces;
  - (utm_source, utm_medium) is an approved pair;
  - utm_campaign = <market>_<campaign type>_<year>q<quarter>, e.g. fr_prospecting_2026q4;
  - known variants are mapped to the approved value (mapping table) so the agency can fix the link.

    python src/utm_validator.py                       validate data/sim/utm_catalogue.parquet + build utm/utm_builder.xlsx
    python src/utm_validator.py "https://...?utm_source=fb&utm_medium=Paid_Social"   validate one URL
Outputs: data/out/utm_validation.csv, utm/utm_builder.xlsx
"""
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
APPROVED = {("google", "cpc"), ("meta", "paid_social"), ("linkedin", "paid_social"), ("cm360", "display"), ("newsletter", "email")}
SOURCES = sorted({s for s, _ in APPROVED})
MEDIUMS = sorted({m for _, m in APPROVED})
MARKETS = ["fr", "de", "es", "it", "uk", "nl", "pl", "us"]
CAMPAIGN_RE = re.compile(r"^[a-z]{2}_[a-z]+_20\d{2}q[1-4]$")
SOURCE_MAP = {"facebook": "meta", "fb": "meta", "instagram": "meta", "ig": "meta", "meta": "meta",
              "google": "google", "adwords": "google", "linkedin": "linkedin", "lnkd": "linkedin", "cm360": "cm360", "dcm": "cm360"}
MEDIUM_MAP = {"paid_social": "paid_social", "paidsocial": "paid_social", "paid-social": "paid_social", "social": "paid_social",
              "cpc": "cpc", "ppc": "cpc", "display": "display", "banner": "display", "email": "email"}


def validate(source: str, medium: str, campaign: str) -> list[str]:
    issues = []
    for name, v in (("utm_source", source), ("utm_medium", medium), ("utm_campaign", campaign)):
        if not v:
            issues.append(f"{name} missing")
        elif v != v.lower():
            issues.append(f"{name} not lowercase")
        if v and " " in v:
            issues.append(f"{name} contains spaces")
    if source and medium and (source, medium) not in APPROVED:
        issues.append(f"pair {source}/{medium} not approved")
    if campaign and not CAMPAIGN_RE.match(campaign):
        issues.append("utm_campaign off convention")
    return issues


def suggest(source: str, medium: str, campaign: str, platform: str | None = None) -> tuple[str, str, str]:
    s = SOURCE_MAP.get((source or "").lower().strip(), (source or "").lower())
    m = MEDIUM_MAP.get((medium or "").lower().strip(), (medium or "").lower())
    if s == "meta" or platform in ("meta", "linkedin"):
        m = "paid_social"                       # social platforms: the only approved medium
    if not m and platform:
        m = {"google_ads": "cpc", "cm360": "display"}.get(platform, "paid_social")
    c = (campaign or "").strip().lower().replace(" ", "_")
    return s, m, c


def validate_url(url: str) -> dict:
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    s, m, c = q.get("utm_source", ""), q.get("utm_medium", ""), q.get("utm_campaign", "")
    issues = validate(s, m, c)
    return {"url": url, "status": "PASS" if not issues else "FAIL", "issues": "; ".join(issues),
            "suggested": "" if not issues else "utm_source={}&utm_medium={}&utm_campaign={}".format(*suggest(s, m, c))}


def build_workbook(results: pd.DataFrame) -> None:
    wb = Workbook()
    head = PatternFill("solid", fgColor="2A78D6")
    ws = wb.active
    ws.title = "builder"
    cols = ["landing_url", "market", "utm_source", "utm_medium", "campaign_type", "year_quarter", "utm_campaign (formula)",
            "final_url (formula)", "check (formula)"]
    ws.append(cols)
    examples = [("https://shop.clientm.example/fr/", "fr", "meta", "paid_social", "prospecting", "2026q4"),
                ("https://shop.clientm.example/de/", "de", "google", "cpc", "search", "2026q4"),
                ("https://shop.clientm.example/uk/", "uk", "linkedin", "display", "awareness", "2026q4")]
    for i in range(2, 102):
        row = list(examples[i - 2]) if i - 2 < len(examples) else ["", "", "", "", "", ""]
        row += [f'=IF(OR(B{i}="",E{i}="",F{i}=""),"",LOWER(B{i}&"_"&E{i}&"_"&F{i}))',
                f'=IF(OR(A{i}="",C{i}="",D{i}="",G{i}=""),"",A{i}&"?utm_source="&LOWER(C{i})&"&utm_medium="&LOWER(D{i})&"&utm_campaign="&G{i})',
                f'=IF(A{i}="","",IF(COUNTIFS(lists!$D$2:$D$20,LOWER(C{i}),lists!$E$2:$E$20,LOWER(D{i}))=0,"FAIL: pair not approved",'
                f'IF(OR(ISNUMBER(SEARCH(" ",G{i})),G{i}=""),"FAIL: campaign","PASS")))']
        ws.append(row)
    for c in ws[1]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), head
    for col, w in zip("ABCDEFGHI", [34, 8, 12, 13, 14, 12, 28, 70, 24]):
        ws.column_dimensions[col].width = w
    red, green = PatternFill("solid", fgColor="F4C7C6"), PatternFill("solid", fgColor="CDEFE0")
    ws.conditional_formatting.add("I2:I101", FormulaRule(formula=['LEFT(I2,4)="FAIL"'], fill=red))
    ws.conditional_formatting.add("I2:I101", FormulaRule(formula=['I2="PASS"'], fill=green))
    lists = wb.create_sheet("lists")
    lists.append(["market", "utm_source", "utm_medium", "approved_source", "approved_medium", "campaign_type"])
    pairs = sorted(APPROVED)
    types = ["search", "shopping", "prospecting", "retargeting", "display", "awareness", "newsletter"]
    for i in range(max(len(MARKETS), len(pairs), len(types))):
        lists.append([MARKETS[i] if i < len(MARKETS) else None, SOURCES[i] if i < len(SOURCES) else None,
                      MEDIUMS[i] if i < len(MEDIUMS) else None, pairs[i][0] if i < len(pairs) else None,
                      pairs[i][1] if i < len(pairs) else None, types[i] if i < len(types) else None])
    for col, ref in (("B", f"lists!$A$2:$A${len(MARKETS) + 1}"), ("C", f"lists!$B$2:$B${len(SOURCES) + 1}"),
                     ("D", f"lists!$C$2:$C${len(MEDIUMS) + 1}"), ("E", f"lists!$F$2:$F${len(types) + 1}")):
        dv = DataValidation(type="list", formula1=f"={ref}", allow_blank=True, showErrorMessage=True,
                            errorTitle="Not in the convention", error="Pick a value from the list (docs/utm_governance.md).")
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}101")
    mp = wb.create_sheet("mapping")
    mp.append(["found (lowercased)", "use instead", "field"])
    for k, v in SOURCE_MAP.items():
        mp.append([k, v, "utm_source"])
    for k, v in MEDIUM_MAP.items():
        mp.append([k, v, "utm_medium"])
    chk = wb.create_sheet("check")
    chk.append(list(results.columns))
    for r in results.itertuples(index=False):
        chk.append(list(r))
    for sheet in (lists, mp, chk):
        for c in sheet[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), head
    chk.column_dimensions["F"].width = 50
    chk.conditional_formatting.add(f"E2:E{len(results) + 1}", FormulaRule(formula=['E2="FAIL"'], fill=red))
    wb.properties.creator = ""
    wb.properties.lastModifiedBy = ""
    (ROOT / "utm").mkdir(exist_ok=True)
    wb.save(ROOT / "utm" / "utm_builder.xlsx")


def main() -> None:
    if len(sys.argv) > 1:
        for url in sys.argv[1:]:
            print(validate_url(url))
        return
    links = pd.read_parquet(ROOT / "data" / "sim" / "utm_catalogue.parquet")
    rows = []
    for r in links.itertuples():
        issues = validate(r.utm_source, r.utm_medium, r.utm_campaign)
        s, m, c = suggest(r.utm_source, r.utm_medium, r.utm_campaign, r.platform)
        rows.append({"link_id": r.link_id, "agency": r.agency, "market": r.market, "platform": r.platform,
                     "status": "PASS" if not issues else "FAIL", "issues": "; ".join(issues),
                     "suggested_source": s, "suggested_medium": m, "suggested_campaign": c})
    res = pd.DataFrame(rows)
    res.to_csv(ROOT / "data" / "out" / "utm_validation.csv", index=False)
    build_workbook(res)
    by = res.groupby("agency").status.apply(lambda x: f"{(x == 'PASS').mean():.0%} pass").to_dict()
    print(f"utm validator: {len(res)} links, {(res.status == 'FAIL').sum()} FAIL | {by} -> utm/utm_builder.xlsx")


if __name__ == "__main__":
    main()
