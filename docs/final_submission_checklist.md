# Final Submission Checklist (Supporting Submission Artifact)

> Submission packaging is not the canonical product roadmap or current status.
> See [ADR 0001](adr/0001-opencare-product-direction.md),
> [project status](project-status.md), and [capability matrix](capability-matrix.md).

Use this checklist before submitting OpenCare Proof Kit for grant or reviewer evaluation.

## Public Repository

- [ ] Repository is public: `https://github.com/KirillNedoboy/open-care-proof-kit`
- [ ] Public default branch is `main`.
- [ ] README links to current status, capability matrix, roadmap, security,
  reviewer, and P3 guide documents.
- [ ] Public `main` contains the completed implementation; historical P3-final
  baseline: `0937d352cc74a3050609e826baa6bad82f6ac9ee`.
- [ ] `v0.1.0` and `v0.2.0` remain the only published tags/releases.

## README First Screen

- [ ] README presents OpenCare as a self-hosted Personal and Family Health
  Workspace plus reusable trust infrastructure.
- [ ] README presents vault → provenance/review → workspace → documents →
  bounded AI → genetics.
- [ ] README distinguishes synthetic public repository fixtures from sensitive
  self-hosted runtime data.
- [ ] README describes D1, P3, `/workspace`, `/family-access`, `/genetics`,
  separate genetics grants, export, and backup/recovery.
- [ ] README does not claim diagnosis, treatment, dosage, clinical authority, or
  clinical validation.

## Reviewer Materials

- [ ] `docs/final_reviewer_pack.md` is current.
- [ ] `docs/reviewer_quickstart.md` is current.
- [ ] `docs/p3-reviewer-guide.md` exists.
- [ ] P1/P2/D1/G5 reviewer guides exist.
- [ ] Reviewer paths include `/workspace`, `/family-access`, `/genetics`, and
  `/demo/health-vault`.
- [ ] Synthetic artifacts are present under `docs/assets/health_vault/`.
- [ ] Safety, provenance, authorization, genetics, and raw-genome boundaries
  are visible in reviewer-facing docs.

## Validation Baseline

Final local evidence:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
.\.venv\Scripts\python.exe -m evals.trust_metrics
.\.venv\Scripts\python.exe -m evals.g5_review
.\.venv\Scripts\python.exe -m evals.p1_review
.\.venv\Scripts\python.exe -m evals.p2_review
.\.venv\Scripts\python.exe -m evals.d1_review
.\.venv\Scripts\python.exe -m evals.p3_review
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Record fresh results in [docs/project-status.md](project-status.md). These are
local verification results unless a CI run is explicitly linked.
## Versioning And Release Identity

- [ ] `pyproject.toml` and `app.__version__` match `0.3.0.dev0`.
- [ ] `0.3.0.dev0` is documented as unreleased development identity.
- [ ] No `v0.3.0` tag or release is claimed.

## Grant Docs

- [ ] Grant answers updated for implemented Health/Family Vault foundations
- [ ] Grant answers mention deterministic read model, reviewer artifacts, read-only reviewer UI, trace graph, CI, and trust metrics
- [ ] Public fixtures/issues/PRs/screenshots/logs contain no real sensitive data.
- [ ] Self-hosted runtime sensitivity, local storage, export, backup, and
  external-provider consent boundaries are documented.
- [ ] Generated `reports/` outputs remain ignored.
- [ ] `/demo/health-vault` remains synthetic/read-only.
- [ ] No wording implies clinical validation or medical approval.
- [ ] Reviewer route remains read-only
- [ ] Trust metrics command is present in reviewer/final-submission docs
- [ ] Safety banner, provenance coverage, and trace graph are part of the reviewer story
- [ ] No wording implies clinical validation or medical approval

## Public Spot-Check

- [ ] Open the GitHub repository page and verify README links render
- [ ] Confirm reviewer docs and artifact links are reachable
- [ ] Confirm generated `reports/` artifacts are not visible as tracked repository files
- [ ] Confirm no additional feature work was merged after the packaging refresh
