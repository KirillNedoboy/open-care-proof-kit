# AGENTS.md

## Project overview

OpenCare Proof Kit is an open-source, self-hosted Personal and Family Health
Workspace plus reusable trust infrastructure for sensitive personal AI agents.

Public `main` contains the completed implementation sequence:

- G1 Trust Envelope
- G2 Consent-Gated Runtime
- G2.5 optional Sentient compatibility
- G3 Model Portability
- G4 Portable Trust Package
- G5 Ecosystem Validation
- P1 Evidence-Grounded Ingest
- P2 Usable Family Workspace
- D1 Evidence Document Ingest
- P3 Genetics Research Studio

There is no G6.

Current Product Core schema is v9. The implementation includes Person-scoped
records, provenance and human review, medications, recorded conditions, labs,
Visits and Visit Briefs, bounded PDF/TXT document ingest, Family Access v1-v3,
separate genetics grants, Genetics Workspace, family genetics comparison, and
bounded Genetics Evidence/Explore Research Mode.

Public repository fixtures, tests, screenshots, reviewer artifacts, and examples
must contain synthetic or de-identified data only. A self-hosted runtime is
designed to process user-owned sensitive health, document, and genetic data
locally under explicit authorization, provenance, review, consent, export, and
audit boundaries.

OpenCare is not an AI doctor, diagnostic authority, treatment planner, dosage
recommender, medication start/stop authority, clinical decision-support system,
or clinically validated software.

## Canonical product rule

The product remains useful without genetics or an LLM.

```text
user-owned source
-> immutable registration
-> extraction / candidate
-> provenance
-> human review
-> canonical record
-> timeline / visit preparation
-> bounded agent context
-> validated answer or refusal
-> audit / receipt
```

AI is never the source of canonical truth.

## Repository role

This repository is the combined OpenCare product and trust foundation. Do not
create a replacement repository or parallel implementation for already-shipped
capabilities.

Canonical current-state documents:

- `docs/project-status.md`
- `docs/capability-matrix.md`
- `AGENTS.product-direction.md`
- `docs/architecture/module-boundaries.md`
- `docs/roadmap/product-core-roadmap.md`

Historical documents may preserve earlier phase language. Historical text must
not override current-state documents or current runtime behavior.

## Current module map

```text
app/product_core
    Product Core schema v9, Sources, candidates, canonical records, timeline,
    Visits, Visit Briefs, document ingest, genetics persistence, export,
    backup/recovery.

app/family_access
    Actor sessions, Person authorization, relationships, assignments, consent,
    Family Access scope generations v1-v3.

app/agent_trust
    Trust Envelope, policy-bound context, execution receipt, portable trust
    package contracts.

app/agent
    Bounded agent context, providers, validation, audit, consent-gated runtime.

app/genetics
    Consumer-genotype parsing, normalization, evidence assessment, family
    comparison, Research contracts and validation.

app/product_core/genetics.py
    Persisted genetics source/dataset/finding/review/research service.

app/templates/genetics.html
app/static/genetics.js
    Genetics Workspace / Research Studio UI.

evals
    Deterministic G5/P1/P2/D1/P3 reviewers and trust metrics.

data
    Synthetic demo data and local evidence packs only.

docs
    Product, security, architecture, reviewer, grant, and historical material.
```

## Authorization invariants

Authorization is deny-by-default.

- Server-side Actor identity comes from the validated session.
- Every health operation is explicitly Person-scoped.
- Relationships alone are not grants.
- Family Access assignments use their frozen scope generation.
- Family Access v1 and v2 remain frozen.
- Family Access v3 adds document scopes.
- Genetics access is separate from ordinary Family Access:
  - `genetics.read`
  - `genetics.write`
  - `genetics.research`
  - `genetics.compare`
  - `genetics.export`
- Ordinary caregiver health access must never imply genetics access.
- Genetics comparison requires authorization for every involved Person.
- Revocation must take effect on the next authorization decision.
- Hidden or unauthorized Persons fail closed.

Do not weaken these boundaries for convenience, demo behavior, or agent tooling.

## Provenance and canonical-record invariants

- Sources are registered before derived claims.
- Source identity and integrity are preserved.
- Candidate facts are not canonical facts.
- Human review controls promotion into canonical records.
- Unsupported, conflicting, absent, no-call, build-incompatible, or ambiguous
  states remain explicit.
- Derived views may be rebuilt; canonical truth must not depend on derived output.
- Agent output must not mutate canonical records.
- Research hypotheses must never silently become canonical facts.

## Document-ingest boundary

D1 supports bounded local ingestion of:

- TXT
- text-layer PDF

It does not imply OCR, image interpretation, cloud extraction, clinical NER, or
LLM extraction.

Document bytes and extracted page text remain source/provenance material. Normal
agent context must contain only explicitly selected authorized projections, not
unrestricted raw document contents.

## Genetics boundary

P3 supports bounded consumer-genotype workflows with selective normalized
observations and evidence-backed findings.

Permanent genetics constraints:

- raw genome bytes are highly sensitive;
- raw genome never enters provider context;
- do not weaken this to “not sent by default”;
- only authorized, minimized, selected projections may enter Research context;
- ambiguous A/T and C/G orientation must fail closed for supported findings
  unless orientation is resolved;
- absence on a genotyping chip means “not tested / not present in supplied
  coverage”, not “variant absent”;
- incompatible genome builds fail closed;
- no implicit liftover;
- family comparison is compatibility/IBS-style evidence only, never legal or
  forensic kinship proof;
- no FASTQ/BAM/CRAM/gVCF/WGS production pipeline unless a new explicit product
  decision approves it.

## AI and Research Mode rules

Do not apply one flat “LLM may only summarize” rule to every OpenCare surface.
The allowed behavior depends on the mode.

### Ordinary health-agent / evidence-grounded paths

Allowed:

- summarize authorized records;
- explain supplied evidence and provenance;
- explain limitations and uncertainty;
- draft clinician-reviewable summaries;
- generate questions for discussion.

Required:

- claims remain grounded in supplied authorized evidence;
- citations or provenance references must resolve to supplied context;
- uncertainty must remain explicit.

Not allowed:

- invented sources;
- diagnosis-as-fact;
- treatment plans;
- medication selection;
- dosage changes;
- start/stop medication instructions;
- autonomous canonical-record mutation.

### Genetics Evidence Mode

Evidence Mode is stricter.

- Use selected normalized observations, reviewed findings, selected evidence
  entries, and selected authorized health records only.
- Do not use unsupported model background as evidence.
- Do not convert ambiguous or unresolved observations into supported claims.
- Every supported claim must resolve to authorized selected evidence.

### Genetics Explore Mode

Explore Mode is intentionally broader than ordinary evidence-only summarization.

Allowed when explicitly labelled:

- hypotheses;
- possible mechanisms;
- alternative explanations;
- model-background knowledge;
- counterarguments;
- conflicting interpretations;
- missing-information analysis;
- questions worth investigating;
- cross-domain genetics + authorized health-context synthesis.

Required epistemic labels include:

- observed
- supported
- plausible
- speculative
- unsupported/conflicting

Explore Mode must preserve a mandatory Devil’s Advocate / counterevidence view.

Explore Mode still must not:

- state a diagnosis as established fact;
- claim variants prove a disease or symptom cause;
- instruct treatment;
- tell a user to start/stop/change medication;
- recommend or alter dosage;
- mutate canonical records;
- cite unauthorized evidence as supplied evidence.

Framing text such as “literature says”, “external claim”, or “quoted claim” must
never bypass diagnosis or prescribing safety rules. Quoting or discussing an
external statement is not permission to repeat it as actionable advice to the
Person.

## Trust Envelope / agent invariants

The agent receives an authorized envelope or selected context projection, never
unrestricted vault/database access.

The trust boundary composes:

- Actor identity
- explicit Person scope
- delegated access
- requested action
- purpose-bound consent
- selected evidence
- provenance
- policy decision
- disclosure preview
- constrained execution
- output validation
- execution receipt

Security invariants are absolute:

- unauthorized item never emitted;
- canonical mutation never through the agent path;
- external call never without required consent;
- raw genome never sent through the supported provider path.

Hash integrity is SHA-256 integrity, not signatures, PKI, blockchain, or remote
attestation.

## G5 exact state

Do not misreport G5.

Agent Skills interoperability is verified across:

- OMP 17.3.5
- Hermes Agent 0.19.0

The root Agent Plugins two-independent-client gate remains external evidence
pending.

Exact machine state:

```text
READY_FOR_SECOND_CLIENT_SMOKE
```

Never rename that root-plugin gate to PASS.

## Permanent non-goals

Without a new explicit product decision, do not add:

- diagnosis;
- treatment recommendation;
- dosage recommendation;
- medication start/stop authority;
- clinical genetics authority;
- clinical validation claims;
- OCR;
- FASTQ/BAM/CRAM/gVCF/WGS production pipelines;
- autonomous canonical-record mutation;
- SaaS multi-tenant product expansion;
- payments;
- Telegram;
- blockchain;
- cloud raw-genome upload;
- MCP as a new project objective;
- deployment changes unrelated to an explicitly approved task.

Do not claim HIPAA certification, GDPR certification, FDA approval, medical
device compliance, or clinical readiness.

## Package and release identity

The development package version may be ahead of the latest published tag.

Do not infer a release from a development version such as `0.3.0.dev0`.

Do not create a tag, release, PR, deploy, or mutate GitHub settings unless the
user explicitly asks for that exact remote action.

Do not hardcode a mutable current `main` SHA into long-lived current-state prose.
When a historical implementation baseline matters, label it explicitly as a
historical or phase-final baseline.

## Testing

Use Python 3.12.

Core validation commands:

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m evals.trust_metrics
python -m evals.g5_review
python -m evals.p1_review
python -m evals.p2_review
python -m evals.d1_review
python -m evals.p3_review
python -m pip check
git diff --check
node --check app/static/product_core_workspace.js
node --check app/static/genetics.js
```

Run the relevant focused tests while iterating. Run the full required suite once
after changes stabilize.

Never weaken tests, evaluators, security counters, authorization checks, or
review gates merely to obtain PASS.

## Review checklist

A change is acceptable only if it:

- preserves local/self-hosted defaults;
- preserves Person isolation;
- preserves provenance and human review;
- keeps sensitive repository fixtures synthetic/de-identified;
- keeps raw genome outside provider context;
- preserves mode-specific Research boundaries;
- keeps diagnosis/treatment/dosage authority out of the product;
- keeps agent paths unable to mutate canonical records;
- includes tests for changed behavior;
- keeps current-state docs aligned with verified behavior;
- does not misreport `READY_FOR_SECOND_CLIENT_SMOKE`.
