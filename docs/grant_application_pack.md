# Grant Application Pack (Supporting Grant Artifact)

> Grant and reviewer materials describe verified evidence and intended public
> framing. They do not define the current product roadmap or runtime status.
> See [ADR 0001](adr/0001-opencare-product-direction.md),
> [project status](project-status.md), and [capability matrix](capability-matrix.md).

## Project Title

OpenCare Proof Kit: self-hosted personal/family health workspace infrastructure with deterministic provenance, safety, audit, and person-scoped access.

## Related Submission Docs

- `docs/grant_submission_answers.md` for copy-paste application answers.
- `docs/grant_short_pitch.md` for 15-second, 30-second, and 60-second variants.
- `docs/grant_milestones.md` for conservative post-grant milestones.
- `docs/final_reviewer_pack.md` for the compact reviewer index.

## Short Pitch

OpenCare Proof Kit is not a medical chatbot. It is an open-source, self-hosted personal/family health workspace with a synthetic reviewer surface and an implemented Phase 2 family identity/access boundary: explicit consent, person-scoped permissions, deny-by-default authorization, audit, export, and recovery controls.

## Long Pitch

The strongest current story is vault first. OpenCare should be useful before DNA enters the picture. The repo proves that with a synthetic/demo-only Health/Family Vault and a live local family workspace: deterministic schemas, provenance-preserving read models, reviewer artifacts, a read-only `/demo/health-vault` page, and a Phase 2 family identity/access boundary.

That vault layer is paired with visible review infrastructure: privacy/safety threat models, provenance semantics, artifact guarantees, an authorization matrix, GitHub Actions CI, and trust metrics. A reviewer can inspect the docs, artifacts, routes, access policy, and validation evidence directly.

The existing Medication-to-Doctor Briefing / PGx path remains intact as a narrow reference workflow. It is useful here because it stress-tests evidence, safety, audit, and eval behavior. But it is no longer the main product framing. Genetics is still a future enhancement layer. Any future LLM remains an interface layer, not the source of truth.

The repo is synthetic/demo-only. It does not claim real-patient support, real-genetic-data support, diagnosis, treatment recommendation, dosage guidance, medication selection, start/stop medication advice, clinical decision support, or clinical validation.

## Origin Story

OpenCare grew out of a practical family need. As a parent managing recurring
health needs across several family members and coordinating information from
different clinicians and care settings, I found that existing tools were
fragmented, cloud-dependent, and poorly suited to preserving context,
provenance, permissions, and privacy. The project is being built first for my
own family, then as open-source infrastructure that other families can inspect,
adapt, and use. This motivation is intentionally described without publishing
diagnoses or identifying medical details about family members.

## Problem

Sensitive personal AI needs more than a chat box. People and families need a place to organize medications, labs, visits, documents, questions, and family context with visible provenance. Reviewers and downstream builders need to inspect what data moved, what is source-backed, what is only recorded context, and where safety boundaries are enforced.

## Solution

OpenCare Proof Kit provides:

- a synthetic Health/Family Vault foundation that is useful without DNA;
- deterministic provenance-preserving builders;
- committed reviewer artifacts plus a read-only reviewer UI;
- a deterministic context/provenance trace graph;
- a local Actor/family access boundary with explicit consent and person-scoped permissions;
- deny-by-default authorization, access audit, person export, and offline recovery boundaries;
- CI, evals, and trust metrics;
- the existing PGx briefing path as a narrow evidence/safety reference workflow.

## Why Open Source

This work is valuable because it is inspectable. Another builder can audit:

- the vault schema;
- provenance rules;
- deterministic builders;
- trust metrics;
- eval cases;
- reviewer docs and artifacts.

That is a better fit for public-goods funding than a closed medical assistant.

## Why Private And Local-First

The repo is designed so reviewers can inspect the system locally without cloud dependency or hidden upload. The current implementation uses synthetic/demo-only data and keeps generated `reports/` artifacts ignored by Git.

## Current Reviewer Surface

Inspect first:

- `http://127.0.0.1:8000/demo/health-vault`
- `http://127.0.0.1:8000/family-access`
- `docs/final_reviewer_pack.md`
- `docs/assets/health_vault/family-vault-summary.md`
- `docs/assets/health_vault/family-vault-manifest.json`
- `docs/privacy_safety_threat_model.md`
- `docs/provenance_semantics.md`
- `docs/vault_artifact_guarantees.md`
- `docs/security/family-access-authorization-matrix.md`
- `docs/security/family-access-threat-model.md`

The reviewer can inspect:

- safety banner and boundaries;
- family overview and provenance coverage;
- context/provenance trace graph;
- committed manifest trust flags;
- CI and trust metrics outputs.

## Technical Architecture

```txt
synthetic family vault dataset
  -> deterministic loader / validation
  -> deterministic read model
  -> deterministic reviewer artifacts
  -> read-only reviewer UI
  -> context/provenance trace graph

synthetic briefing inputs
  -> demo genotype parser
  -> local evidence pack
  -> deterministic PGx matcher
  -> safety policy
  -> Markdown report
  -> JSON audit
  -> eval runner
```

The product rule stays: vault first, genetics second, LLM third as interface.

## Safety Model

The repo must stay conservative:

- no diagnosis;
- no treatment recommendation;
- no dosage guidance;
- no medication selection advice;
- no start/stop advice;
- no clinical decision support;
- no clinical validation claim;
- no real patient support;
- no real genetic data support.

The reviewer vault layer is provenance/traceability only, not medical interpretation.

## Evals And Trust Checks

Fresh validation results are maintained in
[docs/project-status.md](project-status.md). Counts in earlier grant
snapshots are historical and must not be treated as the current baseline.

GitHub Actions CI runs tests, lint, type checks, evals, and trust metrics on `push` and `pull_request`.

## Milestones

### Implemented now

- synthetic Health/Family Vault Core
- Phase 2 Family Identity and Access Boundary
- deterministic loader/validation
- deterministic read model
- deterministic local artifacts
- committed reviewer artifacts
- threat model / provenance / artifact guarantee docs
- read-only reviewer UI
- context/provenance trace graph
- CI and trust metrics
- Medication-to-Doctor Briefing / PGx reference workflow

### Next grant-funded work

- local ingest/provenance conventions for documents, labs, medications, visits, and notes;
- Conditions/Labs and clinician-review handoff improvements;
- broader evals and trust metrics around provenance gaps and access boundaries;
- future genetics/interface research only after the vault and family-access foundations remain safe and inspectable.

## Requested Support / Use Of Funds

Support would help fund:

- vault-first ingest/provenance tooling;
- reviewer artifact maintenance and verification tooling;
- broader synthetic eval and trust coverage;
- cleaner clinician-review handoff exports;
- conservative research on future genetics and interface layers after the current foundation is stable.

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Overclaiming capability | Keep the repo synthetic/demo-only and explicit about non-goals. |
| Reviewer confusion | Keep the reviewer pack, threat model, trust metrics, and route boundaries easy to inspect. |
| Scope creep into genetics too early | Keep the product rule visible: vault first, genetics later. |
| Safety drift in future UI or prose | Preserve wording scans, trust metrics, and fail-closed provenance rules. |

## Non-Goals

OpenCare Proof Kit does not aim to provide:

- diagnosis;
- treatment recommendation;
- dosage guidance;
- medication selection advice;
- start/stop medication advice;
- real patient or real genetic data support in the current repo;
- FASTQ/BAM/WGS processing;
- clinical decision support;
- clinical validation claims.

## Application Wording Guardrails

Use:

- "not a medical chatbot"
- "privacy-first personal/family medical workspace foundation"
- "vault first"
- "synthetic/demo-only"
- "reviewer artifacts"
- "read-only reviewer UI"
- "provenance trace graph"
- "CI and trust metrics"

Avoid:

- "AI doctor"
- "diagnosis"
- "treatment recommendation"
- "dosage guidance"
- "clinical decision support"
- "real patient upload"
- "real genome analysis"
