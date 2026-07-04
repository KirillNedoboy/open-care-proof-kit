# Provenance Semantics

Provenance in OpenCare means a surfaced piece of context can be traced back to
a recorded source reference. It answers: "Where did this displayed context come
from in the local record?"

Provenance is not the same as clinical truth. It does not prove that a note,
lab, medication list, condition, family relationship, or question is medically
correct. It only makes the origin of the recorded context explicit so a reviewer
can inspect it.

## Current V1E Scope

The current Health/Family Vault provenance model applies to the synthetic demo
dataset and deterministic local artifacts. It does not support real patient
data, real genetic data, `genome_profile`, VCF/raw genotype data, FASTQ, BAM,
WGS, clinical genome interpretation, or production inheritance inference.

The vault layer does not diagnose, recommend treatment, recommend medication
selection, provide dosage guidance, or tell anyone to start or stop medication.
It records and reorganizes demo context.

## Core Terms

### DocumentSource

`DocumentSource` is the recorded source object for demo context. In V1E it has:

- `id`: the stable source identifier used by evidence links;
- `title`: reviewer-readable source title;
- `source_type`: source category, such as `visit_note`, `lab_report`, `medication_record`, `user_observation`, or `synthetic_document`;
- `synthetic`: must be `true` in the demo vault;
- `demo_only`: must be `true` in the demo vault;
- `description`: short source description.

`DocumentSource` tells reviewers what record a displayed item points to. It does
not certify that the source is clinically complete, current, or correct.

### EvidenceLink

`EvidenceLink` connects a surfaced record to a `DocumentSource`. It has:

- `source_id`: the referenced source;
- `strength`: the provenance strength label;
- `note`: a short explanation of why the source is attached.

Current strength labels include:

- `source_backed`: recorded from a source object in the demo dataset;
- `user_reported`: recorded as user/demo context;
- `inferred_from_demo_context`: derived from the synthetic demo context, not a clinical inference;
- `unknown`: reserved for unclear provenance states.

These labels describe provenance strength. They do not authorize medical action.

### Source-Backed

Source-backed means the item has at least one valid `EvidenceLink` that resolves
to a known `DocumentSource`. In the current vault layer, important records must
be source-backed before they can appear in the read model or artifacts.

Source-backed does not mean clinically verified. A source can be synthetic,
user-recorded, incomplete, stale, or wrong. The purpose is traceability.

### User/Demo-Recorded Context

User/demo-recorded context is information present in the local record because it
was entered, imported, or included in the synthetic dataset. In V1E this includes
recorded medications, conditions/concerns, labs, visits, timeline events, family
relationships, and questions.

OpenCare does not convert that context into diagnosis, treatment selection,
dosage instructions, medication changes, or genetic interpretation.

## Provenance Flow

The current Health/Family Vault flow is:

```txt
synthetic dataset
  -> loader validation
  -> deterministic read model
  -> local artifacts
  -> reviewer docs
```

1. `data/demo_patients/demo_family_vault.json` stores the synthetic family vault dataset.
2. `load_demo_family_vault()` loads it as a validated `VaultDataset`.
3. Validation requires demo/synthetic flags, known person IDs, known source IDs, and provenance links for important records.
4. `build_vault_read_model(...)` groups the validated context and preserves source links.
5. `build_vault_artifacts(...)` writes JSON, Markdown, and manifest artifacts only after checking provenance coverage and safety notices.
6. Reviewer docs explain the artifact chain and its boundaries.

## Missing Provenance Fails Closed

Missing provenance blocks the current vault chain:

- the loader rejects important records without evidence links;
- the read model raises if a summary item has no source links;
- the artifact builder requires zero missing-source records;
- the manifest reports provenance coverage so reviewers can inspect the result.

The current demo manifest reports:

```txt
total_important_records: 14
records_with_source: 14
records_missing_source: 0
missing_source_item_ids: none
```

If a future phase permits incomplete imported data, it must mark missing
provenance explicitly and keep unsupported claims out of summaries, reports, and
assistant output.

## What Provenance Does Not Guarantee

Provenance does not guarantee:

- clinical correctness;
- source completeness;
- source freshness;
- source authenticity;
- that a user-entered statement is true;
- that a lab result has been interpreted correctly;
- that a medication is appropriate;
- that a condition is an OpenCare diagnosis;
- that a family relationship implies genetic inheritance;
- that future user data is safe without validation.

Provenance is a traceability discipline, not a medical authority.

## Preservation Rules For Future Phases

Future phases should preserve provenance by default:

- imports should attach source metadata at ingest time;
- derived summaries should keep source references near surfaced medical context;
- unsupported or source-missing states should fail closed or be visibly labeled;
- local artifacts should continue to report provenance coverage;
- generated text must not invent facts, sources, or certainty;
- UI, API, and agent surfaces should expose the same source references instead of hiding them.

## Provenance Rules For Future Contributors

- Surfaced medical context must keep source references.
- Summaries must not invent medical facts.
- Family relationships must not imply genetic inheritance interpretation.
- Medications are recorded context, not recommendations.
- Conditions are recorded context, not OpenCare diagnoses.
- Labs are recorded context, not interpretation.
- Questions are user/reviewer prompts, not system answers.
- Genetics remains out of scope until explicitly implemented.
- Source-backed means traceable to a recorded source, not clinically proven.
- Missing provenance must fail closed or be displayed as unsupported, never silently upgraded.
