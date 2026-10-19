"""Event agent: classify new 8-K filings by their SEC item codes (rule-based, auditable)."""
from __future__ import annotations

ITEM_MAP = {
    "1.01": ("Material agreement", 2), "1.03": ("Bankruptcy / receivership", 5),
    "2.01": ("M&A completed", 3), "2.03": ("New debt obligation", 3),
    "2.04": ("Acceleration / default trigger", 5), "2.05": ("Restructuring / exit costs", 3),
    "2.06": ("Material impairment", 4), "3.01": ("Delisting notice", 4),
    "4.01": ("Auditor change", 3), "4.02": ("Non-reliance on financials", 5),
    "5.02": ("Executive / director change", 2), "1.02": ("Agreement terminated", 3),
}


def classify_filings(filings: list[dict], since: str | None = None) -> list[dict]:
    events = []
    for f in filings:
        if f["form"] != "8-K" or (since and f["date"] <= since):
            continue
        for item in (f.get("items") or "").split(","):
            item = item.strip()
            if item in ITEM_MAP:
                label, sev = ITEM_MAP[item]
                events.append({"date": f["date"], "item": item, "label": label,
                               "severity": sev, "url": f["url"]})
    return sorted(events, key=lambda e: (e["severity"], e["date"]), reverse=True)
