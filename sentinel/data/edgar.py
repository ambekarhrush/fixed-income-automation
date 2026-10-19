"""SEC EDGAR client: XBRL company facts + filing text. Public, free, no key.

SEC requires a descriptive User-Agent; set SEC_USER_AGENT="Name email@domain".
"""
from __future__ import annotations

import os
import re
import time
from functools import lru_cache

import requests

BASE = "https://data.sec.gov"
UA = os.getenv("SEC_USER_AGENT", "Sentinel research sentinel@example.com")
_last = [0.0]


def _get(url: str) -> requests.Response:
    wait = 0.12 - (time.time() - _last[0])  # stay under SEC's 10 req/s
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r


@lru_cache(maxsize=1)
def ticker_map() -> dict[str, str]:
    data = _get("https://www.sec.gov/files/company_tickers.json").json()
    return {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}


def cik_for(ticker: str) -> str:
    return ticker_map()[ticker.upper()]


def company_facts(cik: str) -> dict:
    return _get(f"{BASE}/api/xbrl/companyfacts/CIK{cik}.json").json()


def submissions(cik: str) -> dict:
    return _get(f"{BASE}/submissions/CIK{cik}.json").json()


def recent_filings(cik: str, forms=("10-K", "10-Q", "8-K"), limit: int = 20) -> list[dict]:
    rec = submissions(cik)["filings"]["recent"]
    out = []
    for i, form in enumerate(rec["form"]):
        if form in forms:
            acc = rec["accessionNumber"][i]
            out.append({
                "form": form, "date": rec["filingDate"][i], "accession": acc,
                "items": rec.get("items", [""] * len(rec["form"]))[i],
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                       f"{acc.replace('-', '')}/{rec['primaryDocument'][i]}",
            })
        if len(out) >= limit:
            break
    return out


def filing_text(url: str, max_chars: int = 400_000) -> str:
    html = _get(url).text
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    return re.sub(r"\s+", " ", text)[:max_chars]


def debt_section(text: str, window: int = 60_000) -> str:
    """Return the slice of a 10-K most likely to hold the debt footnote."""
    for pat in [r"\bLong[- ]Term Debt\b", r"\bDebt\b\s*(?:and|&)?\s*Financing", r"\bBorrowings\b",
                r"\bSenior (?:Secured |Unsecured )?Notes\b"]:
        hits = [m.start() for m in re.finditer(pat, text, re.I)]
        if len(hits) > 1:  # skip the table-of-contents hit
            s = hits[1]
            return text[max(0, s - 2000): s + window]
    return text[:window]
