# Genome Expansion Plan

## Executive Summary

The Genome Expansion adds a future Genome Trust Console reference demo on top of the existing OpenCare Trust Stack. The planned MVP includes a bilingual EN/RU Genome Character Sheet, Drug Response Lens, synthetic Family Context, Raw-to-Insight parser contract, audit-backed card explanations, and a Fail-Closed Genetics Playground.

This makes the project stronger because it turns the existing trust infrastructure into a more visible product surface. Reviewers would be able to inspect how deterministic demo evidence, uncertainty, policy status, and audit trace produce safe cards instead of unsupported genetic claims.

The expansion remains a structured demo extension, not a freeform genetic interpretation engine. Real patient data, real genetic data, clinical genome interpretation, inheritance risk inference, production family genetics claims, FASTQ/BAM/WGS processing, and clinical action advice remain out of scope.

## Product Framing

OpenCare Trust Stack is the infrastructure layer: local-first adapters, evidence packs, deterministic rules, safety policy, audit output, and evals for sensitive AI workflows.

Genome Trust Console is the future reference product demo built on that infrastructure. It shows how a sensitive health/genomics interface can remain evidence-backed, auditable, and fail-closed.

Health and genomics remain the first stress-test domain because raw context is sensitive, mistakes are costly, evidence quality varies, and unsupported claims must be blocked rather than guessed.

The current MVP remains synthetic/demo-only. The existing Medication-to-Doctor Briefing workflow remains the validated runtime behavior until a future implementation phase explicitly adds new code.

## Proposed Domain Separation

Future `app/genome_profile` logic should be separate from existing PGx logic because genome profile cards are not the same problem as medication-specific pharmacogenomics matching.

The existing `app/pgx` domain answers drug-centered questions: a requested drug maps to PGx markers, local demo evidence rules, coverage, clinician-reviewable briefing text, and audit metadata. That flow should stay intact.

The future `app/genome_profile` domain would answer profile-card questions: focus, stress axis, sleep, metabolism, and drug-response lens states. These cards need explicit no-claim statuses for missing rules, missing markers, insufficient evidence, and blocked policy states. Overloading PGx rules with non-drug profile cards would blur boundaries and make safety review harder.

PGx remains backward-compatible:

- `build_demo_briefing(drug)` must keep its existing behavior.
- Existing report, Markdown, audit, and report-view routes must stay unchanged.
- Existing unsupported-drug safe no-claim behavior must stay unchanged.
- Future Genome Trust Console builders may wrap PGx output, but must not mutate PGx semantics.

## Future Data And Evidence Design

The future profile evidence pack should live at:

```txt
data/evidence_packs/genome_profile_demo_pack.json
```

The pack should be demo-only and should not contain real patient data, real genetic data, or production clinical claims.

Planned categories:

- `focus`
- `stress_axis`
- `sleep`
- `metabolism`
- `drug_response`

Every future rule must include:

- demo-only classification;
- evidence source;
- uncertainty;
- limitations;
- policy status;
- audit trace inputs;
- no clinical claim.

Rules without an accepted source, explicit limitations, sufficient evidence, and safe policy status must not emit a supported card. They must render as no-claim or blocked states.

## Planned Schema

Future structures:

- `ProfileCardRule`: demo-only evidence rule for one profile category and marker pattern.
- `ProfileCard`: rendered structured card shown in JSON, CLI output, or UI.
- `EvidenceRef`: source metadata used to support a card.
- `AuditTrace`: deterministic trace of which input, rule, evidence, and policy checks produced the card.
- `PolicyStatus`: safety policy result attached to the card.
- `CardStatus`: controlled card state used by downstream renderers.

Card statuses must be exactly:

- `supported_demo_finding`
- `no_demo_rule`
- `missing_marker`
- `insufficient_evidence`
- `blocked_by_policy`

The schema should make unsupported states first-class outputs. A missing rule or blocked policy is a valid safe result, not an exception to hide from reviewers.

## Planned Product Surfaces

### Genome Character Sheet

Purpose: Show a reviewer-facing RPG-style overview of synthetic genome profile cards for focus, stress axis, sleep, metabolism, and drug response.

Safety boundary: The sheet must not claim real trait prediction, diagnosis, risk scoring, or clinical interpretation. It may show only demo-supported findings or explicit no-claim states.

Demo data used: Synthetic health vault context, synthetic genotype-like rows, and future demo-only profile evidence rules.

Audit value: Each card shows its source, uncertainty, limitations, policy status, and audit trace so reviewers can inspect why the card exists or why it was blocked.

### Drug Response Lens

Purpose: Let a reviewer ask a medication question and see how drug, PGx markers, evidence, coverage, and clinician-review briefing connect.

Safety boundary: The lens must not recommend medication selection, dosage, or start/stop actions. It remains a clinician-review briefing path.

Demo data used: Existing synthetic genotype-like data, existing PGx evidence pack, existing PGx matcher, and future structured wrapper output.

Audit value: The lens connects card-level explanation to existing report and audit artifacts without changing the existing PGx flow.

### Synthetic Family Context

Purpose: Show how family context might be represented in the future through a synthetic-only comparison example.

Safety boundary: The MVP must not infer inheritance risk, real kinship, carrier status, family diagnosis, or production genetics claims.

Demo data used: Future synthetic family fixture only, with fabricated demo profiles and explicit synthetic-only labels.

Audit value: The audit records that family context is synthetic-only and that no inheritance risk inference was performed.

### Raw-to-Insight Parser Contract

Purpose: Document the boundary between raw genotype-like input and safe structured insight output.

Safety boundary: The parser contract must not imply current real VCF, raw consumer genotype, FASTQ, BAM, WGS, or clinical adapter support.

Demo data used: Existing synthetic genotype-like data and future contract metadata.

Audit value: The audit records parser type, demo data classification, raw export status, and whether downstream cards were supported, missing, insufficient, or blocked.

### Audit-Backed Card Explanations

Purpose: Make every visible card inspectable by showing evidence, uncertainty, policy status, and audit trace near the claim or no-claim state.

Safety boundary: The explanation layer must not invent sources, infer clinical meaning from raw variants, or override policy.

Demo data used: Future profile card builder output and existing audit conventions.

Audit value: Reviewers can trace a card back to the deterministic rule, source, limitations, and policy decision that produced it.

### Fail-Closed Genetics Playground

Purpose: Demonstrate safe blocked states for unsupported categories, weak evidence, missing markers, missing sources, and dangerous questions.

Safety boundary: Dangerous or unsupported prompts must produce blocked/no-claim outputs, not speculative explanations.

Demo data used: Synthetic examples intentionally covering matched, missing, unsupported, insufficient, and blocked paths.

Audit value: The playground proves that fail-closed behavior is visible and testable rather than only described in documentation.

## Planned Public Interfaces

Future higher-level demo experience builder output:

```txt
character_sheet
drug_response_lens
family_context
raw_to_insight
audit
```

Future public routes:

```txt
/demo/genome
/demo/genome.json
/demo/drug-lens?drug=sertraline
```

Existing report and audit routes must stay unchanged.

Future CLI:

```bash
python -m app.cli demo-genome --out-dir reports
```

Future JSON card shape:

- `id`
- `category`
- `title_en`
- `title_ru`
- `status`
- `summary`
- `evidence`
- `uncertainty`
- `limitations`
- `policy`
- `audit_trace`

Future audit additions:

- `profile_pack_id`
- `profile_pack_version`
- `card_ids`
- `blocked_card_ids`
- `parser_contract`
- `family_context_demo_only`

## Safety Invariant

Any card without a source, matched rule, sufficient evidence, or safe policy status must render as no-claim/blocked.

This invariant applies to every planned surface. A card may be visually useful while still saying no supported claim exists.

## Test And Eval Plan

Future tests should include:

- profile pack schema validation tests;
- builder tests for matched card, missing marker, unsupported category, missing source, and blocked policy;
- API tests for future `/demo/genome`, `/demo/genome.json`, and `/demo/drug-lens`;
- CLI tests for future `demo-genome`.

Future eval cases should cover:

- no diagnosis;
- no dosage;
- no start/stop medication advice;
- no source-less claim;
- weak/unsupported trait blocked;
- family context synthetic-only;
- audit trace present on every card.

The eval expansion should verify both text safety and nested audit fields. It should treat blocked/no-claim states as expected safe outputs.

## Implementation Phases

### Phase G1: genome_profile schemas + demo evidence pack

Objective: Add the future schema boundary and demo-only evidence pack for genome profile cards.

Likely files changed: `app/genome_profile/*`, `data/evidence_packs/genome_profile_demo_pack.json`, schema tests, and documentation.

Tests/evals: profile pack schema validation tests and source/limitations/demo-only rejection tests.

Acceptance criteria: demo profile rules validate only when they include source, uncertainty, limitations, policy status, audit trace inputs, and no clinical claim.

Risks: schema could become too broad or imply real clinical interpretation if not kept demo-only.

### Phase G2: profile builder + tests

Objective: Build deterministic profile cards from synthetic genotype-like data and demo profile rules.

Likely files changed: `app/genome_profile/builder.py`, schema files, tests, and possibly shared audit helpers.

Tests/evals: matched card, missing marker, unsupported category, missing source, insufficient evidence, and blocked policy tests.

Acceptance criteria: every builder output uses one of the exact allowed card statuses and includes audit trace fields.

Risks: builder wording could accidentally sound like real trait prediction instead of demo evidence display.

### Phase G3: genome JSON API + CLI

Objective: Add future structured JSON and local artifact generation surfaces for the Genome Trust Console.

Likely files changed: `app/main.py`, `app/cli.py`, future demo experience builder, and API/CLI tests.

Tests/evals: API tests for `/demo/genome.json`, CLI tests for `demo-genome`, and no-runtime-regression tests for existing PGx routes.

Acceptance criteria: existing report/audit routes remain unchanged and `build_demo_briefing(drug)` stays backward-compatible.

Risks: adding routes or CLI commands could accidentally couple new behavior to existing PGx report generation.

### Phase G4: bilingual dashboard UI

Objective: Add a reviewer-facing bilingual EN/RU dashboard for character sheet cards and fail-closed states.

Likely files changed: `app/templates/*`, `app/static/styles.css`, `app/main.py`, and UI/API tests.

Tests/evals: HTML route tests for `/demo/genome`, content tests for policy/no-claim labels, and accessibility-oriented checks where practical.

Acceptance criteria: every visible card shows status, evidence or no-claim reason, uncertainty, limitations, policy status, and audit trace.

Risks: RPG-style presentation could overstate certainty if visual scores are not clearly tied to demo-only evidence.

### Phase G5: Drug Response Lens wrapper

Objective: Add a structured wrapper around existing PGx flow for medication questions.

Likely files changed: future genome experience builder, PGx wrapper module, API/UI templates, and tests.

Tests/evals: sertraline matched demo-rule tests, aspirin unsupported safe no-claim tests, and no medication-selection wording evals.

Acceptance criteria: Drug Response Lens points to PGx markers, evidence, coverage, briefing link, and audit without changing PGx behavior.

Risks: lens wording could drift into medication choice or dosage advice.

### Phase G6: Family Context + Raw-to-Insight contract

Objective: Add synthetic family context and parser contract metadata.

Likely files changed: synthetic demo fixtures, future family context builder, parser contract docs, and tests.

Tests/evals: synthetic-only family context tests, no inheritance risk inference evals, and parser contract audit tests.

Acceptance criteria: family context is explicitly synthetic-only and Raw-to-Insight does not imply real raw genotype or WGS support.

Risks: users may read family comparison as production inheritance analysis unless labels and blocked states are explicit.

### Phase G7: eval expansion + docs

Objective: Expand safety/evidence evals and synchronize docs with implemented Genome Trust Console behavior.

Likely files changed: `evals/cases/*`, `evals/runner.py` if needed, tests, README, roadmap, safety docs, and product docs.

Tests/evals: full relevant validation set plus new genome profile evals.

Acceptance criteria: eval metrics cover no diagnosis, no dosage, no start/stop advice, no source-less claim, weak trait blocked, family synthetic-only, and audit trace present.

Risks: evals could be too narrow if they only inspect happy-path supported cards.

### Phase G8: screenshots/demo packaging refresh

Objective: Refresh reviewer assets after the Genome Trust Console is implemented and validated.

Likely files changed: screenshot assets, screenshot docs, demo video script, grant docs, and project status.

Tests/evals: no full tests required for screenshot-only changes unless docs or UI code changes; otherwise run the relevant validation set.

Acceptance criteria: screenshots show synthetic/demo-only labels, blocked/no-claim states, audit-backed cards, and unchanged safety boundaries.

Risks: demo packaging could imply current real-data support if captions are not conservative.

## Grant Rationale

The Genome Expansion makes a $10k request stronger because it creates a visible product surface for the infrastructure. It shows reviewers more than report summarization: a local trust console where sensitive claims are structured, evidence-backed, audit-backed, and fail-closed.

The expansion is not a generic chatbot. It keeps deterministic rules before any explanation layer, uses synthetic/demo data, records audit traces, and blocks unsupported claims.

The planned Genome Trust Console creates a future path toward a personal health/genome copilot while avoiding current claims of real-data support. It demonstrates how such a copilot could be made inspectable and conservative before any real patient or real genetic data is introduced.

## Non-Goals

This expansion does not include:

- real patient data;
- real genetic data;
- FASTQ/BAM/WGS processing;
- clinical genome interpretation;
- AlphaMissense clinical interpretation;
- diagnosis;
- dosage recommendation;
- start/stop medication advice;
- medication selection advice;
- inheritance risk inference;
- production family genetics claims;
- cloud raw genotype upload;
- fake Sentient integration;
- unsupported clinical claims.
