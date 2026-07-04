# Health/Family Vault demo

This page documents the committed Health/Family Vault reviewer artifacts for V1D. The files are generated from the V1C artifact builder using only `data/demo_patients/demo_family_vault.json`.

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
  -> local JSON, Markdown, and manifest artifacts
```

The artifacts make the new Health/Family Vault layer reviewable without adding API routes, CLI commands, UI/templates, LLM generation, genetics support, or medical advice.

## What files are included

- `docs/assets/health_vault/family-vault-read-model.json`
- `docs/assets/health_vault/family-vault-summary.md`
- `docs/assets/health_vault/family-vault-manifest.json`

These are intentional committed demo artifacts. They are not runtime output from a user workspace.

## How the artifact chain works

The source dataset is loaded through `load_demo_family_vault()`, which reads `data/demo_patients/demo_family_vault.json` and validates it as a `VaultDataset`.

The read model is built by `build_vault_read_model(...)`. It groups recorded context by person, preserves relationship and timeline data, keeps question threads as questions, carries provenance links, and adds safety boundary notices.

The local artifacts are built by `build_vault_artifacts(...)`. The builder writes the JSON read-model artifact, Markdown summary, and manifest. It fails closed if the data is not demo-only, is not synthetic, lacks provenance coverage, lacks safety notices, or contains blocked unsafe text.

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

They also do not claim clinical decision support.

## What this demo does not do

This V1D packaging phase does not add API routes, CLI commands, UI/templates, LLM generation, genetics, `genome_profile`, VCF/raw genotype/FASTQ/BAM/WGS support, dependencies, or PGx behavior changes.

The committed artifacts are sample reviewer assets only. Future UI or agent surfaces can consume the same read-model shape, but that is not implemented in V1D.

## How to verify locally

Run the focused Health/Family Vault tests:

```bash
pytest tests/test_health_vault.py tests/test_health_vault_read_model.py tests/test_health_vault_artifacts.py
```

Then inspect:

```txt
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
