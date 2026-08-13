# OpenCare Agent Trust — Threat Model

Scope: Sentient G1–G5 agent trust contract (Trust Envelope, Consent-Gated
Runtime, Model Portability, Portable Trust Package, Ecosystem Validation).
This document maps the **G5 adversarial corpus** (and the G1–G4 mechanisms it
exercises) to the **OWASP Top 10 for Agentic Applications 2026** (ASI01–ASI10)
from the OWASP Gen AI Security Project's Agentic Security Initiative.

**Purpose: taxonomy alignment, not certification.** The mapping exists so
reviewers and downstream readers can relate OpenCare's enforced boundaries to
the industry-standard threat vocabulary. It is **not** an OWASP audit,
compliance attestation, or certification claim — OWASP's Top 10 is a risk
framework, not a certification scheme — and it does not assert that OpenCare
"implements" or is "compliant with" any OWASP category.

## 1. What the corpus defends

The G5 corpus (`evals/g5/corpus.json`, 20 cases) is a deterministic,
synthetic-only enforcement matrix. Each case has a fixed expected outcome
(`refused_prepare` / `refused` / `answered` plus stable reason codes) and is
driven by scripted providers on a fixed synthetic clock with synthetic actors
(Alice, Bob, Carol), persons, and evidence. Every case passes or fails as a
binary enforcement property; a failure is a contract defect, not a graded
weakness.

The table below maps each case to the **primary ASI category** whose risk the
case's enforced invariant defends against. Cases are not forced into a
category: where the closest category is only approximate, the note says so,
and some cases primarily defend a non-security property (determinism,
minimization) that OWASP does not categorize.

## 2. Case → ASI mapping

| G5 case | Invariant family | Primary ASI | Notes |
|---|---|---|---|
| g5-01 wrong-person-direct | Person isolation | **ASI03 Identity & Privilege Abuse** | Cross-person access request refused at prepare (`person_access_denied`). |
| g5-02 wrong-person-injection | Person isolation | **ASI03** (attack vector: ASI01) | Injected instruction tries to switch the bound Person; the provider receives only the bound Person's evidence. The *attack technique* is goal hijacking (ASI01); the *enforced boundary* is identity (ASI03). |
| g5-03 evidence-injection | Person isolation | **ASI03** | Cross-person evidence selection refused (`evidence_person_mismatch`). |
| g5-04 context-poisoning | Context integrity | **ASI06 Memory & Context Poisoning** | Disclosure derives only from the Envelope's selected evidence; foreign content cannot enter context. |
| g5-05 revoked-person-assignment | Revocation | **ASI03** | Revoked authorization stops execution after consent; zero provider calls. |
| g5-06 revoked-disclosure-consent | Consent revocation | **ASI03** (closest) | Revoked consent refuses execution at the live revalidate gate (`context_changed`). |
| g5-07 context-changed (TOCTOU) | Context TOCTOU | **ASI06** | Mutated evidence between consent and execute refuses execution; envelope identity change is detected. |
| g5-08 provider-swap | Provider reachability | **ASI02 Tool Misuse** | Provider identity bound by exact consent; a swapped provider refuses (`context_changed`), zero calls. |
| g5-09 model-swap | Provider reachability | **ASI02** | Model identity bound by descriptor hash; a swapped model refuses, zero calls. |
| g5-10 provider-unavailable | Availability | **ASI08 Cascading Failures** | Provider outage fails closed (`provider_failed`); no fallback provider, no silent substitution. |
| g5-11 mutation-tool | Tool boundary | **ASI02** | Write operation through the mediator blocked (`tool_not_allowed`); mutation attempt recorded. |
| g5-12 unknown-tool | Tool boundary | **ASI02** | Unknown tool name refused by the fail-closed mediator. |
| g5-13 citation-outside-envelope | Citation boundary | **ASI02** | Answer citing a source outside the Envelope is refused (`unknown_citation`); output integrity. |
| g5-14 fabricated-evidence-id | Provenance | **ASI02** (closest) | Fabricated evidence identifier refused (`provenance_missing`). Closest category is output/data integrity; this is **not** a dependency-supply-chain claim (ASI04 is out of G5 scope, §4). |
| g5-15 unsupported-medical-claim | Unsupported medical output | **ASI09 Human-Agent Trust Exploitation** | Unsupported prescriptive claim refused (`unsafe_prescriptive_claim`); prevents misleading human-facing output. |
| g5-16 receipt-tampering | Receipt integrity | **ASI07 Insecure Inter-Agent Communication** (closest) | Tampered Receipt fails integrity validation; the runtime refuses to return a corrupted stored Receipt. Closest category is integrity of artifacts exchanged across the agent boundary. |
| g5-17 envelope-tampering | Canonical mutation | **ASI07** (closest) | Byte-tampered Envelope rejected (`invalid_contract`); canonical identity integrity. |
| g5-18 replay-determinism | Replay/determinism | — (integrity property) | Identical runs produce identical Envelope/Receipt bytes; a second execute is replay-refused; changed semantic input changes identity. Primarily a reproducibility and integrity property; no direct ASI category. |
| g5-19 disclosure-minimization | Minimization | **ASI02** (closest) | Only selected evidence reaches the provider (20/58 eligible IDs; measured byte reduction). Closest category is minimal tool/data use; primarily a privacy-by-design property. |
| g5-20 fixture-misuse | Fixture isolation | **ASI09** | A committed synthetic fixture validates as a contract document but grants no live authorization; executing without consent refuses with zero provider calls. Defends the human/agent trust boundary against treating hashes or fixtures as authority. |

## 3. Mechanism summary

The mapping above is enforced by mechanisms that exist in G1–G4, not by
prompting:

- the Person-scoped Trust Envelope and closed purpose/action/tool registries
  (identity, scope, and evidence isolation);
- the G2 consent gate: exact external consent bound to actor, Person,
  Envelope, provider, and model; single-use, non-replayable (provider
  reachability);
- live reauthorization and revalidation before execution, including evidence
  hashes and provider descriptor (revocation, TOCTOU);
- the fail-closed tool mediator and output validation (tool boundary,
  citation boundary, unsupported medical output);
- canonical JSON, content identity, and Receipt validation (canonical
  mutation, Receipt integrity);
- scripted, deterministic providers with zero network access in the G5
  harness (no real model behavior participates in enforcement evidence).

## 4. Explicitly not claimed

G5's corpus does **not** exercise or claim coverage of:

- **ASI04 Agentic Supply Chain Vulnerabilities** — no dependency, MCP/A2A, or
  third-party component supply-chain surface is evaluated (MCP and A2A are
  explicit G5 exclusions);
- **ASI05 Unexpected Code Execution** — no plugin code execution, hook, or
  script surface is evaluated (the package is skill-only, no `mcp.json`, no
  hooks);
- **ASI10 Rogue Agents** — no self-directed-agent behavior is evaluated;
- model-level goal hijacking of a real model (ASI01 attack technique) is
  defended only at the boundary level: the enforced property is that a
  manipulated model still cannot reach unauthorized evidence, tools, or
  providers. Model behavior itself is out of scope and unbenchmarked.

Recording what is **not** claimed is part of the alignment: a taxonomy
mapping is only honest when its coverage limits are explicit.

## 5. Sources

- OWASP Gen AI Security Project, Agentic Security Initiative:
  `https://genai.owasp.org/initiatives/agentic-security-initiative/`
- OWASP Top 10 for Agentic Applications 2026 (ASI01–ASI10), published
  2025-12-09: `https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/`
- G5 design: [sentient-g5-ecosystem-validation](../architecture/sentient-g5-ecosystem-validation.md)
- G5 corpus: [evals/g5/corpus.json](../../evals/g5/corpus.json)
- G5 reviewer: [evals/g5_review.py](../../evals/g5_review.py)
- OWASP terms "Top 10", "ASI01"–"ASI10" are used for taxonomy alignment only
  (§ purpose above).
