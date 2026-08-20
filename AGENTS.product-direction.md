# OpenCare Product Direction

This file is an operational summary for repository agents. The authoritative
details live in [the Direction ADR](docs/adr/0001-opencare-product-direction.md),
[the current project status](docs/project-status.md), and
[the capability matrix](docs/capability-matrix.md).

## Canonical identity

OpenCare is an open-source, self-hosted Personal and Family Health Workspace.
It turns fragmented medical documents and user-entered information into a
user-confirmed, source-linked longitudinal health record.

## Primary workflow

The first primary workflow is **Prepare for next appointment**.

## Repository role

This repository is the main combined OpenCare foundation. It contains Product
Core direction, reusable Trust Foundation components, frozen Reference
Workflows, and reviewer/grant artifacts. Do not create a replacement
repository.

## Boundaries

- Product Core: people, family, sources, records, review, timeline, visits,
  questions, and briefs.
- Trust Foundation: provenance, policy, validation, audit, evaluations, and
  deterministic artifact generation.
- Reference Workflows: the frozen PGx Medication Briefing.
- Reviewer and grant artifacts: evidence and synthetic demonstrations only.

Product Core may depend on Trust Foundation. Trust Foundation must not depend on
reviewer UI. Reference and reviewer artifacts may consume both, but canonical
records must not depend on LLM output.

## Current status and permanent non-goals

Product Core migrations through v9, document upload/extraction, Family Access,
Genetics Workspace, separate genetics grants, family comparison, and bounded
Research Mode are implemented on public `main`. Do not reopen them as future
foundation work or create parallel implementations.

Permanent non-goals remain diagnosis, treatment/dosage/start-stop authority,
clinical validation, FASTQ/BAM/CRAM/gVCF/WGS, OCR, SaaS/cloud raw-genome
upload by default, autonomous canonical-record mutation, MCP, and deployment
changes without an explicit product decision.

## Prohibited product drift

Do not make chat the product identity, position PGx or genetics as the entry
point, turn the repository into a standalone trust product, claim that the
read-only JSON vault is already a complete workspace, or imply clinical
authority.

## Classifying new work

1. Product Core work must advance the source-to-confirmed-record-to-visit
   workflow.
2. Trust work must remain reusable and independent of reviewer presentation.
3. Reference workflow work must preserve PGx as a bounded demonstration.
4. Reviewer or grant work must describe verified behavior and must not define
   the product roadmap.
5. Any AI feature must be query-scoped, source-aware, explicitly bounded, and
   unable to silently mutate canonical records.

## Authoritative documents

- Product direction: `docs/adr/0001-opencare-product-direction.md`
- Current repository truth: `docs/project-status.md`
- Capability status: `docs/capability-matrix.md`
- Next implementation sequence: `docs/roadmap/product-core-roadmap.md`
- Intended boundaries: `docs/architecture/module-boundaries.md`
- Historical chronology: `CHECKPOINT.md` and `SESSION_NOTES.md`
