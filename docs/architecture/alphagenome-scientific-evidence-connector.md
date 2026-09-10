# OpenCare — AlphaGenome Atlas Scientific Evidence Connector Foundation

**Status:** the AlphaGenome Atlas connector foundation is **implemented locally** on a parallel branch. It is additive and **not runtime-wired**. Runtime Product Core integration is **deferred until after D2.2**. The live AlphaGenome API is **unverified** — no smoke test was performed, intentionally.

**Verification date:** all terms and coordinate facts below were checked against primary official sources on **2026-09-09**.

## Primary official references

Accessed 2026-09-09:

- `github.com/google-deepmind/alphagenome` — README plus docs: `faqs.md`, `variant_scoring.md`, `api/atlas.md`, `src/alphagenome/atlas/atlas.py`, `src/alphagenome/data/genome.py`.
- DeepMind AlphaGenome pages, including the linked **"AlphaGenome Services Additional Terms of Service"** (`deepmind.google.com/science/alphagenome/terms`, last modified 2026-09-08) and the output-terms page.
- `github.com/google-deepmind/science-skills` — the `alphagenome_variant_impact_score` and `alphagenome_single_variant_analysis` skills.

The original blog announcement URL has rotated; the official repo-linked pages are used as authorities. Science Skills is treated as a **read-only external reference** — nothing was vendored, cloned, or copied, and its software license and third-party data terms remain distinct from OpenCare's.

## Intended OpenCare role

AlphaGenome is an **external scientific evidence source**, not a diagnosis engine. The intended flow:

```text
selected local normalized P3 variant
  -> explicit scientific query
  -> AlphaGenome Atlas
  -> predicted molecular/functional effect
  -> validated external evidence object
  -> (later) Genetics Research Studio integration
```

Explicitly **not**: raw genome → AlphaGenome; whole Product Core → AlphaGenome; AVI score → disease diagnosis.

## Terms snapshot (paraphrased)

Current official wording, checked 2026-09-09:

- Free of charge for non-commercial use; Google reserves the right to charge with prior notice.
- Eligible users: individuals and non-commercial organizations (universities, non-profits, research institutes, educational/government bodies), plus journalism. The services are unavailable to commercial entities even for non-commercial work.
- AlphaGenome Assets are for theoretical modelling and research only — not intended, validated, or approved for clinical use.
- Outputs must not be used for clinical purposes or relied on for medical or professional advice.
- Outputs should not train other ML models that predict genetic-variant effects (narrow carve-outs exist).
- Commercial full-model access is offered separately via Google Cloud.

**Key nuance:** the single **AVI Score** output is carved out as commercially usable, while the **AVI Score Feature Breakdown** (the 18-feature attribution) and other outputs remain non-commercial. Redistributed outputs (except the AVI Score) require a conspicuous notice that they are subject to the AlphaGenome Output Terms. API credentials are personal and must never be published or shared.

**OpenCare posture:** the connector descriptor encodes `research_only=true`, `clinical_use_allowed=false`, and a commercial-use class reflecting the AVI-Score-only carve-out. Downstream surfaces must never present AVI as clinical authority.

## Research-only boundary and AVI semantics

AVI is a **predicted molecular/functional impact** per the external model. It is never pathogenicity truth, disease probability, penetrance, diagnosis, prognosis, or a clinical risk score. A high AVI means a stronger predicted functional-impact signal; it does not establish disease causation. The typed `UsagePolicy` (`usage_class=research_only`, `clinical_decision_support=false`, `medical_advice=false`, `diagnosis=false`) makes any misrepresentation require consciously bypassing a typed distinction.

## AlphaGenome vs ClinVar

**AlphaGenome** provides a predicted functional/molecular effect. **ClinVar** provides submitted clinical classifications. No `Pathogenic` / `Likely Pathogenic` / `Benign` / `VUS` labels exist in the AlphaGenome result model. A future evidence-synthesis layer may show both side by side; not now.

## Data minimization / no raw genome

The external query carries **exactly one selected normalized SNV**: a chr-prefixed chromosome (`chr1`–`chr22`, `chrX`, `chrY`), a 1-based position, a single REF/ALT from A/C/G/T with `REF != ALT`, and the hg38 build enum. It is **structurally impossible** for the query to carry raw genotype bytes or text, a VCF payload, filesystem paths, full genotype files, other variants, Person name/DOB/demographics, medications, conditions, labs, family relationships, or arbitrary evidence arrays.

The raw genome remains local; the existing 32,000,000-byte genetics upload limit is unchanged. The API key (future runtime env `ALPHAGENOME_API_KEY`, following the official science-skills convention) is operator-supplied, never canonical data, never UI-visible, never exported, and never present in the descriptor or serialized models. The Colab-only `ALPHA_GENOME_API_KEY` spelling is irrelevant here.

## Coordinate contract

Official basis: the alphagenome repo docs/FAQ plus science-skills.

- Assembly: **hg38 = GRCh38.p13 only**.
- Annotation: **GENCODE v46**.
- Positions: **1-based**.
- Chromosomes: **chr-prefixed**; server acceptance of un-prefixed names is undocumented, so OpenCare always sends chr-prefixed outward.
- Alleles: forward reference strand; **no strand field** on variants.
- The server does **not** validate REF against the genome — OpenCare validates REF on its own side.
- Atlas precomputed coverage is documented as **SNV-only**; non-SNV input fails closed.
- Unknown or incompatible build fails closed with a stable typed reason.
- **No automatic liftover**; official hg19 guidance points to the external UCSC liftover — out of scope.
- chrM, alt, and decoy contigs are undocumented → excluded.

## Result model (bounded)

Official field names:

- echoed variant (`chr:pos:ref>alt`);
- `avi_phred` — float, documented range approximately [0, 70] (derived from the 1e-7 tail floor);
- `avi_raw`;
- `avi_quantile` — tail quantile (1 − CDF), in (0, 1];
- `top_percentile` — in (0, 100];
- `top_modality`;
- `top_feature_importance` — signed;
- optional attribution map capped at **exactly the 18 documented modality keys**, joined **by name, never positionally**: `MERGED_SPLICING`, `MAX_ABS_RNA_SEQ`, `MAX_ABS_ATAC`, `MAX_ABS_DNASE`, `MAX_ABS_CHIP_TF`, `MAX_ABS_CHIP_HISTONE`, `MAX_ABS_CAGE`, `MAX_ABS_PROCAP`, `MAX_ABS_POLYADENYLATION`, `MAX_ABS_CONTACT_MAPS`, `ALPHAMISSENSE`, `CACTUS_241_WAY`, `PROTEIN_TERMINATION`, `START_LOST`, `STOP_LOST`, `PHASTCONS_470_WAY`, `IS_INSERTION`, `IS_DELETION`.

The full experimental-track catalog (~9,440 tracks) is a separate endpoint and **never** enters the result. No tensors, no plots.

Provenance fields: assembly, annotation, source/API identity, requested scorers (`AVI_SCORE`, `AVI_SCORE_FEATURE_IMPORTANCE`), `retrieved_at`, response/schema version, and terms reference.

The normalizer **fails closed** on: missing `AVI_SCORE` or empty scores; NaN/inf; malformed identity; queried-vs-result mismatch; unexpected build; out-of-range quantile/percentile; more than 18 or unknown attribution keys. An absent quantile layer yields a typed `None` for phred/quantile — never a fabricated zero.

## Architecture

`app/scientific_evidence/` is an isolated typed connector layer with **no** FastAPI, **no** `app.product_core` repositories/services, **no** `app.family_access`, **no** SQLite, **no** SessionStore, and **no** UI.

The `ScientificEvidenceConnector` protocol (`descriptor` + `query_variant`) is designed to be reusable later for ClinVar/gnomAD/dbSNP — none implemented. The `AlphaGenomeTransport` protocol isolates network transport from domain parsing; the production transport is deferred, and only deterministic fakes exist in tests.

## Future trust flow (design only)

Nothing below is wired in this branch:

```text
selected normalized observation
  -> genetics-specific prepare
  -> disclosure
  -> explicit consent
  -> AlphaGenome query
  -> validated evidence
  -> receipt/audit
  -> Genetics Research Studio
```

The TrustEnvelope contract and genetics consent tables are unchanged.

- **Forbidden architecture:** P3 raw genome → generic AI agent → Science Skills → APIs.
- **Target architecture:** P3 local authority → selected variant projection → OpenCare `ScientificEvidenceConnector` → AlphaGenome → validated evidence → OpenCare Research Mode.

## Future disclosure contract

Wording reserved for a later UI:

> External scientific evidence lookup — Provider: Google DeepMind AlphaGenome Atlas. Data leaving OpenCare: one selected normalized genomic variant coordinate + REF/ALT. Data NOT leaving OpenCare: raw genome, full genotype file, other variants, health records, Person identity. Purpose: research-only molecular functional prediction.

## Future evidence integration and finding rule

A later stage may create a **versioned external genetics evidence entry** linked to one existing P3 normalized observation. The current `genetic_evidence_entries` schema is untouched and no migration occurs in this branch. AlphaGenome evidence is **not** an automatic reviewed finding, **not** a Condition, and **not** a diagnosis; candidate genetics findings still require the existing P3 human-review semantics.

## Science Skills reference analysis

Patterns observed, nothing copied:

- `atlas.create(api_key)` factory; `query_variant(variant, requested_scorers=[...])`.
- Variant string `chr:pos:ref>alt`, parsed via `genome.Variant.from_str`.
- Roughly 0.5–1.0 s per single-variant Atlas query.
- Bounded per-variant JSON: ~1–1.5 KB, ~3.9 KB with track info.
- stdout kept bounded via top-k / min-phred filtering.
- PHRED interpretation bands: ≥40 → top 0.01%; ≥30 → top 0.1%; ≥20 → top 1%; ≥15 → top 3.16%; ≥10 → top 10% of genome-wide SNVs.
- Mandatory research-only framing and clinical-safety warnings.
- Citation expectation: Avsec et al. 2026; Cheng et al. 2026 for the Atlas.
- Credentials read from `~/.env`, failure when unset, never echoed.

Its installation workflow is **not** OpenCare's.

## Current non-goals

Explicitly out of scope for this foundation: no live API call; no AlphaGenome SDK install; no dependency changes; no UI (no AVI cards, buttons, settings, or routes); no Settings entry; no export/backup/recovery changes; no Product Core schema/version change; no Family Access changes; no Clinical/Classical classification; no model benchmarking.

## Post-D2.2 integration plan

Implement **none** of these here:

- **A** — rebase/cherry-pick the foundation onto post-D2.2 main.
- **B** — operator AlphaGenome configuration (enabled/disabled, key-present yes/no, research-only classification).
- **C** — selected-observation authorization.
- **D** — genetics-specific external disclosure + consent.
- **E** — official AlphaGenome SDK/transport.
- **F** — versioned external genetics evidence persistence.
- **G** — Genetics Workspace AVI/evidence presentation.
- **H** — Research Mode evidence inclusion.
- **I** — backup/export/recovery alignment.
- **J** — one bounded live API smoke test.

---

## Stage B — Operator Configuration (implemented)

Operator-controlled runtime configuration added 2026-09-10 as a minimal,
safe seam — no network, no SDK, no persistence, and no Product Core or
Family Access dependency.

- **Disabled by default.** A fresh install or unconfigured deployment always
  has `alphagenome_enabled: false` and `alphagenome_api_key: None`. No
  startup error, no missing-config warning, no log; AlphaGenome is
  completely inert until the operator opts in.

- **Activation flag:** `OPENCARE_ALPHAGENOME_ENABLED`, following the
  established `OPENCARE_*` convention. Strict boolean parsing only
  (exactly `"true"` or `"false"`, case-insensitive after stripping);
  any other value raises `ConfigError` naming the env var. The flag
  carries no secret and may appear in config summaries.

- **API key:** `ALPHAGENOME_API_KEY`, following the official
  science-skills convention (no `OPENCARE_` prefix — the Foundation
  documented name is preserved as-is). Operator-supplied, environment
  only. Never surfaced in any UI, never persisted to any OpenCare
  database or export, never logged, never stored in product config
  State, never included in `ConfigError` messages or `repr()` output.
  The Settings dataclass holds it as `str | None` (presence-normalised);
  the operator config model wraps it in `pydantic.SecretStr` for safe
  typed handling. Blank and whitespace-only values are collapsed to
  `None` by `_read_optional_secret`, and direct `SecretStr("  ")`
  construction is rejected by field validator.

- **Derived runtime status** (`AlphaGenomeRuntimeStatus`):
  - `disabled` — when `enabled` is `false` (regardless of key presence).
  - `missing_api_key` — when `enabled` is `true` but no key is supplied.
  - `configured` — when `enabled` is `true` and a non-empty key is present.

- **Configured ≠ live verified.** Status `configured` means runtime
  configuration is sufficient for a FUTURE transport to be constructed.
  It does **not** imply the API key is valid, the Atlas endpoint is
  reachable, or any live smoke test succeeded. `live_verified` is
  always `false` in this stage; stage E (official SDK/transport) will
  handle actual verification.

- **Static truth derived from `ATLAS_CONNECTOR_DESCRIPTOR`** (single
  source, no hardcoded literals on `AlphaGenomeRuntimeStatus`):
  `connector_id`, `source_name`, `external`, `research_only`,
  `clinical_use_allowed`, and `commercial_use_class` are all copied
  from the descriptor. The nuance of `PARTIAL_AVI_SCORE_ONLY`
  commercial use is preserved.

- **No Product Core persistence, no Person authorization, no UI
  credential entry.** The configuration seam is purely process-level.
  Stage C (selected-observation authorization) and stage D (genetics
  disclosure + consent) remain separate concerns.

- **Real SDK/gRPC/AnnData transport is NOT implemented** in this
  stage. Wire-format compatibility with the live API is UNVERIFIED.
  The offline normalized evidence contract (AVI phred/raw/quantile
  bounds, 18-modality attribution cap) is unchanged.

## Stage C — Selected Observation Authorization (implemented)

Server-side read-only authorization seam added 2026-09-10. Resolves exactly
one persisted P3 genetics observation for an authorized Actor; no consent
(D), no transport (E), no persistence (F), no UI, no HTTP route.

- **Single method, two inputs.** ``ScientificObservationAuthorizer.authorize``
  accepts only ``person_id`` and ``observation_id`` — no dataset, source,
  or client-authoritative fields on the signature. The returned
  ``AuthorizedGeneticsObservation`` is frozen; ``reported_genotype`` and
  ``source_locator_json`` are absent.

- **Config gating before any resolution.** Operator configuration state
  ``disabled`` or ``missing_api_key`` raises ``AlphaGenomeSelectionUnavailableError``
  with a bounded reason code before any database query. Configured state
  proceeds; ``live_verified`` stays ``False`` everywhere. Configuration
  ≠ authority — the gate is independent of Person authorization.

- **Authority: genetics.research delegated.** The authorizer delegates
  Person authority to the existing ``ProductCoreAccess.require_genetics``
  boundary — ``require_person(person_id, "person.read")`` + active assignment
  + non-revoked genetics grant with ``genetics.research``. Hidden, foreign,
  denied, and revoked all propagate identical not-found semantics. The
  inherited ``person.read`` success audit fires through that path; no new
  audit writes are added at stage C. No parallel authorization
  implementation exists — the module imports ``ProductCoreAccess`` directly.

- **Full ownership chain.** The observation is resolved via a single JOIN
  through ``genetic_variant_observations → genetic_datasets → sources``,
  all gated on ``person_id``. A direct SELECT on observations alone would
  find the row; the JOIN is the structural requirement. Foreign, guessed,
  or broken-lineage observation IDs are indistinguishable from not-found.

- **No raw Source bytes.** The authorizer never invokes any source-read path
  (``SourceStore.read``, ``GeneticsService.export_package``, or similar);
  the raw genome remains local.

- **Deterministic local eligibility** from persisted values only. Reasons
  are stable, bounded codes collected in deterministic order:
  ``observation_no_call`` (coverage_state ≠ "present" or no_call truthy),
  ``unsupported_genome_build`` (anything other than ``GRCh38/hg38``),
  ``unsupported_chromosome`` (MT, chr-prefixed, or non-primary contigs),
  ``orientation_ambiguous`` / ``orientation_unresolved`` /
  ``orientation_not_applicable``, and **always** ``reference_allele_unresolved``.
  ``query_eligible`` is ``True`` only when reasons is empty — currently
  always ``False`` due to the permanent REF/ALT gap.

- **The REF/ALT gap.** Consumer-genotype diploid data contains no
  authoritative forward-strand reference or alternate alleles. The
  ``genetic_variant_observations`` table has no REF/ALT columns. Genotype
  is NEVER guessed into REF/ALT. ``SelectedVariantQuery`` is NOT
  constructible from an ``AuthorizedGeneticsObservation`` — stage C.1
  (Reference Allele Binding / Outbound SNV Projection) is REQUIRED
  before stage D.

- **No writes, no new audit table.** The authorizer is read-only. The
  inherited ``person.read`` audit from ``require_person`` (stage D wiring)
  is the only audit event; no new audit writes are added in stage C.
  All genetics payload tables (observations, datasets, sources, grants)
  are verified byte-for-byte identical before and after.

- **Not wired into app.main.** The authorizer is constructible but not
  runtime-wired; stage D will integrate it with ``ProductCoreAccess``.

## G5 freeze note

Unchanged: Agent Skills interoperability **verified** on OMP 17.3.5 + Hermes Agent 0.19.0; the root Agent Plugins gate is **external validation pending**; machine state `READY_FOR_SECOND_CLIENT_SMOKE`. There is no G6.
