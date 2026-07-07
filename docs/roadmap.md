# Roadmap

This roadmap is conservative. It moves OpenCare toward a privacy-first, agent-ready personal/family medical workspace without expanding the current validated repo into diagnosis, treatment recommendation, dosage guidance, medication selection, start/stop advice, clinical decision support, real-patient handling, or real-genetic-data handling.

The latest implemented runtime phase is V1H. V1I is a docs-only grant/reviewer packaging refresh on top of that runtime state.

## Completed Foundation

- Deterministic local Medication-to-Doctor Briefing demo pipeline.
- Synthetic/demo health vault and genotype-like inputs for the PGx reference workflow.
- Local demo evidence pack.
- Safe unsupported-drug no-claim behavior.
- Markdown report and JSON audit output.
- FastAPI API and server-rendered local web demo.
- Static-text and pipeline-backed evals.
- GitHub Actions CI and deterministic local trust metrics.
- V1A Health/Family Vault Core schemas, validation, and synthetic family dataset.
- V1B deterministic Health/Family Vault read model.
- V1C deterministic Health/Family Vault local artifacts.
- V1D committed synthetic reviewer artifacts and reviewer docs.
- V1E privacy/safety threat model, provenance semantics, and artifact guarantees.
- V1G read-only `/demo/health-vault` reviewer UI.
- V1H deterministic context/provenance trace graph on the reviewer route.

## Completed Runtime Phase: V1H Context / Provenance Trace Graph

Goal:

- add a deterministic provenance/traceability layer over the synthetic Health/Family Vault reviewer surface;
- connect recorded demo context to people, sources, safety boundary nodes, and reviewer artifact nodes;
- keep the route read-only and explicitly non-clinical;
- preserve the existing Medication-to-Doctor Briefing / PGx flow unchanged.

Status:

- `app/health_vault/trace_graph.py` is implemented.
- `/demo/health-vault` renders graph summary counts and per-record trace rows.
- The trace graph is deterministic traceability, not medical interpretation and not clinical validation.

Boundaries:

- no JSON API endpoints;
- no upload forms or user input;
- no LLM generation;
- no genetics, `genome_profile`, VCF/raw genotype, FASTQ, BAM, or WGS support;
- no diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice;
- no PGx behavior changes.

## Current Packaging Phase: V1I Final Grant / Reviewer Packaging Refresh

Goal:

- synchronize README, reviewer docs, grant docs, and final submission docs with the implemented V1A-V1H state;
- make the public repo read as vault first, genetics later, LLM third as interface;
- keep reviewer routes, artifacts, trust metrics, and boundaries easy to inspect;
- avoid adding any new runtime surface.

Status:

- V1I is docs-only.
- No runtime code, tests, evals, routes, or boundaries change in this phase.
- Latest implementation phase remains V1H.

Recommended next step after V1I:

- push or merge the final branch;
- run one public GitHub spot-check;
- stop feature work before submission unless a real blocker is found.

## Phase 2: Ingest And Provenance

Goals:

- add local conventions for ingesting medical documents, labs, medications, visits, and notes;
- attach source/provenance metadata to imported or manually entered records;
- keep unsupported, missing, or unverified states explicit;
- preserve local-first behavior.

Boundaries:

- no cloud upload by default;
- no claim extraction without provenance;
- no medical advice from imported documents.

## Phase 3: Usable Non-Genetic Workspace

Goals:

- deepen the product as a useful workspace without DNA;
- add stronger person/family profile views, timeline, document index, medication/lab views, and question workspace;
- improve clinician-review handoff outputs without automating clinical action.

Boundaries:

- no AI doctor positioning;
- no diagnosis or treatment recommendation;
- no automatic clinical action.

## Phase 4: Future Genetics Layer

Goals:

- bring genetics back only after the vault foundation remains safe and inspectable;
- add selected synthetic/demo genetics examples only where provenance, evidence, uncertainty, policy, and audit can stay visible;
- preserve fail-closed behavior for unsupported or weak claims.

Boundaries:

- no real genetic data support in the current repo;
- no FASTQ/BAM/WGS processing;
- no production genome interpretation;
- no inheritance-risk claims without later approved evidence and safety work.

## Explicit Non-Promises

This roadmap does not promise:

- diagnosis;
- treatment recommendation;
- dosage guidance;
- medication selection advice;
- start/stop medication instructions;
- real patient support;
- real genetic data support;
- FASTQ/BAM/WGS processing;
- clinical decision support;
- clinical validation;
- regulatory approval.
