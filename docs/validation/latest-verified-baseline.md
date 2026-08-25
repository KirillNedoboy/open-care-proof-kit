# Latest verified repository baseline

Date: 2026-08-25  
Validated code SHA: `a226413b701fa004fa444c2071d0984f6cc14aff`  
Python: `3.12.10`

This is local, synthetic/de-identified evidence for the R3 closure. The
validated code baseline is the third local commit; the commit that adds this
file is documentation-only and does not change runtime behavior.

Results:

- `py -3.12 -m pytest -q`: **707 passed, 4 skipped, 4 warnings**.
- `ruff check app evals tests`: passed.
- `py -3.12 -m mypy app evals`: passed (123 source files).
- `py -3.12 -m evals.runner`: 30/30, all safety rates 0.
- `py -3.12 -m evals.trust_metrics`: passed.
- `py -3.12 -m evals.g5_review`: 20/20; exact state
  `READY_FOR_SECOND_CLIENT_SMOKE`; all security counters 0; deterministic
  replay passed.
- `py -3.12 -m evals.p1_review`: PASS; all counters 0.
- `py -3.12 -m evals.p2_review`: PASS; all counters 0.
- `py -3.12 -m evals.d1_review`: PASS; all counters 0.
- `py -3.12 -m evals.p3_review`: PASS; all counters 0.
- `py -3.12 -m pip check`: verified separately; no broken requirements.
- `git diff --check`: passed.
- `node --check app/static/product_core_workspace.js`: passed.
- `node --check app/static/genetics.js`: passed.
- `node --check app/static/chat.js`: passed.
- `node --check app/static/actor_auth.js`: passed.

Provider truth remains bounded: deterministic is implemented; Ollama is
implemented with live environment smoke `READY_FOR_LIVE_SMOKE`; Responses is
implemented at the contract/configuration boundary and external live smoke is
explicitly unverified. No remote action, deployment, clinical validation, or
production-readiness claim is made by this evidence.
