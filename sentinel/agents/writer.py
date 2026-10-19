"""Writer agent: drafts the credit memo from computed numbers only.

The LLM receives a fact sheet built by code and is told to use no other numbers.
Any number in the draft that is not in the fact sheet is flagged afterwards.
"""
from __future__ import annotations

import json
import re

from sentinel.llm import LLMProvider

SYSTEM = """You are a buy-side credit analyst writing a concise internal memo.
Use ONLY the numbers in the FACT SHEET; do not introduce any other figures.
Return JSON: {"stance": "overweight|neutral|underweight", "conviction": 1-5,
"summary": str (<=80 words), "thesis": str, "catalysts": [str], "risks": [str],
"trade_expression": str}. Be specific and falsifiable."""


def draft_memo(llm: LLMProvider, fact_sheet: dict) -> dict:
    memo = llm.complete_json(SYSTEM, "FACT SHEET:\n" + json.dumps(fact_sheet, default=str, indent=1))
    memo["unsupported_numbers"] = unsupported_numbers(memo, fact_sheet)
    return memo


def _numbers(text: str) -> set[str]:
    return {n.rstrip(".").replace(",", "") for n in re.findall(r"\d[\d,]*\.?\d*", text)}


def unsupported_numbers(memo: dict, fact_sheet: dict) -> list[str]:
    allowed = _numbers(json.dumps(fact_sheet, default=str))
    # allow common rounding of allowed figures
    rounded = set()
    for a in allowed:
        try:
            v = float(a)
            rounded |= {f"{v:.0f}", f"{v:.1f}", f"{v:.2f}"}
        except ValueError:
            pass
    text = " ".join(str(memo.get(k, "")) for k in ("summary", "thesis", "catalysts", "risks", "trade_expression"))
    return sorted(n for n in _numbers(text) if n not in allowed | rounded and len(n) > 1)
