# Evidence Policy

## Purpose

Evidence packs are local, versioned files that define what the deterministic rule engine can use.

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

## Clinical action

v0.1 must set `clinical_action_allowed=false`.

Reports may produce clinician-discussion items only.

## Unsupported data

Unsupported variants, unknown variants, weak associations, VUS, and AlphaMissense-only annotations must not be actionable.

## Demo pack

The initial demo pack is educational/synthetic and must not be treated as clinical-grade medical guidance.
