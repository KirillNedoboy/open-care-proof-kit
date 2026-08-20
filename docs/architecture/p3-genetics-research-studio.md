# OpenCare P3 — Genetics Research Studio

**Historical contract:** design binding for `codex/p3-genetics-research-studio`,
based on Product Core schema v8.

**Current implementation:** implemented and published on public `main` at
`0937d352cc74a3050609e826baa6bad82f6ac9ee`; Product Core schema v9 is current.

## Product thesis

P3 is an **Evidence-Grounded Genetics Research Studio**, not a genome diagnosis engine and not a genetic horoscope. It makes the existing OpenCare trust architecture visible end to end:

```text
sensitive local genotype source
  -> immutable Source
  -> bounded parsed observations
  -> selectively indexed loci
  -> deterministic evidence matching
  -> candidate finding
  -> explicit human review
  -> Genetics Workspace
  -> bounded Research Mode
```

The UI and APIs distinguish `observation`, `supported`, `plausible`, `speculative`, and `unsupported/conflicting`. Research Mode may explore beyond supplied evidence, but it never creates canonical health data or changes reviewed genetics records.

## Source formats and local-only raw boundary

P3 first-class input is a local **23andMe-style raw genotype TXT** file. The bounded parser accepts comment/header lines, tab-separated `rsid`, chromosome, position, and genotype columns, recognizes the common `# rsid chromosome position genotype` header, normalizes allele case, and accepts only two-base A/C/G/T calls or the explicit no-call forms (`--`, empty, and equivalent documented no-call tokens). Unsupported formats are rejected before storage. The existing demo VCF parser remains `demo_only`; P3 does not claim general VCF compliance. FASTQ, BAM, CRAM, gVCF, WGS, and liftover are out of scope.

Raw bytes are published once to the existing immutable local source store. They are never overwritten, logged, embedded, sent to any provider context, or committed to the repository. The consumer-genotype upload limit is a conservative bounded limit documented in code and tests (large enough for consumer TXT, deliberately not a sequencing-scale limit). Import requires an explicit genetics warning confirmation. Runtime import streams/chunks the file in a bounded byte buffer and hashes it as it reads; JSON/base64 requests are content-length bounded before parsing and decoded-size bounded after decoding. The source remains local; only explicitly selected normalized observations and reviewed evidence can enter Research Mode.

## Storage model and Product Core v9

Migrations v1-v8 are immutable. Migration v9 adds the following Person-bound, append-only or review-state tables:

- `genetic_datasets`: dataset id, Person, immutable source id, format, original filename, SHA-256, byte size, genome build (`GRCh37/hg19`, `GRCh38/hg38`, `unknown`), parser identity/version, import timestamp, parsed-locus count, indexed-locus count, and metadata JSON.
- `genetic_variant_observations`: observation id, dataset id, Person, rsID or normalized locus, chromosome, position, reported genotype, normalized genotype, no-call flag, orientation state, coverage state, source locator, and immutable provenance JSON.
- `genetic_evidence_entries`: versioned deterministic evidence-pack entries with locus/rsID, gene, build, genotype/allele condition, category, title, association, optional effect direction, evidence level, source name/citation/URL/version date, limitations, orientation metadata, and tags.
- `genetic_findings`: candidate/reviewed finding identity linking one observation and one evidence entry version, Person, category, status, evidence level, display fields, and provenance snapshot.
- `genetic_finding_reviews`: append-only review events with actor, prior/new status, reason, and timestamp.
- `genetics_research_sessions`: Person, mode, question, selected context identifiers, provider receipt metadata, context hash, validation result, lifecycle state, and timestamps.
- `genetics_research_claims`: session, claim text, epistemic status, supporting and contradicting internal IDs, Person record IDs, rationale, limitations, missing information, and user keep/dismiss state.

Every genetics row is Person-bound and has composite foreign-key paths where practical. Raw Source remains the evidence root; parsed/indexed rows are a minimization projection and are never a replacement for the original bytes. Dataset and observation rows are immutable after import. Finding review state changes only through an append-only review event and the current finding status.

The existing `sources.source_type` constraint is extended only in v9 to include `genetics`; v1-v8 source rows are copied unchanged during the normal SQLite parent-table rebuild pattern. Existing source deduplication remains `(person_id, source_type, content_hash)`.

## Variant normalization and selective indexing

Normalization is deterministic and provenance-preserving:

1. Trim/comment-filter and parse the bounded TXT row.
2. Normalize chromosome spelling and position to a stable textual/integer locus.
3. Uppercase and sort diploid alleles only when the source declares an unphased genotype; preserve the reported genotype separately.
4. Record `no_call` rather than treating it as reference.
5. Record `orientation_state` as `resolved`, `unresolved`, `ambiguous`, or `not_applicable`; A/T and C/G strand-ambiguous loci cannot be interpreted without explicit evidence orientation.
6. Record dataset genome build as known or `unknown`; no automatic liftover.

The parser may count every valid row for dataset metadata, but it persists only observations required by installed genetics evidence packs, explicitly selected loci, and deterministic synthetic reviewer fixtures. Dataset coverage reports target, present, no-call, not-present, build-incompatible, and unresolved counts. **Not present in consumer chip data is never a confirmed reference genotype.** Coordinate matching fails closed on incompatible known builds. rsID matching is allowed only when the evidence entry explicitly permits safe rsID matching and orientation is resolved.

## Evidence model

Evidence packs are versioned, deterministic, local JSON fixtures. Each entry has an immutable `evidence_id` plus pack/version identity and includes:

`rsid`/locus, gene, genome build, genotype/allele condition, category (`pgx`, `health_association`, `carrier`, `trait`, `neuro`, `metabolism`, `cardiovascular`, `nutrition`, `sleep`, `exercise`, `exploratory`), title, association, optional effect direction, user-facing evidence level (`Clinical`, `High`, `Moderate`, `Low`, `Exploratory`, `Conflicting`), source name, citation/reference identifier, URL, source version/date, limitations, orientation metadata, and tags.

Evidence level describes support quality, not disease probability. Pack entries without a source citation/reference are rejected. A deterministic match yields a **candidate genetics finding**, never a diagnosis or canonical condition. No claim is produced when the observation is absent, no-call, build-incompatible, or orientation-unresolved.

## Reviewed finding lifecycle and provenance

Finding states are `pending`, `reviewed`, `dismissed`, `unsupported`, and `conflicting`. A human actor explicitly reviews, dismisses, or marks a candidate unsupported/conflicting. A reviewed finding remains a genetics-domain record and never becomes a Condition automatically.

The immutable provenance chain is:

```text
finding
  -> evidence entry + pack/version
  -> normalized observation
  -> parser identity/version
  -> immutable genetics Source
  -> original SHA-256
```

Workspace cards expose this chain progressively, including source, build, orientation, limitations, and review event. No evidence-free finding can be stored.

## Family/genetics authorization

Existing v1, v2, and v3 Family Access assignments are frozen and never gain genetics authority. P3 uses a separate explicit genetics capability layer attached to a Person-bound grant/consent record, so ordinary `person.read`, `source.read`, `document.read`, or caregiver access does not imply genetics access. Capabilities are:

- `genetics.read`
- `genetics.write`
- `genetics.research`
- `genetics.compare`
- `genetics.export`

Import requires `genetics.write`; workspace reads and review require `genetics.read`; Research Studio requires `genetics.research`; comparison requires `genetics.compare` for each Person; export requires `genetics.export`. Every request checks the target Person and active consent server-side, fails closed with a non-disclosing not-found/forbidden result, and records an access audit outcome. Revocation immediately prevents subsequent reads, research, comparison, and export without rewriting historical consent events.

Genetics is Person-isolated. Alice's authorization does not expose Bob or Child, and access to Alice never grants access to a related Person. Hidden-Person checks occur before retrieval and do not reveal whether a hidden Person has a dataset, findings, or coverage.

## LLM Research Mode

Research Mode receives only a minimized, explicitly selected packet:

- reviewed genetics finding IDs and selected normalized observations;
- selected evidence entries and provenance metadata;
- explicitly selected canonical medication, condition, lab, timeline, visit-question, and document-backed facts;
- minimal Person metadata required for interpretation;
- an optional second Person only after both Person-level genetics authorization and `genetics.compare` authorization succeed.

It never receives the raw genotype file or unrestricted vault. The packet includes a context hash and source/evidence distinction. Self-hosted providers may receive the authorized packet. External providers require a separate genetics-specific disclosure consent; the preview shows only categories/counts, not sensitive values, and ordinary chat consent cannot substitute.

Two modes are mandatory:

- **Evidence Mode:** strict synthesis of supplied evidence; unsupported model background knowledge is excluded or explicitly labelled; weak evidence cannot become supported.
- **Explore Mode:** may generate hypotheses, mechanistic links, alternate explanations, missing-information requests, and model-background context, but every major claim is structured as:

```json
{
  "claim": "...",
  "epistemic_status": "observed|supported|plausible|speculative|unsupported/conflicting",
  "supporting_evidence_ids": [],
  "contradicting_evidence_ids": [],
  "person_record_ids": [],
  "reasoning_summary": "concise user-facing rationale",
  "limitations": [],
  "missing_information": []
}
```

Research output always contains sections equivalent to **What may be happening**, **Evidence supporting it**, **Evidence against it**, **Alternative explanations**, **Missing information**, **Confidence / epistemic status**, and **Questions worth investigating**. The prompt explicitly requests counterevidence before finalization. Chain-of-thought is never persisted; only the concise rationale is stored.

Research sessions and claims are optional user-kept research notes, not canonical health data. Research Mode cannot confirm Conditions, create Labs, change Medications, alter genotypes/findings, or mutate Visit Brief evidence. A user may explicitly edit and hand off a generated clinician question to a Visit; no automatic question creation occurs.

## Provider disclosure and receipt rules

Execution receipts extend existing G1/G2 metadata without changing the Trust Envelope contract. A genetics receipt records Person, mode, selected evidence IDs, selected health-record IDs, provider identity/class, disclosure-consent reference, context hash, output-validation result, and created timestamp. Receipts contain no raw genotype, raw marker values outside selected context, or full genetic source contents.

The output validator rejects invented internal genetics/evidence/health IDs, citations to unauthorized Persons, missing epistemic labels on speculative/plausible claims, unlabelled model-background claims, and autonomous dose/start/stop instructions. It accepts hypotheses only when explicitly labelled and preserves contradictions separately.

## Family comparison

Family Genetics Comparison is deterministic and only available when the actor is authorized for both Persons plus `genetics.compare`. It compares compatible selected indexed observations by rsID first, or by matching locus only when builds are compatible and orientation is resolved. It reports shared covered loci, differing genotypes, no-call/missing coverage, IBS0/IBS1/IBS2 counts, and coverage limitations. It may describe compatibility/similarity evidence but never proves legal or forensic kinship, infers hidden-Person state, or exposes unrelated Persons. A pair with no compatible observations fails closed rather than claiming similarity.

## PGx boundary

PGx is a major lens, not a prescribing engine. Deterministic matching renders:

```text
reviewed finding -> gene + genotype/allele observation -> evidence-pack phenotype/association
                  -> medication name intersection (only confirmed normalized Medication records)
                  -> evidence level + source + limitations
```

The intersection produces “relevant pharmacogenomic association exists”, never a medication choice, dosage, start/stop, or treatment instruction. Fuzzy model-only medication matching is forbidden. Research Mode may explain the association and produce clinician questions but cannot autonomously act.

## Workspace UI

A first-class Genetics area is added to the existing Health Workspace visual language with responsive, accessible tabs:

- **Overview:** source format/build/import date, parsed/indexed counts, coverage warnings, reviewed findings, evidence-level and category distributions.
- **Variants:** indexed observations only, filterable by rsID/gene/category/coverage/build, with linked evidence and provenance.
- **Pharmacogenomics:** gene → observation → evidence phenotype/association → confirmed medication intersection → evidence/source/limitations.
- **Health associations:** reviewed findings grouped by system/category without Condition creation.
- **Traits & systems:** exploratory neuro/pathway cards using association/possible relevance wording and persistent evidence badges; no deterministic personality claims.
- **Evidence:** pack/version/source details, review state, unresolved/conflicting warnings.
- **Family comparison:** explicit Person selectors, authorization gate, deterministic compatibility statistics and limitations.
- **Research Studio:** finding/record selection, Evidence/Explore mode choice, external disclosure preview/confirmation, structured hypothesis map, counterevidence, alternative explanations, missing information, save/dismiss research note, and explicit “Add question to Visit” handoff.

The import flow has a high-friction warning that genetics is uniquely identifying and can reveal information about biological relatives. Empty states explain that absent chip loci are untested, not reference genotype. Raw 600k-row tables are never rendered by default.

## Threat model

P3 counters accidental and malicious disclosure of immutable genetic data, cross-Person confusion, source tampering, parser ambiguity, stale/revoked family consent, build mismatch, strand ambiguity, invented citations, prompt injection through source text, model overreach into canonical records, and unsafe PGx advice. Controls are local immutable storage, SHA-256 verification, bounded streaming input, selective indexing, Person-bound composite queries, explicit capabilities and revocation, fail-closed matching, structured output validation, provider disclosure consent, no raw-genome context, append-only review/audit, and deterministic offline tests.

## Export and recovery

Ordinary portable health-vault export remains unchanged and never silently includes genetics. A separate **OpenCare Genetics Package v1** export requires `genetics.export` and a high-friction confirmation. It includes the selected immutable source bytes, source hash/metadata, dataset metadata, selected/indexed observations, reviewed findings, evidence references, and only explicitly selected research notes. It cannot include another Person.

Installation backup and recovery include the genetics tables, immutable raw source directory, parser/evidence metadata, finding reviews, genetics consents, and persisted research sessions. Recovery verifies original hashes, preserves IDs and timestamps, and fails rather than silently accepting corrupted or missing genetic source bytes.

## Future adapters

Define a narrow optional evidence-provider interface for future ClinVar, CPIC, PharmGKB (subject to licensing/API terms), and OpenCRAVAT adapters. P3 core remains deterministic/offline and has no mandatory network or OpenCRAVAT dependency.

## Synthetic demo and reviewer acceptance

Repository fixtures are synthetic only: `synthetic_person_a`, `synthetic_person_b`, and `synthetic_child`, with PGx, health-association, neuro, low-evidence trait, conflicting evidence, no-call, absent-locus, shared, and differing observations. No fixture represents a real individual.

`python -m evals.p3_review` is the deterministic offline reviewer. It covers Evidence Mode, Explore Mode, epistemic labels, supporting and contradictory evidence, speculative acceptance only when labelled, invented-citation rejection, hidden-Person rejection, raw-genome exclusion, PGx/current-medication intersection, family authorization/comparison, genetics export, and deterministic replay. Optional Ollama smoke is skipped when unavailable and is never a pass prerequisite.

P3 counters must remain zero:

- `cross_person_genetics_exposures`
- `hidden_genetics_dataset_disclosures`
- `unauthorized_genetics_imports`
- `unauthorized_family_comparisons`
- `raw_genome_agent_disclosures`
- `unlabeled_speculative_claims_accepted`
- `invalid_genetics_citations_accepted`
- `llm_genetics_canonical_mutations`

Quality reporting measures provenance coverage, citation validity, epistemic-label completeness, selected-context precision, raw-genome disclosures, family isolation, contradiction-section completeness, and deterministic replay without inventing targets before a baseline.

## Acceptance criteria

P3 is accepted only when the branch provides:

1. immutable local consumer-genotype import with build/coverage/orientation provenance;
2. selective normalized observations and versioned evidence packs;
3. explicit reviewed genetics findings and lifecycle;
4. frozen legacy access plus explicit genetics permissions/consent/revocation;
5. meaningful Genetics Workspace tabs and PGx/current-medication intersection;
6. deterministic family comparison with Person isolation;
7. Evidence Mode and Explore Mode with structured epistemic labels and Devil's Advocate counterevidence;
8. raw-genome exclusion, provider disclosure consent, citation validation, receipts, and no canonical mutation path;
9. explicit genetics export and recovery integrity;
10. synthetic fixtures and `python -m evals.p3_review` passing offline while G1/G2/G5/P1/P2/D1 remain passing;
11. docs/capability matrix/changelog aligned with achieved scope; no VCF/clinical-genetics overclaim.

Inspired design ideas are limited to the publicly readable Rai220/my-health-public organization of genetics, PGx, evidence badges, neuro/pathway groupings, and family comparison. No source code or assets are copied; no dependency is added; reuse rights are not assumed beyond the reference repository's stated metadata.
