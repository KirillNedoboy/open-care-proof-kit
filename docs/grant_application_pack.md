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

OpenCare Proof Kit is not a medical chatbot. It is an open-source, self-hosted
personal/family health workspace with an implemented Product Core, Family
Workspace, D1 document evidence ingest, P3 Genetics Research Studio, explicit
consent, person-scoped permissions, deny-by-default authorization, audit,
export, and recovery controls.

## Long Pitch

The strongest current story is vault first. OpenCare is useful before DNA enters
the picture. Public fixtures remain synthetic/demo-only, while the self-hosted
runtime is designed for user-owned sensitive health, document, and genetic data
under explicit local authorization. Current live surfaces include `/workspace`,
`/family-access`, `/genetics`, and `/demo/health-vault`.

That vault layer is paired with visible review infrastructure: privacy/safety threat models, provenance semantics, artifact guarantees, an authorization matrix, GitHub Actions CI, and trust metrics. A reviewer can inspect the docs, artifacts, routes, access policy, and validation evidence directly.

The existing Medication-to-Doctor Briefing / PGx path remains a narrow reference
workflow. D1 document evidence and P3 Genetics Research Studio are now
implemented on public `main`; P3 provides bounded reviewed associations,
selective indexing, family comparison, and Evidence/Explore Research Mode.
Genetics remains secondary to the vault and the LLM remains an interface layer,
not the source of truth.

The repo contains synthetic/de-identified fixtures only. It does not claim
diagnosis, treatment recommendation, dosage guidance, medication selection,
start/stop medication advice, clinical decision support, or clinical validation.

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
- the existing PGx briefing path as a narrow evidence/safety reference workflow;
- D1 document evidence ingest and P3 Genetics Research Studio with bounded
  Evidence/Explore modes.

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
- public repository fixtures are synthetic/de-identified only;
- the self-hosted runtime is designed for user-owned sensitive health,
  document, and genetic data under explicit local authorization.

The reviewer vault layer is provenance/traceability only, not medical interpretation.

## Evals And Trust Checks

Fresh validation results are maintained in
[docs/project-status.md](project-status.md). Counts in earlier grant
snapshots are historical and must not be treated as the current baseline.

GitHub Actions CI runs tests, lint, type checks, evals, and trust metrics on `push` and `pull_request`.

## Milestones

### Implemented now

- Product Core schema v9 with People, records, review, Visits, Visit Briefs,
  document evidence, export, backup, and recovery;
- Family Access v1-v3 with explicit consent and separate genetics grants;
- D1 PDF/TXT document evidence ingest with immutable bytes and provenance;
- P3 Genetics Workspace, selective consumer-genotype indexing, reviewed
  evidence, PGx associations, family comparison, Genetics Export, and
  Evidence/Explore Research Mode;
- G1-G5 trust infrastructure, deterministic reviewers, CI, and trust metrics;
- synthetic Health/Family Vault Core and Medication-to-Doctor Briefing / PGx
  reference workflow;

### Historical planned work (superseded by completed public-main implementation)

- local ingest/provenance conventions for documents, labs, medications, visits, and notes;
- Conditions/Labs and clinician-review handoff improvements;
- broader evals and trust metrics around provenance gaps and access boundaries;
- future interface/adapters beyond the completed P3 boundary only after explicit
  privacy and safety decisions;

## Requested Support / Use Of Funds

Support would help fund:

- vault-first ingest/provenance tooling;
- reviewer artifact maintenance and verification tooling;
- broader synthetic eval and trust coverage;
- cleaner clinician-review handoff exports;
- conservative research on future interface decisions beyond the completed P3
  boundary.

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Overclaiming capability | Keep the repo synthetic/demo-only and explicit about non-goals. |
| Reviewer confusion | Keep the reviewer pack, threat model, trust metrics, and route boundaries easy to inspect. |
| Scope creep into genetics too early | Keep the product rule visible: vault first, genetics secondary. |
| Safety drift in future UI or prose | Preserve wording scans, trust metrics, and fail-closed provenance rules. |

## Non-Goals

OpenCare Proof Kit does not aim to provide:

- diagnosis;
- treatment recommendation;
- dosage guidance;
- medication selection advice;
- start/stop medication advice;
- real patient or real genetic data in public repository fixtures;
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
