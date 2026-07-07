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
- V1B deterministic Health/Family Vault read-model builder with provenance coverage and safety notices.
- V1C deterministic Health/Family Vault local artifact builder for JSON, Markdown, and manifest files.
- V1D Health/Family Vault reviewer/demo packaging with committed synthetic artifacts and reviewer docs.
- V1E Health/Family Vault provenance and threat-model hardening.
- V1F CI/trust metrics hardening added.
- V1G minimal local Health/Family Vault reviewer UI added.
- V1H deterministic Health/Family Vault context/provenance trace graph added as the current reviewer-facing phase.

## Completed Vault Phase: V1A Health/Family Vault Core

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

## Completed Vault Phase: V1B Vault Summary/Read-Model Builder

Goal:

- build deterministic read models over the V1A vault;
- expose safe summaries for people, family context, source coverage, timeline, medications, labs, and open questions;
- keep summaries source-backed and explicitly non-diagnostic;
- preserve the existing Medication-to-Doctor Briefing runtime until a later phase intentionally integrates new surfaces.

Boundaries:

- no diagnosis, treatment planning, dosage advice, medication selection advice, or start/stop medication advice;
- no genetics or Genome Trust Console implementation;
- no clinical decision support claims.

Status:

- V1B read-model builder and focused tests have been added.
- The read model is not exposed through UI, API, CLI, or LLM summaries.

## Completed Vault Phase: V1C Health/Family Vault Local Artifact Builder

Goal:

- add the smallest reviewer-facing local artifact surface for the V1B read model;
- write deterministic JSON, Markdown, and manifest artifacts;
- preserve source links, provenance coverage, safety notices, and synthetic/demo-only labels;
- keep the phase local artifact-only.

Boundaries:

- no diagnosis, treatment recommendation, dosage advice, medication selection advice, or start/stop medication advice;
- no LLM-generated summaries;
- no genetics or Genome Trust Console implementation.
- no API routes, CLI commands, UI, or templates.

Status:

- V1C local vault artifact builder has been added.
- The artifact builder is not exposed through UI, API, CLI, or LLM summaries.

## Completed Vault Phase: V1D Health/Family Vault Reviewer/Demo Packaging

Goal:

- make the Health/Family Vault layer visible to reviewers through committed synthetic artifacts and docs;
- generate JSON, Markdown, and manifest demo artifacts from the V1C builder;
- preserve local artifact-only boundaries;
- keep Genome Expansion after vault foundations.

Boundaries:

- no diagnosis, treatment recommendation, dosage advice, medication selection advice, or start/stop medication advice;
- no genetics or Genome Trust Console implementation.
- no API routes, CLI commands, UI, templates, LLM generation, or dependencies.

Status:

- V1D reviewer/demo packaging has been added.
- The committed artifacts are generated from the synthetic family vault dataset through the V1C builder.
- README and reviewer quickstart now link the Health/Family Vault reviewer path.

## Completed Vault Phase: V1E Provenance And Threat-Model Hardening

Goal:

- document the Health/Family Vault privacy and safety threat model;
- define provenance semantics for `DocumentSource`, `EvidenceLink`, source-backed context, and user/demo-recorded context;
- document what the V1C/V1D vault artifacts guarantee and do not guarantee;
- make the committed artifacts easier to review without adding product surface area;
- keep Genome Expansion after vault foundations remain reviewable and safe.

Boundaries:

- no diagnosis, treatment recommendation, dosage advice, medication selection advice, or start/stop medication advice;
- no real patient data or real genetic data;
- no clinical decision support claims;
- no Genome Trust Console implementation.
- no API routes, CLI commands, UI/templates, LLM generation, genetics support, dependencies, or PGx behavior changes.

Status:

- V1E provenance and threat-model hardening has been added.
- The phase is docs/spec hardening only.
- New docs cover threat model, provenance semantics, and artifact guarantees.
- No runtime behavior is changed.

## Completed Vault Phase: V1F CI And Trust Metrics Hardening

Goal:

- add GitHub Actions CI for portable validation on push and pull request;
- add a deterministic local trust metrics report;
- make eval totals, artifact manifest safety flags, and generated-report ignore expectations easier to inspect;
- keep the phase automation/reporting-only.

Boundaries:

- no diagnosis, treatment recommendation, dosage advice, medication selection advice, or start/stop medication advice;
- no real patient data or real genetic data;
- no clinical decision support claims;
- no API routes, CLI commands, UI/templates, LLM generation, genetics support, dependencies, or PGx behavior changes.

Status:

- V1F CI/trust metrics hardening is added.
- GitHub Actions CI runs tests, lint, type checks, evals, and trust metrics.
- `python -m evals.trust_metrics` prints automated demo/reviewer trust checks.
- Trust metrics are not clinical validation.

## Completed Vault Phase: V1G Minimal Local Reviewer UI

Goal:

- add one local read-only reviewer page for the synthetic Health/Family Vault layer;
- render the deterministic read model, provenance coverage, and manifest/trust flags;
- keep the page reviewer-focused and explicit about safety boundaries;
- preserve the existing Medication-to-Doctor Briefing and PGx flow unchanged.

Boundaries:

- no JSON API endpoints;
- no upload forms or arbitrary file input;
- no LLM generation;
- no genetics, `genome_profile`, VCF/raw genotype, FASTQ, BAM, or WGS support;
- no diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice;
- no dependencies or PGx behavior changes.

Status:

- V1G minimal local reviewer UI is added and validated.
- `/demo/health-vault` renders the synthetic family vault through the validated deterministic read model.
- The page is local and read-only.
- Existing PGx routes remain the same.

## Current Vault Phase: V1H Context / Provenance Trace Graph

Goal:

- add a deterministic context/provenance trace graph over the synthetic Health/Family Vault reviewer surface;
- connect recorded demo context to people, sources, safety boundary nodes, and reviewer artifact nodes;
- keep the feature reviewer-focused, text/table based, and explicitly non-clinical;
- preserve the existing Medication-to-Doctor Briefing and PGx flow unchanged.

Boundaries:

- no JSON API endpoints;
- no upload forms or user input;
- no LLM generation;
- no genetics, `genome_profile`, VCF/raw genotype, FASTQ, BAM, or WGS support;
- no diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice;
- no dependencies or PGx behavior changes.

Status:

- V1H deterministic context/provenance trace graph is added/in progress.
- `/demo/health-vault` renders graph summary counts and per-record trace rows.
- The graph is deterministic traceability, not medical interpretation and not clinical validation.

Recommended next phase after V1H:

- V1I final grant packaging refresh; or
- V1I deeper family-aware reviewer navigation without changing safety boundaries.

Do not start V1I until V1H has been validated and reviewed.

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
