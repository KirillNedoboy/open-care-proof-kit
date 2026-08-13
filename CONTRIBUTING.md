# Contributing

OpenCare Proof Kit welcomes contributions that strengthen local-first, evidence-grounded, safety-checked health AI infrastructure without expanding the project into clinical decision-making.

## Project Boundaries

This project is not an AI doctor, diagnostic system, treatment planner, medication recommendation engine, or dosage tool.

Do not contribute changes that add:

- diagnosis;
- dosage recommendation;
- start/stop medication instruction;
- treatment planning;
- real patient data;
- FASTQ, BAM, WGS, or clinical genomics interpretation;
- SaaS auth, payments, Telegram, or blockchain;
- cloud upload of raw health or genetic data by default;
- clinical claims beyond the local demo evidence pack.

## Welcome Contributions

Useful contributions include:

- stronger eval cases for unsafe wording and missing evidence;
- evidence-pack validation improvements;
- safer report and audit formatting;
- clearer reviewer documentation;
- CI or local validation automation;
- synthetic/demo data improvements that do not resemble real patient records;
- local-first privacy and audit tooling.

## Out Of Scope Contributions

The following are out of scope for the current MVP:

- real clinical advice features;
- medication choice or dosage guidance;
- real patient import workflows;
- genomic pipeline expansion into FASTQ/BAM/WGS;
- cloud-first raw genotype processing;
- user accounts, payments, bots, or production SaaS deployment.

## Development Setup

Use Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints/python312.txt -e ".[dev]"
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints/python312.txt -e ".[dev]"
```

## Required Checks

Run before opening a PR:

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m evals.g5_review
python -m app.cli demo-report --drug sertraline --out-dir reports
python -m app.cli demo-report --drug aspirin --out-dir reports
```

Windows PowerShell without activating:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.g5_review
.\.venv\Scripts\python.exe -m app.cli demo-report --drug sertraline --out-dir reports
.\.venv\Scripts\python.exe -m app.cli demo-report --drug aspirin --out-dir reports
```

Generated files under `reports/` must remain ignored and must not be committed.

## Evidence-Pack Rules

Evidence-pack changes must:

- include explicit source metadata;
- use allowed source domains enforced by the local validator;
- include limitations;
- remain demo-only unless a future phase explicitly changes the project scope;
- keep `clinician_review_required=true`;
- keep `clinical_action_allowed=false`;
- avoid source-less medical claims.

If an evidence source is not represented in the local pack, the system must fail closed with no clinical claim.

## No Real Patient Data

Do not put real patient data in:

- commits;
- issues;
- pull requests;
- screenshots;
- generated reports;
- eval cases;
- demo fixtures.

Use synthetic/demo data only. If you accidentally include sensitive data, remove it immediately and disclose the mistake privately rather than in a public issue.

## Trust Contract Changes (Sentient G1)

The trust contract (`opencare-trust-envelope/1`, `opencare-execution-receipt/1`) is literal and versioned. Any change to field meaning, canonicalization, controlled purpose/action/tool registries, schema content, required invariants, or hash preimages is breaking and requires a **new literal contract version** — never a reinterpreted one (G1 §13). Before proposing such a change:

- state the versioning decision explicitly (new literal, not a bump of the same literal);
- update the machine schemas (`schemas/agent-trust/` via `scripts/export_agent_trust_schemas.py`, never hand-edited) and the committed canonical vectors;
- update/add validators and stable reason codes, with tests for every affected path;
- document the migration reasoning: what changes, why it is breaking, and how old-version artifacts are handled (never silently downgraded);
- do not add optional fields to a v1 model — v1 rejects extras; a new version is required.

## Authorization Adapter Contributions

Adapters implement the generic `AuthorizationAdapter` Protocol (`app/agent_trust/`). They **adapt** live authority; they must never become a second authorization system, consent store, evidence store, or safety engine.

- The adapter returns an `AuthorizationDecision` from live state (e.g., Family Access); it must not accept a caller-supplied decision, identity, or arbitrary JSON.
- Every adapter change must pass the trust conformance suite (G1 envelope/decision invariants) and preserve exact **Person and resource scope** and **provenance** semantics: no cross-Person selection, no scope expansion, no source-less evidence.
- The generic layer stays free of OpenCare imports; health-specific authority code lives in `app/agent/trust_adapter.py`.

## Provider Contributions (Sentient G3)

Providers implement the `AgentProvider` contract (`app/agent/providers/`).

- Provider input is the exact projected disclosure only — never `ProductCoreRuntime`, repositories, DB connections, Family Access, credentials, session stores, or the broad `AgentContext`.
- Provider output is untrusted and must pass the existing G2 answer validation before it can be returned; a provider is never a source of truth and never mutates canonical state.
- Every provider must pass the shared G3 provider tests (descriptor identity, projection-only input, structured output, no Product-Core exposure, fail-closed on malformed/oversized/timeout responses, no cloud or second-provider fallback).
- Real providers additionally carry model identity and tool-call data; the executed provider/model must equal the descriptor bound by consent.

## Agent Plugin Changes (Sentient G4/G5)

The committed package `agent-plugins/opencare-trust/` is built **deterministically** from the canonical skill source (`skills/`), never by hand-editing the plugin copy; the packaging script is the only writer and the drift test asserts byte-identity.

- `plugin.json` stays strict Agent Plugins 1.0.0 (canonical `$schema`, only permitted root fields, name constraints).
- Every skill must conform to the Agent Skills specification: valid frontmatter with `name` matching its directory, `description` present.
- No secrets, credentials, tokens, private keys, absolute host paths, real person data, or raw health payloads in the package (invariant 13 scan).
- Package containment: no path escapes, no symlinks/junctions/reparse points out of the plugin root.
- The package remains skill-only: **no `mcp.json`**, no hooks, no code execution (MCP and other component types are explicit exclusions).
- Cross-client loading evidence (like `docs/assets/g5/client-interop-evidence.md`) must record client/version, package hashes before and after load, skills discovered, and cleanup — with no raw logs, tokens, usernames, or chat transcripts.

## Evaluation Contributions (Sentient G5)

Every security-regression case in the G5 corpus (`evals/g5/corpus.json`) must **define the expected invariant it protects** and a binary expected outcome (`refused_prepare` / `refused` / `answered` plus stable reason codes, expected/forbidden evidence, `provider_must_be_called`, `mutation_allowed`).

- Cases are deterministic and offline; scripted providers only; fixed synthetic clock; no model-dependent judgments as enforcement evidence.
- A failing case is a P0 contract defect, not a graded weakness — do not relax the expected outcome to make a case pass.
- New metrics in `evals/g5/metrics.py` must report numerators and denominators; do not introduce target percentages.
- The reviewer (`python -m evals.g5_review`) must stay a single local command with deterministic exit codes.

## Synthetic Data Rule

All eval cases, trust fixtures, and demo artifacts are **synthetic only**: no real identifying health, family, person, consent, or credential data anywhere in the repo (commits, fixtures, cases, screenshots, reports). Use fixed synthetic actors (e.g., Alice/Bob/Carol), persons, and evidence IDs; keep the fixed fixture clock. If real data is ever required, it is out of scope for this repository and must not be added.
