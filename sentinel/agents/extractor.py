"""Extraction agent: LLM reads the debt footnote and returns a structured debt stack."""
from __future__ import annotations

from sentinel.llm import LLMProvider

SYSTEM = """You are a leveraged-finance analyst extracting a company's debt stack from a 10-K debt footnote.
Return JSON: {"tranches": [{"name": str, "type": "secured_loan|secured_notes|unsecured_notes|convertible|subordinated|revolver|other",
"principal_musd": number, "coupon": str|null, "maturity_year": int|null, "rank": int, "source_quote": str}]}.
Rules: rank 1 = most senior (secured), 2 = senior unsecured, 3 = subordinated/convertible.
principal_musd is outstanding principal in USD millions as stated. source_quote MUST be copied verbatim
from the text (max 30 words) and contain the principal figure. If unsure, omit the tranche. Never invent."""


def extract_debt_stack(llm: LLMProvider, debt_text: str) -> list[dict]:
    data = llm.complete_json(SYSTEM, f"10-K DEBT FOOTNOTE TEXT:\n{debt_text[:60000]}")
    tranches = data.get("tranches", []) if isinstance(data, dict) else []
    clean = []
    for t in tranches:
        try:
            clean.append({
                "name": str(t["name"])[:120], "type": t.get("type", "other"),
                "amount": float(t["principal_musd"]) * 1e6, "coupon": t.get("coupon"),
                "maturity_year": t.get("maturity_year"), "rank": int(t.get("rank", 2)),
                "source_quote": str(t.get("source_quote", "")),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return clean
