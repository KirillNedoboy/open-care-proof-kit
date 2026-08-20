# Product Core Roadmap

## Current status

The implementation roadmap through P1, P2, D1, and P3 is complete on public
`main`.

This file is no longer a queue of pending Product Core features. It records the
completed implementation sequence and preserves the architectural logic behind
it.

Do not infer a new feature phase from historical sections in this document.
Future product work requires a new explicit product decision.

Do not hardcode the mutable current `main` SHA here. Historical phase-final SHAs
belong in project history or release notes, not in the definition of “current
main”.

## Product thesis

OpenCare is an open-source, self-hosted Personal and Family Health Workspace plus
reusable trust infrastructure for sensitive personal AI agents.

The product remains:

```text
vault first
-> provenance and human review
-> family workspace
-> document evidence
-> bounded AI
-> genetics research
```

OpenCare should be useful without genetics and without an LLM.

## Completed sequence

### Foundation / Trust

| Phase | Outcome | Status |
| --- | --- | --- |
| G1 | Trust Envelope | Complete |
| G2 | Consent-Gated Runtime | Complete |
| G2.5 | Optional Sentient compatibility | Complete |
| G3 | Model Portability | Complete |
| G4 | Portable Trust Package | Complete |
| G5 | Ecosystem Validation engineering | Complete |

G5 has one deliberately separate external evidence gate:

```text
READY_FOR_SECOND_CLIENT_SMOKE
```

Agent Skills interoperability is verified across OMP 17.3.5 and Hermes Agent
0.19.0. Root Agent Plugins two-independent-client validation remains external
evidence pending and must not be relabelled PASS.

There is no G6.

### P1 — Evidence-Grounded Ingest

Completed outcome:

- generic candidate/canonical lifecycle;
- medications, recorded conditions, and labs;
- provenance locators;
- explicit human review;
- unsupported/conflicting states;
- source-backed timeline;
- Visit Brief v2;
- canonical records exposed to bounded agent context.

Core invariant established:

```text
Source
-> Candidate
-> Human Review
-> Canonical Record
-> Timeline / Visit Brief
```

AI output does not promote itself into canonical truth.

### P2 — Usable Family Workspace

Completed outcome:

- actor-scoped workspace;
- explicit Person switching;
- server-derived capabilities;
- Family Access authorization;
- review inbox and provenance surfaces;
- lifecycle controls;
- Visit preparation UX;
- responsive workspace behavior;
- race-safe Person changes.

Core authorization invariant:

```text
Actor
-> explicit Person
-> assignment / scope generation
-> authorized operation
```

Relationships alone are not grants.

### D1 — Evidence Document Ingest

Completed outcome:

- local TXT ingest;
- text-layer PDF ingest;
- immutable Source bytes;
- deterministic bounded extraction;
- page-level extraction records;
- exact provenance spans;
- candidate creation from selected evidence;
- human review before canonical truth;
- document-specific Family Access v3 scopes;
- portable vault v4 document inclusion;
- backup/recovery support.

D1 intentionally does not imply:

- OCR;
- image interpretation;
- cloud extraction;
- LLM extraction;
- autonomous clinical NER.

Core flow:

```text
document
-> immutable Source
-> deterministic extraction
-> provenance span
-> candidate
-> human review
-> canonical record
```

Raw document bytes/page text do not become unrestricted agent context.

### P3 — Genetics Research Studio

Completed outcome:

- immutable local consumer-genotype Source;
- selective normalized observations;
- explicit genome-build and coverage state;
- versioned genetics evidence entries;
- reviewed genetics findings;
- separate revocable genetics grants;
- `/genetics` workspace;
- PGx lens;
- family comparison over authorized indexed loci;
- Evidence Mode;
- Explore Mode;
- explicit epistemic labels;
- counterevidence / Devil’s Advocate;
- separate Genetics Export;
- bounded Research receipts.

Core flow:

```text
raw genotype
-> immutable genetics Source
-> selective normalized variants
-> evidence-backed finding candidate
-> human review
-> reviewed finding
-> bounded Genetics Research context
```

Raw genome never enters provider context.

Research hypotheses never become canonical facts automatically.

## Current Product Core baseline

Current implementation baseline:

- Product Core schema v9;
- Family Access v1 frozen;
- Family Access v2 frozen;
- Family Access v3 document scopes;
- separate genetics grants:
  - `genetics.read`
  - `genetics.write`
  - `genetics.research`
  - `genetics.compare`
  - `genetics.export`
- Visit Brief content schema v2;
- v1 Visit Brief revisions remain readable;
- ordinary Person portable vault format v4;
- Genetics Export separate from ordinary vault export.

## AI boundary after P3

OpenCare now has multiple AI behavior classes and they must not be collapsed into
one obsolete rule.

### Ordinary health / evidence-grounded assistance

- source-constrained;
- authorized context only;
- provenance-aware;
- uncertainty explicit;
- no invented evidence;
- no diagnosis/treatment/dosage authority.

### Genetics Evidence Mode

- reviewed selected evidence only;
- unresolved ambiguity fails closed;
- supported claims require selected evidence;
- no unsupported model background as evidence.

### Genetics Explore Mode

May generate explicitly labelled:

- hypotheses;
- mechanisms;
- alternatives;
- model-background possibilities;
- counterarguments;
- missing-information analysis;
- questions worth investigating.

Still prohibited:

- diagnosis-as-fact;
- causal certainty unsupported by evidence;
- treatment instructions;
- medication start/stop/change;
- dosage instructions;
- autonomous canonical-record mutation.

External/literature/quoted framing is not a safety bypass.

## Permanent architecture invariants

All future work must preserve:

1. User-owned source first.
2. Immutable source identity/integrity.
3. Provenance-preserving derivation.
4. Human review before canonical promotion.
5. Explicit Actor and Person authorization.
6. Separate genetics authorization.
7. Deny-by-default access.
8. Purpose/consent-aware external disclosure.
9. Minimized agent context.
10. Raw genome excluded from provider context.
11. Validated output/refusal.
12. Audit/receipt.
13. No agent path to silent canonical mutation.
14. No diagnosis, treatment, or dosage authority.

## Deferred capabilities are not implied next steps

The following remain outside the implemented roadmap unless a new explicit
decision approves them:

- OCR;
- production VCF/gVCF/WGS pipelines;
- FASTQ/BAM/CRAM processing;
- mandatory external genetics services;
- clinical diagnosis;
- autonomous treatment;
- dosage recommendation;
- clinical decision support;
- SaaS multi-tenant expansion;
- cloud raw-genome storage/transmission;
- MCP as a product objective.

Their presence in old design notes must not be interpreted as an approved next
phase.

## Repository / ecosystem follow-ups are not product phases

The following may still be useful operational work but do not reopen the Product
Core roadmap:

- root Agent Plugins second-client external validation;
- GitHub branch-protection / required-check policy;
- GitHub license metadata recognition;
- refreshed current Workspace / Genetics screenshots;
- release/tag decision.

These are repository, governance, presentation, or ecosystem-evidence tasks, not
new product phases.

## Historical design evolution

Earlier Phase 1 / Phase 2 / Phase 3 documents and ADRs remain useful historical
context. Their old “non-goals” describe what was intentionally excluded at that
time.

When an earlier section says that family permissions, document ingest, or
genetics were deferred, read it historically. Those capabilities are now
implemented.

Historical material must not override:

- `docs/project-status.md`;
- `docs/capability-matrix.md`;
- `AGENTS.md`;
- `AGENTS.product-direction.md`;
- current runtime tests and reviewers.

## Next product step

None is selected here.

The completed roadmap ends at P3.

Any future product phase must start with a new explicit product decision that
states:

- user problem;
- scope;
- non-goals;
- data/privacy boundary;
- authorization impact;
- provenance/review impact;
- agent-policy impact;
- acceptance criteria;
- validation plan.

Until such a decision exists, do not invent P4, G6, or another feature phase.
