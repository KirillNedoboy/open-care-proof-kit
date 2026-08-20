# Grant Submission Answers (Supporting Grant Artifact)

> This copy is for grant context and is not the canonical product roadmap or
> current repository status. See [ADR 0001](adr/0001-opencare-product-direction.md)
> and [project status](project-status.md).

Copy these answers into a Sentient Open Source AGI Grant or similar public-goods application. Keep the wording conservative. This public repo is local-first trust infrastructure with health as the stress-test domain. It is not a clinical product.

## Current implementation note

G1-G5, P1, P2, D1, and P3 are implemented on public `main`. The planning and
future-work language below is historical grant context, not a pending product
roadmap. Public fixtures remain synthetic/de-identified; no clinical authority
is claimed.

Character counts:

- Short summary: 651
- Long summary: 1155
- Final blurb: 642

## A. Project Title

OpenCare Proof Kit: privacy-first personal/family medical workspace infrastructure with deterministic trust, provenance, safety, audit, and evals.

## B. One-Sentence Pitch

OpenCare Proof Kit is an open-source, self-hosted foundation for a privacy-first
personal/family health workspace with deterministic trust, provenance, safety,
audit, review, document evidence, and bounded genetics research.

## C. Short Summary

OpenCare Proof Kit is an open-source, self-hosted foundation for a privacy-first
personal/family health workspace. The repo implements Product Core records,
Family Access, D1 PDF/TXT evidence documents, P3 Genetics Research Studio,
explicit consent, Person-scoped permissions, deny-by-default authorization,
access audit, export, and offline backup/recovery. The existing
Medication-to-Doctor Briefing / PGx demo remains a narrow reference workflow.
The project does not provide diagnosis, treatment recommendation, dosage
guidance, medication selection, or clinical decision support.

## D. Longer Summary

OpenCare Proof Kit is a local-first, open-source foundation for a privacy-first
personal/family health workspace. Public repository fixtures are synthetic and
de-identified; the self-hosted runtime is designed for user-owned sensitive
health, document, and genetic data under explicit local authorization.

The older Medication-to-Doctor Briefing / PGx demo still runs as a narrow
reference workflow. D1 document evidence and P3 Genetics Research Studio are
implemented on public `main`; P3 remains selective, evidence-backed, and
bounded. The design rule is deterministic tools before LLM. The vault remains
the source of truth, and any model remains an interface layer rather than
clinical authority. The project does not provide diagnosis, treatment
recommendation, dosage guidance, medication selection, start/stop advice,
clinical decision support, or clinical validation.

## E. Problem

People and families already have useful health context before genetics enters the picture: medications, labs, visits, documents, timeline events, family relationships, and open questions. Today that context is usually scattered across PDFs, portals, notes, and memory. At the same time, generic LLM products can blur evidence, hide provenance, and produce unsafe or unsupported health language.

The open-source ecosystem needs a concrete pattern for handling sensitive personal context in a way that stays local, source-grounded, auditable, person-scoped, and fail-closed when support is missing.

## F. Solution

OpenCare Proof Kit provides a working local reference implementation:

- a synthetic Health/Family Vault foundation that is useful without DNA;
- deterministic loader and validation for person/family medical context;
- a provenance-preserving read model;
- committed reviewer artifacts plus a read-only reviewer page;
- a deterministic context/provenance trace graph;
- a family identity/access boundary with explicit consent and person-scoped permissions;
- deny-by-default authorization, access audit, person export, and offline recovery boundaries;
- the existing Medication-to-Doctor Briefing / PGx demo for a narrow reference workflow;
- JSON audit metadata, executable evals, CI, and deterministic trust metrics.

The result is not a medical chatbot. It is a reviewer-friendly trust and provenance substrate that other builders can inspect, fork, and reuse.

## G. Why This Should Be Open-Source

Trust infrastructure for sensitive AI should be inspectable. Open source lets reviewers and downstream builders audit:

- data models;
- provenance rules;
- deterministic builders;
- safety boundaries;
- audit metadata;
- eval cases;
- CI and trust checks.

The value is not a closed patient workflow. The value is a reusable public-good pattern for sensitive local agent systems.

## H. Why This Is Local-First / Private-By-Default

Medication, family, and genetic context are high-sensitivity data categories. OpenCare Proof Kit keeps the current repo local-first so a reviewer can inspect what was loaded, what was transformed, what evidence was used, what safety boundaries were applied, and what outputs were produced without requiring cloud upload.

Public repository fixtures remain synthetic/de-identified only. The self-hosted
runtime is designed for user-owned sensitive health, document, and genetic data
under explicit local authorization; generated `reports/` artifacts remain
ignored by Git.

## I. Who Benefits

- people who want a private workspace for medical and family context;
- families who need shared context, provenance, and explicit access boundaries across health, document, and genetics context;
- open-source builders working on sensitive local agents;
- clinicians and reviewers who want visible sources, boundaries, and audit metadata;
- grant reviewers looking for concrete trustworthy-AI infrastructure rather than a pitch deck.

## J. What Has Been Built So Far

- Public GitHub repository: `https://github.com/KirillNedoboy/open-care-proof-kit`
- Synthetic Health/Family Vault Core schemas and synthetic family dataset.
- Deterministic Health/Family Vault loader and validation.
- Deterministic Health/Family Vault read model.
- Deterministic local reviewer artifacts: JSON read model, Markdown summary, manifest.
- Committed synthetic reviewer artifacts under `docs/assets/health_vault/`.
- Privacy/safety threat model, provenance semantics, and vault artifact guarantees docs.
- Read-only local reviewer UI at `/demo/health-vault`.
- Deterministic context/provenance trace graph in the reviewer UI.
- Phase 2 Family Identity and Access Boundary, including family access UI and policy documentation.
- Person-scoped permissions, deny-by-default authorization, access audit, export, and offline recovery boundaries.
- GitHub Actions CI plus deterministic local trust metrics.
- Existing Medication-to-Doctor Briefing / PGx demo, report output, audit output, and eval suite.
- D1 document evidence ingest and P3 Genetics Research Studio with bounded Evidence/Explore modes.

## K. Technical Architecture

```txt
synthetic family vault dataset
  -> deterministic loader / validation
  -> deterministic read model
  -> deterministic reviewer artifacts
  -> read-only reviewer UI
  -> context/provenance trace graph

synthetic briefing inputs
  -> demo genotype parser
  -> local evidence pack loader
  -> deterministic PGx rule matcher
  -> safety policy
  -> Markdown report
  -> JSON audit
  -> eval runner
```

The product rule is vault first, genetics second, LLM third as interface. The LLM/report writer is not the source of medical truth.

## L. Safety Model

The safety model is explicit and fail-closed:

- no source, no claim;
- unsupported flows must stay visibly unsupported;
- the reviewer vault layer is recorded context only, not medical interpretation;
- every surfaced reviewer artifact keeps provenance or fails closed;
- the PGx briefing path still requires safety note, clinician-review note, limitations, sources, and audit metadata;
- evals and trust metrics are engineering checks, not clinical validation.

The repo must not provide diagnosis, treatment recommendation, dosage guidance, medication selection, start/stop medication advice, clinical decision support, or clinical validation claims.

## M. Evaluation / Audit Model

The current validation commands and fresh results are maintained in
[docs/project-status.md](project-status.md). Counts in this submission
document are not a current baseline and must be refreshed before reuse.

GitHub Actions CI runs tests, lint, type checks, evals, and trust metrics. The trust metrics report reads eval totals plus committed Health/Family Vault manifest flags such as `demo_only`, `synthetic`, `no_llm_generation`, `no_genetics`, `no_medical_advice`, and `generated_reports_ignored`.

## N. Why Sentient / Grant Alignment

This project fits an open-source public-goods grant because it focuses on
infrastructure that makes personal agents more inspectable, private, and
controllable. The repo is local-first, deterministic-first, and explicit about
what is not clinical authority. Public fixtures are synthetic/de-identified;
self-hosted runtime capabilities are local and authorization-bound.

It does not assume closed deployment, platform lock-in, or current Sentient integration. It is the kind of substrate another builder can inspect and reuse.

## O. Historical support framing

The planning language in this section predates the completed D1/P3 public-main
implementation. It is retained as grant context, not as a pending product
roadmap.

Grant support could help fund better ingest/provenance tooling, reviewer
automation, synthetic eval coverage, trust metrics, release hygiene, clinician-
review handoffs, and future interface/adapters beyond the completed P3 boundary.

## P. Historical 30-Day Milestones

- Maintain the Phase 2 reviewer pack and GitHub release hygiene.
- Tighten reviewer docs around vault-first behavior, family access, and trust metrics.
- Add artifact refresh and reviewer-pack maintenance instructions.
- Expand wording scans and packaging checks for submission hygiene.
## Q. Historical 60-Day Milestones

- Add local ingest/provenance conventions for documents, labs, medications, visits, and notes.
- Improve clinician-review handoff exports without adding clinical action.
- Extend trust metrics and reviewer surfaces around provenance gaps and unsupported states.
## R. Historical 90-Day Milestones

- Research optional future genetics and interface layers without breaking the vault-first architecture.
- Define privacy, provenance, and safety requirements before any real-data or adapter work.
- Extend trust metrics around provenance gaps, access boundaries, and unsupported states.
- Define privacy, provenance, and safety requirements before any future genetics or interface work.

## S. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Overclaiming clinical capability | Keep the repo synthetic/demo-only, deterministic-first, and explicit that it is not medical advice or clinical validation. |
| Source-less or unsupported context being overstated | Fail-closed provenance rules, reviewer artifacts, and trust metrics. |
| Privacy drift | Local-first defaults, ignored generated reports, and synthetic/de-identified public fixtures. |
| Scope creep into genetics or AI-doctor positioning | Product rule: vault first, genetics second, LLM third as interface. |
| Reviewer confusion | Compact reviewer pack, visible safety boundary language, CI, and reproducible validation commands. |

## T. Non-Goals

OpenCare Proof Kit does not provide or promise:

- diagnosis;
- treatment recommendation;
- medication choice recommendation;
- dosage guidance;
- start/stop medication instructions;
- clinical decision support;
- clinical validation;
- real patient data in public repository fixtures;
- real genetic data in public repository fixtures;
- FASTQ/BAM/WGS pipeline;
- production genome interpretation;
- SaaS/auth/payments/Telegram/blockchain;
- cloud raw genotype upload by default.

## U. Repository / Demo Instructions

Repository:

```txt
https://github.com/KirillNedoboy/open-care-proof-kit
```

Run locally:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints/python312.txt -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Inspect first:

```txt
http://127.0.0.1:8000/demo/health-vault
http://127.0.0.1:8000/family-access
docs/final_reviewer_pack.md
docs/assets/health_vault/family-vault-summary.md
docs/assets/health_vault/family-vault-manifest.json
```

The existing PGx reference workflow remains available through the local demo pages and CLI.

## V. Final Short Application Blurb

OpenCare Proof Kit is an open-source, self-hosted foundation for a privacy-first personal/family health workspace. The current repo combines a synthetic Health/Family Vault reviewer surface with a Phase 2 family identity/access boundary: explicit consent, person-scoped permissions, deny-by-default authorization, audit, export, and recovery controls. It does not provide diagnosis, treatment recommendation, dosage guidance, or clinical decision support.

## Application Wording Guardrails

Use:

- "personal/family medical workspace foundation"
- "vault first"
- "synthetic/demo-only"
- "reviewer artifacts"
- "read-only reviewer UI"
- "provenance trace graph"
- "trust metrics"
- "not medical advice"

Avoid:

- "AI doctor"
- "diagnosis"
- "treatment recommendation"
- "dosage guidance"
- "clinical decision support"
- "real patient upload"
- "real genetic data support"
- "whole genome interpretation"
