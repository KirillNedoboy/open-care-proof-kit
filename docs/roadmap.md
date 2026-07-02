# Roadmap

This roadmap is conservative. It moves OpenCare toward a privacy-first, agent-ready personal medical and genomics workspace without expanding the current validated system into diagnosis, treatment recommendation, dosage guidance, real patient clinical decision-making, or real genomic interpretation.

The current validated runtime remains Medication-to-Doctor Briefing until new phases are implemented. The existing demo uses synthetic/demo data, deterministic PGx matching, safety policy checks, Markdown report output, JSON audit output, and pipeline-backed evals.

## Completed Foundation

- Deterministic local demo pipeline.
- Synthetic/demo health vault and genotype-like inputs.
- Local demo evidence pack.
- PGx rule matcher for the Medication-to-Doctor Briefing reference workflow.
- Safe unsupported-drug no-claim behavior.
- Markdown report and JSON audit output.
- FastAPI API and server-rendered local web demo.
- Static-text and pipeline-backed evals.
- GitHub/grant readiness documentation.
- Genome Expansion Plan scope lock as a future genetics layer.
- V1A Health/Family Vault Core schemas, validation, and synthetic family demo dataset.

## Current Phase: V1A Health/Family Vault Core

Goal:

- add vault-first schemas for a person and family;
- create a synthetic family demo dataset;
- model medical history, medications, conditions/concerns, labs, visits, documents, questions, and provenance;
- keep the product useful without DNA;
- preserve local-first and synthetic/demo-only defaults.

Status:

- V1A schema, loader, validation, and synthetic demo dataset have been added.
- This phase remains schema/data-only and is not exposed through UI, API, CLI, or LLM summaries.

Boundaries:

- no real patient data;
- no real genetic data;
- no diagnosis, treatment planning, dosage advice, or medication selection advice;
- no new PGx behavior;
- no Genome Trust Console implementation in this phase.

Acceptance direction:

- a future agent can inspect a structured person/family vault without relying on an LLM as the source of truth;
- each record can carry provenance/source metadata;
- the synthetic family dataset is clearly marked synthetic/demo-only.

## Immediate Next Phase: V1B Vault Summary/Read-Model Builder

Goal:

- build deterministic read models over the V1A vault;
- expose safe summaries for people, family context, source coverage, timeline, medications, labs, and open questions;
- keep summaries source-backed and explicitly non-diagnostic;
- preserve the existing Medication-to-Doctor Briefing runtime until a later phase intentionally integrates new surfaces.

Boundaries:

- no diagnosis, treatment planning, dosage advice, medication selection advice, or start/stop medication advice;
- no genetics or Genome Trust Console implementation;
- no clinical decision support claims.

## Phase 2: Ingest And Provenance

Goals:

- add local conventions for ingesting medical documents, labs, medications, visits, and notes;
- attach source/provenance metadata to imported or manually entered records;
- make unsupported, missing, or unverified states explicit;
- keep raw sensitive data local by default.

Boundaries:

- no cloud upload by default;
- no claim extraction without provenance;
- no medical advice from imported documents.

## Phase 3: Usable Non-Genetic Workspace

Goals:

- make the product useful without DNA;
- add person/family profile views, timeline, document index, medication/lab views, and question workspace;
- add doctor-prep summaries only as review aids;
- keep LLM output as interface/explanation, not source of truth.

Boundaries:

- no AI doctor positioning;
- no diagnosis or treatment recommendations;
- no automatic clinical action.

## Phase 4: Genome Expansion / Genome Trust Console

Goals:

- implement the previously documented Genome Expansion as an optional future genetics layer after vault foundations exist;
- add selected synthetic/demo genetics cards only where evidence, uncertainty, policy status, and audit trace can be shown;
- preserve strict fail-closed behavior for unsupported, weak, missing, or dangerous claims.

Boundaries:

- no real genetic data support in the MVP;
- no FASTQ/BAM/WGS processing;
- no clinical genome interpretation;
- no inheritance risk inference;
- no personality/RPG genomics as the central product value.

## Phase 5: Family And Drug-Response Differentiation

Goals:

- deepen first-class family support with synthetic/demo examples;
- add family-aware context views without production inheritance claims;
- add drug-response lenses that wrap the existing PGx discipline without changing medication safety boundaries.

Boundaries:

- no production family genetics claims;
- no medication selection advice;
- no dosage or start/stop instructions.

## Phase 6: Grant/Demo/Repo Packaging

Goals:

- refresh reviewer docs, screenshots, demo scripts, status docs, and grant materials;
- document the vault-first product direction clearly;
- keep validation commands and boundaries visible for contributors and reviewers.

Boundaries:

- no fake Sentient integration;
- no unsupported ecosystem claims;
- no claim that future layers are already implemented.

## Explicit Non-Promises

This roadmap does not promise:

- real patient diagnosis;
- medication choice recommendations;
- dosage recommendations;
- start/stop medication instructions;
- WGS/FASTQ/BAM processing;
- clinical genome interpretation;
- inheritance risk inference;
- clinical validation;
- regulatory approval.
