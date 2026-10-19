"""Turn XBRL companyfacts into a clean annual credit-metric set."""
from __future__ import annotations

TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "operating_income": ["OperatingIncomeLoss"],
    "d_and_a": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
                "DepreciationAmortizationAndAccretionNet"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "total_debt": ["LongTermDebt", "DebtInstrumentCarryingAmount", "LongTermDebtNoncurrent"],
    "current_debt": ["LongTermDebtCurrent", "DebtCurrent"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "equity": ["StockholdersEquity"],
    "maturity_y1": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths"],
    "maturity_y2": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo"],
    "maturity_y3": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree"],
    "maturity_y4": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour"],
    "maturity_y5": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive"],
    "maturity_after5": ["LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive"],
}


def _annual(facts: dict, tag: str) -> dict[int, dict]:
    node = facts.get("facts", {}).get("us-gaap", {}).get(tag)
    if not node:
        return {}
    out: dict[int, dict] = {}
    for unit_vals in node.get("units", {}).values():
        for v in unit_vals:
            if v.get("form") != "10-K" or v.get("fp") != "FY":
                continue
            fy = v.get("fy")
            # latest filing wins for a given fiscal year (restatements)
            if fy and (fy not in out or v["filed"] > out[fy]["filed"]):
                out[fy] = {"val": v["val"], "filed": v["filed"], "accn": v["accn"], "tag": tag}
    return out


def annual_metrics(facts: dict) -> dict[int, dict]:
    """{fiscal_year: {metric: value, '_src': {metric: provenance}}}"""
    years: dict[int, dict] = {}
    for metric, tags in TAGS.items():
        for tag in tags:
            series = _annual(facts, tag)
            if series:
                for fy, rec in series.items():
                    y = years.setdefault(fy, {"_src": {}})
                    if metric not in y:
                        y[metric] = rec["val"]
                        y["_src"][metric] = {"tag": rec["tag"], "accn": rec["accn"]}
                break
    return dict(sorted(years.items()))
