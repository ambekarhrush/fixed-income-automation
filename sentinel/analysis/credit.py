"""Deterministic credit analytics. No LLM in here: numbers come from code."""
from __future__ import annotations


def _div(a, b):
    try:
        return None if a is None or not b else a / b
    except TypeError:
        return None


def credit_metrics(y: dict) -> dict:
    ebitda = None
    if y.get("operating_income") is not None:
        ebitda = y["operating_income"] + (y.get("d_and_a") or 0)
    debt = (y.get("total_debt") or 0) + (y.get("current_debt") or 0) or None
    net_debt = None if debt is None else debt - (y.get("cash") or 0)
    fcf = None if y.get("cfo") is None else y["cfo"] - (y.get("capex") or 0)
    return {
        "revenue": y.get("revenue"), "ebitda": ebitda, "debt": debt, "net_debt": net_debt,
        "cash": y.get("cash"), "fcf": fcf,
        "gross_leverage": _div(debt, ebitda), "net_leverage": _div(net_debt, ebitda),
        "interest_coverage": _div(ebitda, y.get("interest_expense")),
        "fcf_to_debt": _div(fcf, debt),
        "ebitda_margin": _div(ebitda, y.get("revenue")),
    }


def maturity_wall(y: dict) -> list[tuple[str, float]]:
    keys = ["maturity_y1", "maturity_y2", "maturity_y3", "maturity_y4", "maturity_y5", "maturity_after5"]
    labels = ["Y+1", "Y+2", "Y+3", "Y+4", "Y+5", "Later"]
    return [(l, y[k]) for k, l in zip(keys, labels) if y.get(k) is not None]


def liquidity_runway(y: dict) -> float | None:
    """Cash + FCF over next 2 years of maturities (>1 = covered without refinancing)."""
    need = (y.get("maturity_y1") or 0) + (y.get("maturity_y2") or 0)
    fcf = (y.get("cfo") or 0) - (y.get("capex") or 0)
    if not need:
        return None
    return ((y.get("cash") or 0) + 2 * max(fcf, 0)) / need


def risk_score(m: dict, runway: float | None) -> tuple[int, list[str]]:
    """0 (safe) to 100 (stressed). Transparent rules, every point explained."""
    score, why = 0, []
    lev = m.get("net_leverage")
    if lev is not None:
        if lev < 0 or (m.get("ebitda") or 0) <= 0:
            if (m.get("ebitda") or 0) <= 0:
                score += 35; why.append("Negative EBITDA")
        elif lev > 6: score += 30; why.append(f"Net leverage {lev:.1f}x > 6x")
        elif lev > 4: score += 18; why.append(f"Net leverage {lev:.1f}x > 4x")
        elif lev > 2.5: score += 8; why.append(f"Net leverage {lev:.1f}x")
    cov = m.get("interest_coverage")
    if cov is not None and cov > 0:
        if cov < 1.5: score += 30; why.append(f"Interest cover {cov:.1f}x < 1.5x")
        elif cov < 3: score += 15; why.append(f"Interest cover {cov:.1f}x < 3x")
    if (m.get("fcf") or 0) < 0:
        score += 15; why.append("Negative free cash flow")
    if runway is not None and runway < 1:
        score += 20; why.append(f"Liquidity covers {runway:.0%} of 2y maturities")
    return min(score, 100), why


def recovery_waterfall(enterprise_value: float, tranches: list[dict]) -> list[dict]:
    """Absolute-priority waterfall. tranches: [{name, amount, rank}] (rank 1 = most senior;
    equal ranks share pro rata)."""
    remaining = max(enterprise_value, 0.0)
    out = []
    for rank in sorted({t["rank"] for t in tranches}):
        group = [t for t in tranches if t["rank"] == rank]
        claim = sum(t["amount"] for t in group)
        paid = min(remaining, claim)
        remaining -= paid
        for t in group:
            share = paid * (t["amount"] / claim) if claim else 0
            out.append({**t, "recovery": share, "recovery_pct": share / t["amount"] if t["amount"] else 0})
    return out


def ev_scenarios(ebitda: float, multiples=(4.0, 6.0, 8.0)) -> dict[str, float]:
    return {f"{m:.0f}x": ebitda * m for m in multiples}
