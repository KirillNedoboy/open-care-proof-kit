# Sentient Alignment (Supporting Grant Context)

> Supporting grant/context document, not the product roadmap or current
> implementation status. See [ADR 0001](adr/0001-opencare-product-direction.md)
> and [project status](project-status.md).

## Positioning

Submit OpenCare Proof Kit as open-source infrastructure for private, inspectable, fail-closed personal agent workflows.

The health workflow is the reference stress test. It shows the pattern in a domain where privacy, evidence, safety boundaries, and auditability matter from the first run.

## Why It Fits

| Criterion | Project fit |
|---|---|
| Open-source infrastructure | Code, schemas, evidence-pack format, safety policies, reports, audits, and evals are inspectable. |
| Private by default | The reference workflow runs locally on synthetic/demo data with no default raw health or genetic upload. |
| User-controlled | Inputs, evidence packs, generated reports, and JSON audits stay visible to the user/reviewer. |
| Trustworthy agent substrate | Deterministic tools run before the report-writing layer; unsupported paths fail closed. |
| Public good | The trust/evidence/policy/audit pattern can be forked and adapted by other sensitive-agent builders. |
| Conservative claims | The repo explicitly avoids diagnosis, dosage guidance, clinical deployment, real-patient support, and fake ecosystem integrations. |

## Why Health Is The Proving Ground

Health is not used here because the project wants to become a broad healthcare platform. It is used because health exposes the trust problem quickly:

- the data is highly sensitive;
- unsupported claims can be harmful;
- sources and limitations must be visible;
- uncertainty cannot be hidden;
- audit trails matter for review.

Medication-to-Doctor Briefing is narrow enough to validate honestly and demanding enough to test the trust layer. The demo uses synthetic/demo data only and keeps the output clinician-reviewable rather than prescriptive.

## Infrastructure, Not Just An App Demo

The reusable layer is:

```txt
input context -> evidence -> policy -> report/output -> audit -> evals
```

The current app surface demonstrates that the layer runs end to end. The grant case is the layer itself: source-grounded evidence, deterministic safety gates, fail-closed behavior, JSON audit metadata, and evals that reviewers can execute.

## Grant Angle

Primary angle:

> Reusable trust infrastructure for private personal agents, demonstrated in health because health is one of the hardest sensitive domains to handle safely.

Reference workflow:

> Medication-to-Doctor Briefing from synthetic/demo health vault and genotype-like data.

## Roadmap Alignment

Later roadmap can include:

- stronger evidence-pack tooling;
- broader synthetic eval coverage;
- clearer audit schema documentation;
- local review UX improvements;
- confidential compute or remote private inference research only after current official docs and privacy/security review;
- Sentient ecosystem compatibility only if official docs and APIs support it.

## Active Sentient Roadmap

The active Sentient-targeted sequence is separate from historical session
labels and from the genetics product roadmap:

1. Sentient G1 — OpenCare Trust Envelope;
2. Sentient G2 — Consent-Gated Agent Runtime;
3. Sentient G2.5 — optional Sentient integration spike; implemented as an
   optional synthetic-only compatibility spike
   ([spike contract](integrations/sentient-agent-framework-spike.md));
4. Sentient G3 — Model Portability;
5. Sentient G4 — Portable Trust Package;
6. Sentient G5 — Evaluation and Ecosystem Validation.

G1 defines and implements the boundary between authorized sensitive OpenCare
state and an agent-capable execution context. It does not wrap arbitrary
internal processing and does not add provider execution. See the
[binding G1 contract](architecture/sentient-g1-trust-envelope.md).

The G2 implementation work also registers ten named trust-evaluation fixtures
for the binding runtime acceptance categories. They document intended
fail-closed checks; they are not evidence of external provider or Sentient
ecosystem integration.

Historical `G1` genome-profile references in session chronology remain
historical; genetics is outside the Sentient critical path.

### Sentient G2.5 status (optional spike)

#### Implemented

- Optional Sentient Agent Framework compatibility spike
  (`sentient-agent-framework==0.3.0` as the `[sentient]` extra; never a core
  dependency).
- Synthetic/demo OpenCare agent (`OpenCareSentientDemoAgent`) over the fixed
  demo context (actor-alice / person-alice).
- G2-backed deterministic execution: the adapter delegates to the existing G2
  consent-gated runtime and a deterministic local provider.
- Sentient event rendering: `OPENCARE_STATUS`, `SOURCES`, `FINAL_RESPONSE`,
  and `OPENCARE_RECEIPT`, with fail-closed refusal paths.
- Validated answer and Receipt event: only G2-validated output is surfaced,
  together with the redacted Execution Receipt.

#### Not implemented

- Production Sentient Chat identity binding.
- Live personal-vault access through Sentient.
- Sentient as an OpenCare authorization source.
- Sentient SDK as a core dependency.
- External LLM integration.
- G3 model portability.

This is a compatibility spike, not a production Sentient integration.

The preserved roadmap note:

```txt
G4 Portable Trust Package
→ target Agent Plugins v1 packaging
→ skill first
→ optional read-only MCP adapter after safe runtime boundary
```

Agent Plugins packaging is not part of G2.5; no `plugin.json`, no `mcp.json`.

Do not invent Sentient APIs, claim integration, or add ecosystem requirements without official sources.
