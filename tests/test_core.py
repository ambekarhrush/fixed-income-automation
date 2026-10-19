import json

from sentinel.agents.events import classify_filings
from sentinel.agents.extractor import extract_debt_stack
from sentinel.agents.verifier import verify_tranches
from sentinel.agents.writer import unsupported_numbers
from sentinel.analysis import credit
from sentinel.data.fundamentals import annual_metrics
from sentinel.ledger import read_calls, record_call, score_calls
from sentinel.llm import MockProvider, parse_json

SOURCE = ("The Company had outstanding $1,250 million of 6.000% Senior Secured Notes due 2029 and "
          "$800 million of 7.625% Senior Unsecured Notes due 2031 as of December 31, 2025.")


def facts(vals):
    return {"facts": {"us-gaap": {tag: {"units": {"USD": [
        {"val": v, "fy": fy, "fp": "FY", "form": "10-K", "filed": f"{fy+1}-02-01", "accn": "x"}
        for fy, v in series.items()]}} for tag, series in vals.items()}}}


def test_annual_metrics_and_credit():
    f = facts({"OperatingIncomeLoss": {2025: 300e6}, "DepreciationDepletionAndAmortization": {2025: 100e6},
               "LongTermDebt": {2025: 2.05e9}, "CashAndCashEquivalentsAtCarryingValue": {2025: 50e6},
               "InterestExpense": {2025: 150e6}, "NetCashProvidedByUsedInOperatingActivities": {2025: 200e6},
               "PaymentsToAcquirePropertyPlantAndEquipment": {2025: 250e6}})
    y = annual_metrics(f)[2025]
    m = credit.credit_metrics(y)
    assert m["ebitda"] == 400e6 and round(m["net_leverage"], 2) == 5.0
    assert round(m["interest_coverage"], 2) == 2.67 and m["fcf"] == -50e6
    score, why = credit.risk_score(m, None)
    assert score == 18 + 15 + 15 and "Negative free cash flow" in why


def test_waterfall_priority():
    w = credit.recovery_waterfall(1.5e9, [{"name": "SSN", "amount": 1.25e9, "rank": 1},
                                          {"name": "SUN", "amount": 0.8e9, "rank": 2}])
    assert w[0]["recovery_pct"] == 1.0 and round(w[1]["recovery_pct"], 4) == 0.3125


def test_extraction_and_verification_catch_hallucination():
    llm = MockProvider([json.dumps({"tranches": [
        {"name": "6.000% Senior Secured Notes due 2029", "type": "secured_notes", "principal_musd": 1250,
         "rank": 1, "maturity_year": 2029, "source_quote": "$1,250 million of 6.000% Senior Secured Notes due 2029"},
        {"name": "7.625% Senior Unsecured Notes", "type": "unsecured_notes", "principal_musd": 900,  # wrong amount
         "rank": 2, "source_quote": "$800 million of 7.625% Senior Unsecured Notes due 2031"},
        {"name": "Term Loan B", "type": "secured_loan", "principal_musd": 500, "rank": 1,  # invented
         "source_quote": "$500 million Term Loan B maturing 2030"}]})])
    v = verify_tranches(extract_debt_stack(llm, SOURCE), SOURCE, xbrl_total_debt=2.05e9)
    status = {l["tranche"]: l["status"] for l in v["log"]}
    assert status["Term Loan B"] == "quote_not_found"
    assert status["7.625% Senior Unsecured Notes"] == "amount_not_in_quote"
    assert len(v["verified"]) == 1 and v["reconciliation"]["status"] == "reconciliation_fail"


def test_writer_flags_invented_numbers():
    memo = {"summary": "Leverage of 5.0x and a $2.3bn hole", "thesis": "", "catalysts": [], "risks": []}
    assert "2.3" in unsupported_numbers(memo, {"net_leverage": 5.0})


def test_events_and_ledger(tmp_path):
    ev = classify_filings([{"form": "8-K", "date": "2026-09-01", "items": "2.03,9.01", "url": "u"},
                           {"form": "8-K", "date": "2026-09-05", "items": "4.02", "url": "u"}])
    assert ev[0]["item"] == "4.02" and ev[1]["label"] == "New debt obligation"
    p = tmp_path / "c.jsonl"
    assert record_call("X", "underweight", 3, 60, "r", path=p)
    assert record_call("X", "underweight", 3, 61, "r", path=p) is None  # no change, no log
    assert record_call("X", "neutral", 2, 30, "r", path=p)["prev_hash"]
    assert score_calls(read_calls(p)[:1], {"X": 10})[0]["hit"]


def test_parse_json_fenced():
    assert parse_json('blah ```json\n{"a": 1}\n``` tail') == {"a": 1}


def test_deepseek_provider_wiring(monkeypatch):
    from sentinel.llm import get_provider
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    p = get_provider("deepseek")
    assert p.name == "deepseek" and "deepseek" in str(p.client.base_url)
