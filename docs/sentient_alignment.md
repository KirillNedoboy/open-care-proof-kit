# Sentient Alignment

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

Do not invent Sentient APIs, claim integration, or add ecosystem requirements without official sources.
