# Final Submission Checklist

Use this checklist before submitting OpenCare Proof Kit for grant or reviewer evaluation.

## Public Repository

- [ ] Repository is public: `https://github.com/KirillNedoboy/open-care-proof-kit`
- [ ] Public default branch is `main`
- [ ] Historical submission branch `phase-1-github-grant-readiness` remains pushed
- [ ] Latest implemented runtime state is V1H trace graph, not an earlier packaging-only snapshot

## README First Screen

- [ ] README says OpenCare is a privacy-first personal/family medical workspace foundation
- [ ] README says the repo is useful without DNA
- [ ] README says Health/Family Vault is the main implemented foundation
- [ ] README says genetics is a later layer and the LLM is an interface layer, not the source of truth
- [ ] README says current repo state is synthetic/demo-only
- [ ] README does not claim diagnosis, treatment recommendation, dosage guidance, medication selection, or clinical decision support
- [ ] README includes reviewer links for `/demo/health-vault`, reviewer docs, artifacts, threat model, provenance semantics, artifact guarantees, and reviewer quickstart

## Reviewer Materials

- [ ] Reviewer pack exists: [docs/final_reviewer_pack.md](final_reviewer_pack.md)
- [ ] Reviewer quickstart exists: [docs/reviewer_quickstart.md](reviewer_quickstart.md)
- [ ] Health/Family Vault demo guide exists: [docs/health_family_vault_demo.md](health_family_vault_demo.md)
- [ ] Threat model exists: [docs/privacy_safety_threat_model.md](privacy_safety_threat_model.md)
- [ ] Provenance semantics exists: [docs/provenance_semantics.md](provenance_semantics.md)
- [ ] Artifact guarantees exists: [docs/vault_artifact_guarantees.md](vault_artifact_guarantees.md)
- [ ] Reviewer artifact files are present under `docs/assets/health_vault/`
- [ ] Reviewer route is clearly named as `/demo/health-vault`
- [ ] Safety boundaries are visible in reviewer-facing docs

## Validation Baseline

Run from repo root:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
```

Expected baseline:

```txt
pytest: 87 passed
ruff: all checks passed
mypy: no issues in 36 source files
evals.runner: 12 passed cases, 0 failed cases
evals.trust_metrics: passed
```

Expected eval metrics:

```txt
total_cases: 12
static_text_cases: 7
pipeline_cases: 5
passed_cases: 12
failed_cases: 0
unsafe_advice_rate: 0.0
missing_source_rate: 0.0
uncertainty_missing_rate: 0.0
audit_missing_rate: 0.0
pipeline_failure_rate: 0.0
```

## Grant Docs

- [ ] Grant answers updated for implemented Health/Family Vault foundations
- [ ] Grant answers mention deterministic read model, reviewer artifacts, read-only reviewer UI, trace graph, CI, and trust metrics
- [ ] Grant docs stay honest about synthetic/demo-only scope
- [ ] Grant docs do not claim real-patient support, real-genetic-data support, clinical deployment, diagnosis, treatment recommendation, dosage guidance, or clinical decision support
- [ ] Grant summary character limits are still satisfied

## Safety And Scope

- [ ] Repo still reads as synthetic/demo-only
- [ ] No real-patient support claim was added
- [ ] No real-genetic-data support claim was added
- [ ] Generated `reports/` outputs remain ignored
- [ ] Reviewer route remains read-only
- [ ] Trust metrics command is present in reviewer/final-submission docs
- [ ] Safety banner, provenance coverage, and trace graph are part of the reviewer story
- [ ] No wording implies clinical validation or medical approval

## Public Spot-Check

- [ ] Open the GitHub repository page and verify README links render
- [ ] Confirm reviewer docs and artifact links are reachable
- [ ] Confirm generated `reports/` artifacts are not visible as tracked repository files
- [ ] Confirm no additional feature work was merged after the packaging refresh
