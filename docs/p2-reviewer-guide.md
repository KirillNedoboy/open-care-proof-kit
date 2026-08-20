# P2 deterministic reviewer guide

The P2 reviewer is a local, deterministic acceptance check for the OpenCare
Health Workspace contract. Run it from the repository root:

```bash
python -m evals.p2_review
```

A successful run exits with status `0` and prints the required `P2 REVIEW`
pass lines, six security counters at zero, and `result: PASS`. Any failed
assertion exits with status `1` and prints `result: FAIL`.

## What it exercises

The scenario uses a fixed UTC clock (`2026-08-20 09:30`), a temporary SQLite
database, and temporary source storage. It creates synthetic Alice, Bob,
Carol, read-only caregiver, and legacy-v1 actors, then drives the real Product
Core lifecycle and authorization services. It covers:

- owner, bounded caregiver, read-only, legacy-v1, hidden-person, and revoked
  capability boundaries;
- medication correction history, recorded condition, and lab result/unit
  provenance;
- one unified pending review containing multiple fact families, including
  rejected, unsupported, and pending correction candidates;
- Person-isolated source metadata and timeline label mappings;
- a scheduled Visit with Questions, a schema-v2 Brief containing medication,
  condition, and lab evidence, and readability of a v1 Brief revision;
- portable-vault version/filename coherence and unchanged P1/G1-G5 boundary
  constants; and
- fail-closed revocation and unauthorized mutation attempts.

The counters are named exactly as follows and must remain zero:

- `cross_person_workspace_exposures`
- `stale_person_render_acceptances`
- `unauthorized_ui_backed_mutations`
- `hidden_record_count_exposures`
- `hidden_source_metadata_exposures`
- `legacy_scope_expansions`

## Guarantees and scope

This is an offline synthetic reviewer, not a production health-data check. It
never contacts a network service, Ollama, Sentient, Docker, a browser, or an
external account, and it does not use real health data or an LLM. Each run
creates and discards its own temporary state; it does not migrate, mutate, or
export the repository database.

The reviewer verifies backend service and authorization behavior plus the
observable contract represented by the scenario. It does not replace the
frontend browser-generation/race tests: the
`stale_person_render_acceptances` counter is intentionally asserted as zero by
this offline reviewer while stale-render enforcement remains covered by the
frontend test suite. Run the focused regression test as well:

```bash
python -m pytest tests/test_p2_reviewer.py
```

Keep this reviewer narrow and deterministic. Changes to Product Core,
family-access policy, export/version constants, or the P2 contract should
update the scenario and its focused test together; do not weaken authorization
or privacy checks to make the reviewer pass.
