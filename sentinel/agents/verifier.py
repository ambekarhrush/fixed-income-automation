"""Verifier agent: deterministic checks that every LLM-extracted figure exists in the source.

This deliberately does NOT use an LLM. A model grading its own output is not verification.
Each tranche gets a status: verified | quote_not_found | amount_not_in_quote | reconciliation_fail.
"""
from __future__ import annotations

import re


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9.%$]", "", s.lower())


def _amount_forms(amount: float) -> set[str]:
    m = amount / 1e6
    forms = {f"{m:,.0f}", f"{m:.0f}", f"{m:,.1f}", f"{m:.1f}"}
    if m >= 1000:
        b = m / 1000
        forms |= {f"{b:.1f}billion", f"{b:.2f}billion", f"{b:g}billion", f"{m:,.0f}"}
    forms |= {f"{m:g}million"}
    return {_norm(f) for f in forms}


def verify_tranches(tranches: list[dict], source_text: str, xbrl_total_debt: float | None = None,
                    tolerance: float = 0.15) -> dict:
    src = _norm(source_text)
    log, verified = [], []
    for t in tranches:
        q = _norm(t.get("source_quote", ""))
        if len(q) < 12 or q not in src:
            status = "quote_not_found"
        elif not any(f in q for f in _amount_forms(t["amount"])):
            status = "amount_not_in_quote"
        else:
            status = "verified"
        t = {**t, "verification": status}
        log.append({"tranche": t["name"], "amount": t["amount"], "status": status})
        if status == "verified":
            verified.append(t)

    recon = None
    if xbrl_total_debt and verified:
        total = sum(t["amount"] for t in verified)
        gap = abs(total - xbrl_total_debt) / xbrl_total_debt
        recon = {"extracted_total": total, "xbrl_total": xbrl_total_debt, "gap_pct": gap,
                 "status": "ok" if gap <= tolerance else "reconciliation_fail"}
    n = len(tranches)
    return {
        "verified": verified, "log": log, "reconciliation": recon,
        "precision": (len(verified) / n) if n else None,
        "usable": bool(verified) and (recon is None or recon["status"] == "ok"),
    }
