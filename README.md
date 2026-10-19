# Sentinel — an autonomous US high-yield credit analyst

Sentinel covers a universe of US high-yield issuers every weekday, end to end, with no manual steps:

1. **Fundamentals** pulled from SEC EDGAR XBRL (leverage, coverage, FCF, maturity wall, liquidity runway)
2. **Extraction agent** (LLM) reads the 10-K debt footnote and returns the debt stack by tranche
3. **Verifier** (plain code, *not* another LLM) checks every extracted figure against the filing
4. **Analysis** computes a transparent risk score and recovery waterfalls under EV scenarios
5. **Event agent** classifies new 8-Ks (new debt, defaults, impairments, auditor changes)
6. **Writer agent** (LLM) drafts a memo using only numbers from a code-built fact sheet
7. **Ledger** records every change of stance, timestamped and hash-chained, committed to git

Output is a static site on GitHub Pages plus a research notebook.

> Not investment advice. Research and portfolio project.

## Design principle: the LLM reads and writes; code does the numbers

| Step | Who | Why |
|---|---|---|
| Metrics, risk score, waterfall | Code | Numbers must be reproducible |
| Reading unstructured debt footnotes | LLM | What models are good at |
| Checking the LLM's extraction | Code | A model grading itself isn't verification |
| Drafting the memo | LLM, constrained to a fact sheet | Any number not in the fact sheet is flagged |

### How verification works
Each extracted tranche must provide a verbatim `source_quote`. The verifier rejects it if:
- the quote does not appear in the 10-K (`quote_not_found`, which catches invented tranches),
- the stated amount does not appear inside the quote (`amount_not_in_quote`, which catches wrong figures),
- the verified tranches don't reconcile to XBRL total debt within 15% (`reconciliation_fail`).

Only verified tranches feed the waterfall. Extraction precision is shown on every issuer page.
`tests/test_core.py` contains a deliberately hallucinated extraction that the verifier must catch.

## Model-agnostic
```bash
export SENTINEL_LLM_PROVIDER=deepseek    # or anthropic, openai, mock (offline)
export DEEPSEEK_API_KEY=sk-...
export SENTINEL_MODEL=...                # optional override
```
Adding a provider means one class implementing `complete()` in `sentinel/llm/__init__.py`.

## Run it
```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name you@email.com"   # required by SEC
python -m pytest -q
python -m sentinel.pipeline --ticker CCL --no-llm   # rules-only, no API key needed
python -m sentinel.pipeline --universe universe/us_hy.csv
python -m sentinel.site.build                       # -> ./site
```
Notebook: `notebooks/sentinel_walkthrough.ipynb`.
A preview of the site rendered from sample data is in `docs/preview/`.

## Automation (GitHub Actions)
`.github/workflows/sentinel.yml` runs weekdays at 06:17 UTC: tests → agents → site → commit data and ledger → deploy Pages.

Setup: add the secrets `SEC_USER_AGENT` and `DEEPSEEK_API_KEY` (or `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`), optionally set the variable `SENTINEL_LLM_PROVIDER`, then enable Pages with source "GitHub Actions".

## The track record
`ledger/calls.jsonl` only gains a line when an issuer's stance changes. Each line carries the previous line's hash, and git history timestamps the commit, so calls can't be quietly edited after the fact. `ledger.score_calls()` scores calls against later outcomes.

## Limitations (keep this honest and up to date)
- XBRL tagging varies by issuer; some metrics fall back to alternative tags or are missing.
- EBITDA here is operating income + D&A, not covenant or adjusted EBITDA.
- The risk score is a transparent heuristic, not a calibrated default model.
- Debt footnotes in tables can defeat text extraction; the verifier then rejects rather than guesses.
- No bond prices or spreads yet (see roadmap), so calls are scored against fundamentals.
- *Log real model failures you observe here.*

## Roadmap
- [ ] Bond prices and spreads (FINRA TRACE) to score calls against market moves
- [ ] Covenant and LME-vulnerability scanner on credit agreements
- [ ] Earnings-call tone tracking
- [ ] Per-issuer extraction error log aggregated into an evaluation report
