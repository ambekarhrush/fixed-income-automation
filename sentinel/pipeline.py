"""Orchestrator: run the full agent chain for one issuer or the whole universe.

    python -m sentinel.pipeline --universe universe/us_hy.csv
    python -m sentinel.pipeline --ticker CCL --no-llm
"""
from __future__ import annotations

import argparse
import csv
import json
import traceback
from datetime import date
from pathlib import Path

from sentinel.agents.events import classify_filings
from sentinel.agents.extractor import extract_debt_stack
from sentinel.agents.verifier import verify_tranches
from sentinel.agents.writer import draft_memo
from sentinel.analysis import credit
from sentinel.data import edgar
from sentinel.data.fundamentals import annual_metrics
from sentinel.ledger import record_call
from sentinel.llm import get_provider

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "issuers"


def build_issuer(ticker: str, name: str = "", sector: str = "", llm=None, use_llm: bool = True) -> dict:
    cik = edgar.cik_for(ticker)
    years = annual_metrics(edgar.company_facts(cik))
    if not years:
        raise ValueError("no XBRL annual data")
    fy = max(years)
    y, prev = years[fy], years.get(fy - 1, {})
    m, m_prev = credit.credit_metrics(y), credit.credit_metrics(prev) if prev else {}
    runway = credit.liquidity_runway(y)
    score, why = credit.risk_score(m, runway)
    prev_score = credit.risk_score(m_prev, credit.liquidity_runway(prev))[0] if prev else None

    filings = edgar.recent_filings(cik)
    events = classify_filings(filings)[:8]

    rec = {
        "ticker": ticker, "name": name, "sector": sector, "cik": cik, "fiscal_year": fy,
        "as_of": date.today().isoformat(), "metrics": m, "metrics_prev": m_prev,
        "history": {k: credit.credit_metrics(v) for k, v in list(years.items())[-5:]},
        "provenance": y.get("_src", {}), "maturity_wall": credit.maturity_wall(y),
        "liquidity_runway": runway, "risk_score": score, "risk_score_prev": prev_score,
        "risk_drivers": why, "events": events, "debt_stack": [], "verification": None,
        "waterfall": None, "memo": None,
    }

    tenk = next((f for f in filings if f["form"] == "10-K"), None)
    if use_llm and tenk:
        text = edgar.filing_text(tenk["url"])
        section = edgar.debt_section(text)
        tranches = extract_debt_stack(llm, section)
        v = verify_tranches(tranches, text, xbrl_total_debt=m.get("debt"))
        rec["debt_stack"], rec["verification"] = v["verified"], {k: v[k] for k in ("log", "reconciliation", "precision", "usable")}
        rec["source_10k"] = tenk["url"]
        if v["verified"] and m.get("ebitda") and m["ebitda"] > 0:
            rec["waterfall"] = {name: credit.recovery_waterfall(ev, v["verified"])
                                for name, ev in credit.ev_scenarios(m["ebitda"]).items()}

    if use_llm:
        fact_sheet = {k: rec[k] for k in ("ticker", "name", "sector", "fiscal_year", "metrics", "metrics_prev",
                                          "liquidity_runway", "risk_score", "risk_score_prev", "risk_drivers",
                                          "maturity_wall")}
        fact_sheet["events"] = [{k: e[k] for k in ("date", "label")} for e in events]
        fact_sheet["verified_debt_stack"] = [{k: t[k] for k in ("name", "amount", "rank", "maturity_year")}
                                              for t in rec["debt_stack"]]
        rec["memo"] = draft_memo(llm, fact_sheet)
    else:
        stance = "underweight" if score >= 50 else "overweight" if score <= 15 else "neutral"
        rec["memo"] = {"stance": stance, "conviction": 2, "summary": "Rules-based stance (no LLM run).",
                       "thesis": "; ".join(why) or "No material risk flags.", "catalysts": [], "risks": [],
                       "trade_expression": "", "unsupported_numbers": []}
    return rec


def run(universe: Path | None, tickers: list[str], use_llm: bool):
    rows = list(csv.DictReader(universe.open())) if universe else [{"ticker": t} for t in tickers]
    llm = get_provider() if use_llm else None
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for r in rows:
        t = r["ticker"].upper()
        try:
            rec = build_issuer(t, r.get("name", ""), r.get("sector", ""), llm, use_llm)
            (OUT / f"{t}.json").write_text(json.dumps(rec, indent=1, default=str))
            memo = rec["memo"]
            record_call(t, memo["stance"], int(memo.get("conviction", 2)), rec["risk_score"],
                        memo.get("summary", ""), {"net_leverage": rec["metrics"]["net_leverage"]})
            summary.append({"ticker": t, "ok": True, "score": rec["risk_score"]})
            print(f"{t:6} score={rec['risk_score']:3}  {memo['stance']}")
        except Exception as e:  # keep the run going; failures are reported, not hidden
            summary.append({"ticker": t, "ok": False, "error": str(e)})
            print(f"{t:6} FAILED: {e}")
            traceback.print_exc(limit=1)
    (ROOT / "data" / "run_summary.json").write_text(json.dumps(
        {"date": date.today().isoformat(), "provider": getattr(llm, "name", "none"), "results": summary}, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", type=Path)
    ap.add_argument("--ticker", action="append", default=[])
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    run(a.universe, a.ticker, not a.no_llm)
