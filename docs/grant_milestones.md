# Grant Milestones

These milestones are conservative and vault-first. They do not promise diagnosis, treatment recommendation, dosage guidance, medication selection, start/stop advice, real patient support, real genetic data support, or clinical deployment.

## Month 1: Public Reviewer Packaging And Hygiene

Goals:

- finish public reviewer-pack polish and GitHub spot-checks;
- document how reviewer artifacts, trust metrics, and validation baselines are refreshed;
- tighten release hygiene for docs-only packaging changes;
- keep generated reports ignored and reviewer-facing boundaries visible.

Acceptance signals:

- reviewer pack, README, grant docs, and final submission docs tell the same story;
- public README first screen matches the implemented V1H state;
- generated `reports/` outputs remain ignored;
- validation baseline and trust metrics commands are easy for reviewers to find.

## Month 2: Vault-First Ingest And Provenance Improvements

Goals:

- add local ingest/provenance conventions for documents, labs, medications, visits, and notes;
- improve unsupported and missing-provenance handling for future imported data;
- improve clinician-review handoff exports without automating clinical action.

Acceptance signals:

- new ingest paths remain local-first and provenance-preserving;
- unsupported states stay visible and fail closed;
- exports remain clearly labeled for review, not treatment action.

## Month 3: Future-Layer Research, Not Scope Jumping

Goals:

- research future genetics and interface layers without breaking the vault-first architecture;
- define privacy, provenance, and safety requirements before any real-data or adapter work;
- prepare a conservative public `v0.1` release after validation and reviewer feedback.

Acceptance signals:

- written requirements exist before implementation of any future genetics or interface layer;
- deterministic vault and provenance infrastructure remains upstream of any model-generated text;
- no new real-data or clinical claims are introduced by roadmap wording alone.

## Explicit Non-Promises

The grant roadmap does not promise:

- diagnosis;
- treatment recommendation;
- dosage guidance;
- medication selection advice;
- start/stop medication instructions;
- real patient support in the current repo;
- real genetic data support in the current repo;
- FASTQ/BAM/WGS pipeline;
- clinical decision support;
- clinical validation.

## Application Wording Guardrails

Use:

- "vault first"
- "privacy-first personal/family medical workspace"
- "synthetic/demo-only"
- "reviewer artifacts"
- "trust metrics"

Avoid:

- "AI doctor"
- "diagnosis"
- "treatment recommendation"
- "dosage guidance"
- "clinical decision support"
- "real patient upload"
