# OpenCare Product Direction

This file is the operational product-direction summary for repository agents.
Current implementation facts belong in `docs/project-status.md` and
`docs/capability-matrix.md`. Historical ADRs and roadmap material must not
override the current runtime.

## Canonical identity

OpenCare is an open-source, self-hosted Personal and Family Health Workspace plus
reusable trust infrastructure for sensitive personal AI agents.

Its product thesis is:

```text
vault first
-> provenance and review
-> usable family workspace
-> document evidence
-> bounded AI
-> genetics research
```

OpenCare should remain useful without DNA and without an LLM.

## Current implementation state

The implemented sequence is complete through:

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

Current Product Core schema is v9.

Family Access v1 and v2 are frozen. Family Access v3 adds document scopes.
Genetics permissions are separate from ordinary Family Access:

- `genetics.read`
- `genetics.write`
- `genetics.research`
- `genetics.compare`
- `genetics.export`

The ordinary Person portable vault format is v4. Genetics Export is separate.
Visit Brief content schema is v2 while v1 revisions remain readable.

## Primary user lifecycle

The core lifecycle is:

```text
sensitive/user-owned source
-> immutable Source
-> extraction or candidate
-> provenance
-> human review
-> canonical record
-> timeline / Visit preparation
-> bounded authorized context
-> validated answer/refusal
-> audit / receipt
```

The first-class product is the health workspace and its evidence lifecycle, not
chat and not genetics.

## AI role

AI is bounded interface and research assistance, not canonical authority.

Ordinary health-agent paths remain evidence-grounded and source-constrained.

Genetics Research Studio has two distinct modes:

### Evidence Mode

- selected/reviewed evidence only;
- authorized context only;
- no unsupported model background presented as evidence;
- citation validation;
- unresolved ambiguity fails closed.

### Explore Mode

Explore Mode may generate explicitly labelled:

- hypotheses;
- mechanisms;
- alternate explanations;
- model-background possibilities;
- counterarguments;
- conflicting interpretations;
- missing information;
- questions worth investigating.

Explore Mode is not sterile summarization. It is intentionally exploratory.

However it still may not:

- establish diagnosis as fact;
- claim a variant proves a disease or symptom cause;
- prescribe treatment;
- choose, start, stop, or change medication;
- recommend or alter dosage;
- mutate canonical records.

External/literature/quoted framing never bypasses these clinical safety
boundaries.

## Genetics sensitivity boundary

Raw genotype/genome bytes are highly sensitive.

The supported Research/provider path receives minimized selected projections,
never the raw genome.

Do not weaken this to “raw genome is not sent by default.”

Ordinary caregiver health access does not imply genetics access.

## Repository-data boundary

Public repository content must remain synthetic/de-identified:

- fixtures;
- tests;
- screenshots;
- reviewer artifacts;
- logs committed to the repository;
- examples.

The self-hosted runtime is designed to process user-owned sensitive
health/document/genetic data locally.

This distinction must remain explicit in README, SECURITY, reviewer, grant, and
agent instructions.

## Product boundaries

OpenCare is not:

- an AI doctor;
- a diagnostic authority;
- a treatment planner;
- a dosage recommender;
- medication start/stop authority;
- clinical decision support;
- clinically validated software.

Do not add clinical-readiness or regulatory-compliance claims.

## Repository role

This repository remains the combined OpenCare product and trust foundation.

Do not:

- split off a replacement “trust-only” product;
- make PGx/genetics the product entry point;
- make chat the product identity;
- recreate already-implemented family/document/genetics layers in parallel;
- treat historical roadmap non-goals as current prohibitions when the capability
  is already implemented.

## Trust infrastructure position

The technical trust contract is the Policy-Bound Context Envelope: an executable
trust boundary between sensitive personal data and AI agents.

The agent receives an authorized envelope/projection, never unrestricted vault
or database access.

Do not position this as a universal agent protocol or as an MCP/A2A replacement.

## G5 exact state

Agent Skills interoperability is verified across OMP 17.3.5 and Hermes Agent
0.19.0.

Root Agent Plugins two-independent-client interoperability remains external
validation pending.

Exact machine state:

```text
READY_FOR_SECOND_CLIENT_SMOKE
```

Do not call that remaining root-plugin gate PASS.

## Classifying new work

Before implementing new functionality, classify it:

1. **Product Core**
   - advances the source -> review -> canonical -> visit lifecycle.

2. **Trust infrastructure**
   - strengthens authorization, provenance, policy, disclosure, validation,
     receipt, or portability without becoming a competing product identity.

3. **Genetics Research Studio**
   - must preserve selective context, separate genetics grants, epistemic
     labels, counterevidence, and the clinical hard boundary.

4. **Reviewer/grant/repository work**
   - describes verified behavior; it must not define new runtime semantics.

5. **External ecosystem validation**
   - may provide evidence for existing gates, but must not weaken the gate to
     manufacture a PASS.

A new product phase requires an explicit product decision. Do not invent the
next phase from historical roadmap text.

## Authoritative documents

- Current repository truth: `docs/project-status.md`
- Capability status: `docs/capability-matrix.md`
- Agent operating rules: `AGENTS.md`
- Current product direction: `AGENTS.product-direction.md`
- Architecture boundaries: `docs/architecture/module-boundaries.md`
- Completed roadmap/history: `docs/roadmap/product-core-roadmap.md`
- Historical product ADR: `docs/adr/0001-opencare-product-direction.md`
