# Privacy and Safety Threat Model

This document defines the V1E threat model for the Health/Family Vault layer.
It covers the current synthetic/demo implementation, not a production health
record system.

Current scope:

- synthetic/demo-only Health/Family Vault data;
- deterministic loader, read-model, and artifact builders;
- recorded context only: medications, conditions, labs, visits, timeline events, family relationships, sources, and questions;
- local reviewer artifacts under `docs/assets/health_vault/`;
- no Health/Family Vault medical interpretation.

The current Health/Family Vault is not a medical device, AI doctor, diagnosis
system, treatment recommender, medication selection engine, dosage tool, or
clinical decision support tool. It does not support real patient data, real
genetic data, raw genome processing, `genome_profile`, VCF/raw genotype,
FASTQ, BAM, or WGS workflows.

Current artifacts are deterministic reorganizations of recorded demo context.
They make provenance and safety boundaries inspectable; they do not make the
record clinically true.

## Threat Model

| Threat | Why it matters | Current mitigation | Detection / test coverage | Residual risk |
|---|---|---|---|---|
| hidden diagnosis wording | A recorded condition could be mistaken for an OpenCare-created diagnosis. | Condition summaries use `recorded_context_not_system_diagnosis`; unsafe text patterns reject system-diagnosis phrasing. Docs state that conditions are recorded context only. | `tests/test_health_vault.py`, `tests/test_health_vault_read_model.py`, and `tests/test_health_vault_artifacts.py` cover unsafe text and safety labels. | Future prose or UI surfaces could soften the boundary if they relabel recorded context as system output. |
| treatment recommendation leakage | A summary could drift from organizing records into recommending treatment. | Builder safety notices include `no_treatment_recommendation`; artifact Markdown states it is not treatment recommendation. | Artifact tests assert the boundary wording and manifest flags. Safety/eval commands still cover the existing Medication-to-Doctor Briefing workflow. | Future AI summaries must preserve the same boundary and pass wording scans. |
| dosage guidance leakage | Dosage wording can create direct medical action risk. | Unsafe text patterns reject common dose-change phrases; safety notices include `no_dosage_guidance`; artifact Markdown states it is not dosage guidance. | Health vault unsafe-text tests and artifact boundary tests. | Pattern-based detection is not exhaustive; future generators need policy checks and review. |
| start/stop medication advice | Start/stop language can be dangerous if presented as system advice. | Unsafe text patterns reject start/stop phrases; read model includes `no_start_stop_medication`; docs repeat the boundary. | Health vault unsafe-text tests and read-model safety-notice tests. | New wording can bypass known patterns unless future surfaces add stronger policy gates. |
| medication selection advice | Medication choice claims would change the product from organization into medical advice. | Medication summaries use `recorded_medication_context_not_recommendation`; unsafe text patterns reject medication-selection phrases. | Read-model tests assert medication safety labels; artifact tests assert no medication selection. | Future drug-response views must keep recorded medications separate from recommended medications. |
| missing source/provenance | Important medical context without source links is hard to audit and easy to overtrust. | Loader requires evidence links for important records; read model raises on missing provenance; artifact builder requires complete provenance coverage. | Tests cover missing provenance failure at loader, read-model, and artifact layers. | Future ingest may receive incomplete records and must fail closed or mark them explicitly unsupported. |
| unsupported medical claim | A claim outside the recorded source set can look authoritative. | Current vault layer does not generate medical claims; summaries carry source links and safety labels. | Tests assert source links on important summary items and unsafe-text rejection. | Future LLM or UI layers could introduce unsupported claims unless every surfaced claim remains source-bound. |
| weak evidence presented as certainty | `user_reported` or demo-inferred context could be overstated as verified fact. | `EvidenceLink.strength` records values such as `source_backed`, `user_reported`, and `inferred_from_demo_context`. Docs define these as provenance strength labels, not truth labels. | Model validation preserves evidence strength; read-model tests assert source links. | Current docs explain semantics, but future UI needs to display strength clearly. |
| user pressure / adversarial phrasing | A user may ask the system to ignore boundaries or provide clinical answers. | Current vault artifacts are deterministic and do not answer questions. Question threads are labeled `recorded_question_not_answer`. | Read-model tests assert questions remain questions, not answers; the G2 eval suite registers an injection/refusal fixture. | Future interactive layers need prompt-injection and refusal tests before any user-facing assistant behavior. |
| family/inheritance overclaim | Family relationships can be misread as genetic inheritance interpretation. | Relationships are stored as family graph context only. No genetics or inheritance interpretation exists in this layer. | Health/Family Vault tests cover relationship validation only, not genetic inference. | Future family views must avoid implying inherited risk unless a later approved genetics layer supplies evidence and safety checks. |
| real-patient data accidentally added to demo | Real personal data in the repo would violate the privacy-first premise. | Dataset, people, family, and sources require `synthetic: true`; dataset and sources require `demo_only: true`; docs state demo-only boundaries. | Tests reject non-demo and non-synthetic records. | Reviewers still need repository review discipline because validators cannot inspect human intent outside structured fields. |
| real genetic data accidentally added to demo | Real genetic data would be sensitive and is outside the current Health/Family Vault scope. | Current vault models do not include genetic data fields; manifest records `no_genetics: true`; docs state no real genetic data support. | Artifact tests assert `no_genetics: true`; no genetics fields exist in this layer. | Future files could still be committed outside the schema unless contribution review checks for them. |
| raw genome scope creep | Raw genome workflows would expand scope, privacy risk, and interpretation risk. | V1E keeps `genome_profile`, VCF/raw genotype, FASTQ, BAM, and WGS out of the vault layer. Roadmap keeps Genome Expansion after vault foundations. | No runtime surface exists; docs and roadmap mark this as out of scope. | Future contributors may try to add raw genome support early; roadmap and review gates must block it. |
| LLM-first trap | Letting an LLM become the source of truth would weaken provenance and safety discipline. | Health/Family Vault artifacts are built without LLM generation. The product rule is vault first, genetics second, LLM third as interface. | Manifest has `no_llm_generation: true`; artifact tests assert the flag. | Future assistant features need deterministic source context and policy checks before generation. |
| artifact tampering | Committed artifacts could diverge from the builder or source dataset. | Manifest records artifact filenames, builder name/version, demo/synthetic flags, provenance coverage, and safety flags. | Artifact tests verify generated structure and manifest fields. Reviewers can compare artifacts to `app.health_vault.artifacts`. | There is no cryptographic signing or checksum in V1E. Git history and tests are the current audit path. |
| source/reference mismatch | A record could point to a missing or wrong source ID. | Loader validates every evidence link against known `DocumentSource` IDs. | `test_evidence_must_reference_known_document_sources` covers unknown sources. | Validation proves source IDs exist, not that the synthetic source text is clinically correct. |
| privacy boundary leakage | A future surface could export raw sensitive data or imply cloud upload. | Current vault artifacts are committed synthetic files only. No API, CLI, UI, LLM, or cloud upload path is added for this layer. | No new runtime surface exists. Full validation confirms existing tests/evals still pass. | Future ingest/export features need explicit raw-data boundary metadata and tests. |
| stale or ambiguous source metadata | Old or vague source descriptions reduce reviewer trust. | `DocumentSource` records ID, title, source type, synthetic flag, demo-only flag, and description. Provenance docs define what those fields mean and do not mean. | Model validation enforces required source fields and demo/synthetic flags. | V1E does not add freshness dates, checksums, or versioned source documents beyond current metadata. |
| reviewer misunderstanding demo artifacts as clinical output | Reviewers may treat committed artifacts as a user export or medical report. | Demo guide and artifact guarantee docs state artifacts are reviewer assets generated from synthetic/demo data, not runtime user output. | Documentation review and wording scan. Manifest flags also state demo/synthetic and no medical advice. | Readers may skim; future reviewer UI should keep boundary labels visible near artifacts. |

## Required Boundary Language

Health/Family Vault docs and reviewer surfaces should keep these facts visible:

- the current implementation is synthetic/demo-only;
- the current Health/Family Vault does not interpret medically;
- artifacts are deterministic reorganizations of recorded demo context;
- provenance shows where recorded context came from, not whether the context is clinically true;
- OpenCare Proof Kit is not a medical device, AI doctor, diagnosis system, treatment recommender, medication selection tool, dosage tool, or clinical decision support tool.

## Review Checklist

Before changing the Health/Family Vault layer, check that the change:

- keeps source/provenance references on surfaced medical context;
- preserves `demo_only` and `synthetic` labels for demo assets;
- keeps family relationships separate from inheritance interpretation;
- keeps medications as recorded context, not recommendations;
- keeps questions as prompts for review, not system answers;
- avoids adding API, CLI, UI, LLM, genetics, or raw genome surfaces unless a later phase explicitly approves them;
- runs the focused vault tests and full validation sequence.
