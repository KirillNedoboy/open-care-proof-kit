# Vault Artifact Guarantees

This document describes what the V1C/V1D Health/Family Vault artifacts guarantee
and what they do not guarantee.

The artifacts are reviewer assets for the current synthetic demo vault. They are
not generated reports under `reports/`, not real user exports, and not clinical
output.

## Artifact Filenames

Committed Health/Family Vault artifacts live under `docs/assets/health_vault/`:

- `family-vault-read-model.json`
- `family-vault-summary.md`
- `family-vault-manifest.json`

## Artifact Lifecycle

The artifact chain is:

```txt
data/demo_patients/demo_family_vault.json
  -> app.health_vault.loader.load_demo_family_vault()
  -> app.health_vault.read_model.build_vault_read_model(...)
  -> app.health_vault.artifacts.build_vault_artifacts(...)
  -> docs/assets/health_vault/
```

The source dataset is synthetic/demo-only. The loader validates the dataset. The
read model reorganizes recorded context while preserving provenance links and
safety labels. The artifact builder writes the JSON read model, Markdown summary,
and manifest after checking provenance coverage and safety boundary metadata.

## Guarantees

The V1C/V1D artifacts guarantee that they are:

- generated from the synthetic/demo vault dataset;
- produced by a deterministic builder;
- built without LLM generation;
- built without genetics in this layer;
- built without medical advice;
- generated from recorded context, not clinical interpretation;
- source/provenance-linked for important surfaced records;
- accompanied by reported provenance coverage;
- accompanied by safety boundary notices;
- described by a manifest that records key safety flags:
  - `demo_only: true`
  - `synthetic: true`
  - `no_llm_generation: true`
  - `no_genetics: true`
  - `no_medical_advice: true`

The current manifest also records:

```txt
total_important_records: 14
records_with_source: 14
records_missing_source: 0
missing_source_item_ids: none
safety_boundary_notice_count: 6
builder_name: health_vault_artifact_builder
builder_version: 0.1.0
```

## Non-Guarantees

The artifacts do not guarantee:

- clinical correctness;
- medical advice;
- diagnosis;
- treatment selection;
- dosage guidance;
- medication selection;
- start/stop medication advice;
- real-patient support;
- real-genetic-data support;
- genetic interpretation;
- clinical decision support;
- source freshness;
- source authenticity;
- tamper-proof output;
- that future user data is safe by default without validation.

They are not a medical device, not an AI doctor, and not proof that OpenCare can
process real patient or real genetic records safely.

## Reviewer Verification Path

Reviewers can verify the artifact guarantees by inspecting:

1. `data/demo_patients/demo_family_vault.json` for the synthetic source dataset.
2. `app/health_vault/models.py` for demo/synthetic validation and unsafe-text checks.
3. `app/health_vault/read_model.py` for provenance-preserving summaries and safety notices.
4. `app/health_vault/artifacts.py` for deterministic artifact generation and manifest fields.
5. `docs/assets/health_vault/family-vault-manifest.json` for safety flags and provenance coverage.
6. `tests/test_health_vault.py`, `tests/test_health_vault_read_model.py`, and `tests/test_health_vault_artifacts.py` for regression coverage.

Focused verification:

```bash
pytest tests/test_health_vault.py tests/test_health_vault_read_model.py tests/test_health_vault_artifacts.py
```

Full repository verification:

```bash
pytest
ruff check app tests evals
mypy app evals
python -m evals.runner
python -m evals.trust_metrics
```

Trust metrics:

```bash
python -m evals.trust_metrics
```

The trust metrics report reads the committed manifest, reports synthetic/demo
artifact safety flags, checks the generated-report ignore expectation, and
includes eval totals from the existing eval runner. It is an automated
demo/reviewer trust check, not clinical validation.

## Difference From Generated Reports Under `reports/`

Health/Family Vault artifacts under `docs/assets/health_vault/` are committed
reviewer assets. They show the vault-first layer and are generated from the
synthetic family vault dataset.

Generated reports under `reports/` are runtime outputs from the existing
Medication-to-Doctor Briefing CLI path. They are ignored by Git and can be
regenerated locally with:

```bash
python -m app.cli demo-report --drug sertraline --out-dir reports
python -m app.cli demo-report --drug aspirin --out-dir reports
```

The vault artifacts and generated reports share the same product boundaries:
synthetic/demo data, local-first behavior, sources, limitations, and no medical
advice. They are different artifact families and should not be treated as the
same output path.
