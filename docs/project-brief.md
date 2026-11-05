# Sentinel Credit Analyst

*LLM-assisted SEC research pipeline · Prepared 5 November 2026*

## The research question

Can an automated high-yield analyst read debt disclosures while keeping numerical analysis deterministic?

## Approach

SEC XBRL feeds fundamentals; an LLM extracts debt tranches and drafts constrained memos. Plain code checks source quotes, amounts and debt reconciliation before tranches enter recovery waterfalls. A hash-linked stance ledger records changes.

## Evidence and result

The verifier checks source quotes, amounts and reconciliation to reported total debt. A deliberately fabricated extraction appears in the test suite. The latest reviewed daily workflow runs failed at the agent step, so unattended daily coverage has not been established.

## Scope and limitations

The verifier’s tolerance and source-text matching do not guarantee complete debt extraction. Scores are heuristic; no bond spread or market-return validation exists. A hash chain alone does not prevent history rewriting or independently timestamp calls.

## Explore the project

Use the sample site preview or a clearly labelled mock/rules-only walkthrough. python -m pytest -q is offline; SEC retrieval needs an identifying user agent and live access.

## Sources and evidence

[data/run_summary.json](../data/run_summary.json) · [tests/test_core.py](../tests/test_core.py) · [.github/workflows/sentinel.yml](../.github/workflows/sentinel.yml)

---

Hrush Ambekar · Research snapshot reviewed 5 November 2026. See linked source files for full methodology, figures and reproducibility.
