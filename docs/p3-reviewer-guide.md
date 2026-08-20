# P3 Genetics Research Studio Reviewer Guide

P3 is implemented on public `main` at
`0937d352cc74a3050609e826baa6bad82f6ac9ee`. This guide is a deterministic,
offline reviewer procedure, not clinical validation.

## Reviewer surfaces

Start the local app with Python 3.12 and inspect:

1. `/workspace` — actor-scoped Health Workspace.
2. `/family-access` — explicit Person and Family authorization.
3. `/genetics` — Genetics Workspace.
4. `/demo/health-vault` — synthetic read-only reviewer surface.

The first three are live Product Core surfaces and require Actor authentication.
The demo route is synthetic reviewer evidence and must not be confused with live
user-owned data.

## Run the reviewer

```bash
python -m evals.p3_review
```

The reviewer is deterministic and does not require a live LLM, network access,
Ollama, or external genetics service. Repository fixtures are synthetic only.

## Contracts under review

- **Selective indexing:** immutable local consumer-genotype Source bytes remain
  local; only evidence-pack or explicitly selected loci become normalized
  observations.
- **Coverage:** present, no-call, not-present, incompatible-build, and
  unresolved-orientation states remain distinct. Missing consumer-chip coverage
  is never treated as a reference genotype.
- **Genetics authorization:** ordinary `person.read`, `source.read`, and
  `document.read` do not imply genetics access. The separate grants are
  `genetics.read`, `genetics.write`, `genetics.research`, `genetics.compare`,
  and `genetics.export`.
- **Person isolation:** Alice, Bob, Child, and hidden Persons remain isolated;
  family relationship membership does not grant genetics access.
- **Strand ambiguity:** A/T and C/G ambiguous observations remain visible as
  unresolved but cannot create findings, PGx intersections, or supported claims.
- **PGx intersection:** only reviewed findings and exact confirmed normalized
  medication names produce an association. No dosage, medication choice, or
  start/stop action is generated.
- **Family comparison:** compatible indexed observations produce shared,
  differing, and IBS statistics. Output is compatibility evidence, not kinship,
  legal, or forensic proof.
- **Evidence Mode:** strict supplied-context synthesis; speculative/model-
  background claims are rejected.
- **Explore Mode:** hypotheses and mechanisms are allowed when epistemically
  labelled and accompanied by support, counterevidence, alternatives, missing
  information, and questions worth investigating.
- **Raw-genome provider exclusion:** no Research request can opt raw Source
  bytes, full genotype text, or unindexed loci into provider context. Raw
  fields, bytes, genotype-row text, and oversized context are rejected.
- **Output safety:** diagnosis-as-fact, causal certainty, treatment
  instructions, medication start/stop, and dosage changes are rejected unless
  clearly framed as an external quoted/literature claim.
- **Canonical mutation boundary:** Research Mode cannot create or alter
  canonical health records, reviewed findings, genotypes, or Visit Brief
  evidence.

## Required P3 counters

The deterministic reviewer reports these counters; every value must remain zero:

- `cross_person_genetics_exposures`
- `hidden_genetics_dataset_disclosures`
- `unauthorized_genetics_imports`
- `unauthorized_family_comparisons`
- `raw_genome_agent_disclosures`
- `unlabeled_speculative_claims_accepted`
- `invalid_genetics_citations_accepted`
- `llm_genetics_canonical_mutations`

## Companion validation commands

```bash
python -m evals.g5_review
python -m evals.p1_review
python -m evals.p2_review
python -m evals.d1_review
python -m evals.p3_review
python -m pip check
```

These checks prove deterministic repository behavior only. They do not prove
clinical correctness, clinical validation, or production readiness.
