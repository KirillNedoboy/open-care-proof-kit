# Reference Landscape

This document records product and architecture references for OpenCare. These projects are references only. They are not dependencies, endorsements, partnerships, or implementation sources.

Reference handling rules:

- Use these repos only as product or architecture references.
- Do not copy code, files, schemas, UI, or claims.
- Do not clone or vendor them into this repository.
- Do not imply endorsement, partnership, or dependency.
- Do not claim OpenCare already supports features from these projects.

## Product / UX References

- https://github.com/Rai220/my-health-public
- https://github.com/nickpdawson/OwnChart
- https://github.com/realactivity/tula

What this category teaches us:

- Personal health data needs a usable workspace, not just a report generator.
- Markdown/file-based organization can be a practical entry point for agent workflows.
- The first product surface should make medical history, documents, questions, and longitudinal context easier to maintain.
- A user-owned health workspace can be useful before any genetics feature exists.

## Genomics / Analysis / Workflows

- https://github.com/KarchinLab/open-cravat
- https://github.com/iobio/gene.iobio
- https://github.com/broadinstitute/seqr
- https://github.com/PGP-UK/GenomeChronicler
- https://github.com/matbanik/agentic-genomics

What this category teaches us:

- Genomics workflows need strict boundaries between raw data, annotation, interpretation, and reporting.
- Real genomic analysis has heavy data, evidence, and domain constraints that do not belong in the first vault MVP.
- A future genetics layer should start narrow, source-backed, and fail-closed.
- OpenCare should not claim WGS, clinical variant interpretation, or broad raw-to-insight support until those workflows are explicitly designed and validated.

## Ecosystem / Ownership / Precedent

- https://github.com/OpenHumans/open-humans
- https://github.com/openSNP/snpr

What this category teaches us:

- User-owned health and genome data has a long open-source precedent.
- Consent, data ownership, exportability, and transparent data handling are product requirements, not add-ons.
- OpenCare should keep privacy-first defaults and avoid any default raw health or genotype upload path.

## External Knowledge / MCP

- https://github.com/Cicatriiz/healthcare-mcp-public

What this category teaches us:

- External knowledge connectors can be useful for agent workflows, but they must not replace local provenance and policy checks.
- Any future MCP or external knowledge integration should be optional, explicit, and bounded by source/audit rules.
- OpenCare should not invent external integration claims or fake ecosystem support.

## Our Baseline

- https://github.com/KirillNedoboy/open-care-proof-kit

What this category teaches us:

- The current validated baseline is Medication-to-Doctor Briefing from synthetic/demo data.
- The baseline already proves local-first execution, deterministic PGx matching, safety policy checks, Markdown output, JSON audit, and pipeline-backed evals.
- The next product direction should preserve that discipline while broadening the product into a vault-first personal/family workspace.
