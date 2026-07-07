# Health/Family Vault demo

This page documents the V1G local reviewer UI plus the committed Health/Family Vault reviewer artifacts. The UI and artifacts are generated from the same synthetic dataset path rooted at `data/demo_patients/demo_family_vault.json`.

Review the V1D demo artifacts together with the V1E hardening docs:

- [Privacy and safety threat model](privacy_safety_threat_model.md)
- [Provenance semantics](provenance_semantics.md)
- [Vault artifact guarantees](vault_artifact_guarantees.md)

Those docs explain how to read the artifact chain, what provenance means, and
what the committed artifacts do and do not guarantee.

## What this demo shows

The demo shows the vault-first layer as a local, inspectable artifact chain:

```txt
synthetic family vault dataset
  -> loader and validator
  -> deterministic read model
  -> local read-only reviewer UI
  -> local JSON, Markdown, and manifest artifacts
```

The reviewer route and artifacts make the Health/Family Vault layer reviewable without adding upload flows, new JSON APIs, CLI commands, LLM generation, genetics support, or medical advice.

## Local reviewer route

Start the app and open:

```txt
http://127.0.0.1:8000/demo/health-vault
```

The page is read-only and renders:

- top safety banner;
- family overview;
- people and relationships;
- recorded medications, conditions/concerns, labs, and visits;
- timeline and question workspace;
- provenance coverage;
- artifact/trust flags;
- explicit "What This Page Does Not Do" boundaries.

## What files are included

- `docs/assets/health_vault/family-vault-read-model.json`
- `docs/assets/health_vault/family-vault-summary.md`
- `docs/assets/health_vault/family-vault-manifest.json`

These are intentional committed demo artifacts. They are not runtime output from a user workspace.

## How the artifact chain works

The source dataset is loaded through `load_demo_family_vault()`, which reads `data/demo_patients/demo_family_vault.json` and validates it as a `VaultDataset`.

The read model is built by `build_vault_read_model(...)`. It groups recorded context by person, preserves relationship and timeline data, keeps question threads as questions, carries provenance links, and adds safety boundary notices.

The local artifacts are built by `build_vault_artifacts(...)`. The builder writes the JSON read-model artifact, Markdown summary, and manifest. It fails closed if the data is not demo-only, is not synthetic, lacks provenance coverage, lacks safety notices, or contains blocked unsafe text.

The local reviewer UI route loads the same synthetic dataset through `load_demo_family_vault()`, builds the deterministic read model through `build_vault_read_model(...)`, reads committed manifest flags, and renders a read-only HTML page. It does not accept user input and does not read arbitrary file paths.

## Synthetic family vault dataset

The source dataset is synthetic/demo-only. It includes:

- a synthetic family record;
- three synthetic people;
- family relationships;
- recorded medications;
- recorded conditions and concerns;
- recorded labs;
- visits and timeline events;
- question threads;
- synthetic document sources and provenance links.

The dataset does not contain real patient data or real genetic data.

## Read model

The read model reorganizes validated vault data into reviewer-friendly groups:

- family overview;
- people;
- relationships;
- medications by person;
- conditions and concerns by person;
- labs by person;
- visits by person;
- timeline;
- question threads;
- provenance coverage;
- safety boundary notices.

It does not infer clinical meaning. Conditions remain recorded context, medications remain recorded medication context, labs remain recorded lab context, and questions remain unanswered workspace items.

## Local artifacts

The JSON artifact is the structured read model with artifact metadata and generated-from fields.

The Markdown artifact is a readable summary for reviewers. It labels the content as recorded demo context and repeats the safety boundary.

The manifest lists the created artifact filenames, artifact types, provenance coverage summary, safety boundary notice count, builder metadata, and scope flags:

- `no_llm_generation: true`
- `no_genetics: true`
- `no_medical_advice: true`

The guarantee and non-guarantee details are documented in
[Vault artifact guarantees](vault_artifact_guarantees.md). In short, these
artifacts show deterministic provenance-preserving demo context. They do not
prove clinical correctness and are not real user output.

## Provenance coverage

The current demo artifact records complete provenance coverage:

- total important records: 14;
- records with source: 14;
- records missing source: 0;
- missing source item IDs: none.

Every important summary item is source-linked to a synthetic document source.

## Safety boundaries

The artifacts state that they are synthetic/demo-only and deterministic summaries of recorded context.

They do not provide:

- diagnosis;
- treatment recommendation;
- dosage guidance;
- medication selection;
- start/stop medication advice;
- genetics support in this layer;
- real-patient support.

They also do not provide clinical validation.

## What this demo does not do

V1G adds one read-only local route and one template. It does not add JSON APIs, upload forms, LLM generation, genetics, `genome_profile`, VCF/raw genotype/FASTQ/BAM/WGS support, dependencies, or PGx behavior changes.

The committed artifacts are sample reviewer assets only. Future UI or agent surfaces can consume the same read-model shape, but that is not implemented in V1D.

## How to verify locally

Run the focused Health/Family Vault tests:

```bash
pytest tests/test_health_vault.py tests/test_health_vault_read_model.py tests/test_health_vault_artifacts.py
```

Then inspect:

```txt
http://127.0.0.1:8000/demo/health-vault
docs/privacy_safety_threat_model.md
docs/provenance_semantics.md
docs/vault_artifact_guarantees.md
docs/assets/health_vault/family-vault-manifest.json
```

The full validation command set remains:

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
```

There is no new V1D CLI command. The committed artifacts were generated from the existing builder, not from a new command surface.
There is no new V1G upload path or JSON API surface. The reviewer UI is a local HTML presentation layer over the existing deterministic vault read model.
