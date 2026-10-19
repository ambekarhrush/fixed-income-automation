"""Append-only, timestamped call ledger. Calls are committed to git by CI,
so the history is public and cannot be quietly edited after the fact."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[1] / "ledger" / "calls.jsonl"


def _hash(rec: dict) -> str:
    return hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()[:16]


def read_calls(path: Path = LEDGER) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def last_call(ticker: str, path: Path = LEDGER) -> dict | None:
    calls = [c for c in read_calls(path) if c["ticker"] == ticker]
    return calls[-1] if calls else None


def record_call(ticker: str, stance: str, conviction: int, risk_score: int, reason: str,
                ref_metric: dict | None = None, path: Path = LEDGER) -> dict | None:
    """Only logs when the stance changes, so the ledger is a list of decisions, not noise."""
    prev = last_call(ticker, path)
    if prev and prev["stance"] == stance:
        return None
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ticker": ticker, "stance": stance, "conviction": conviction,
        "risk_score": risk_score, "reason": reason[:400],
        "ref": ref_metric or {}, "prev_hash": prev["hash"] if prev else None,
    }
    rec["hash"] = _hash(rec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    return rec


def score_calls(calls: list[dict], outcomes: dict[str, float]) -> list[dict]:
    """outcomes: {ticker: change in risk score (or spread, bp) since the call}.
    Underweight is right if credit worsened; overweight if it improved."""
    out = []
    for c in calls:
        d = outcomes.get(c["ticker"])
        if d is None or c["stance"] == "neutral":
            continue
        hit = (d > 0) if c["stance"] == "underweight" else (d < 0)
        out.append({**c, "outcome_delta": d, "hit": hit})
    return out
