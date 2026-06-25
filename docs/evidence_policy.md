# Evidence Policy

## Purpose

Evidence packs are local, versioned files that define what the deterministic rule engine can use.
They are demo-only in v0.1 and must not be treated as clinical coverage.

## Rule

No source, no claim.

## Required evidence fields

- drug;
- gene;
- variant or haplotype;
- source name;
- source URL;
- evidence level;
- summary;
- limitations;
- clinician-review requirement.
- demo-only disclosure, either on the rule or inherited from the pack.

## Source validation

Allowed source domains in v0.1:

- `cpicpgx.org`
- `clinpgx.org`
- `ncbi.nlm.nih.gov`
- `fda.gov`

Rules:

- source URLs must use `https`;
- source URLs must use one of the allowed domains or a subdomain;
- missing source URL means no claim;
- no network calls are made during validation.

## Clinical action

v0.1 must set `clinical_action_allowed=false`.

Reports may produce clinician-discussion items only.
`clinician_review_required` must remain `true`.

## Unsupported data

Unsupported variants, unknown variants, weak associations, VUS, and AlphaMissense-only annotations must not be actionable.
Unsupported drugs with no demo-pack rules must return a safe no-claim report.

## Coverage

Coverage in this project means demo evidence-pack coverage only.

It does not mean:

- clinical completeness;
- medication suitability;
- pharmacogenomic sufficiency;
- absence of relevant evidence outside the demo pack.

## Demo pack

The initial demo pack is educational/synthetic and must not be treated as clinical-grade medical guidance.
