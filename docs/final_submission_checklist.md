# Final Submission Checklist

Use this checklist before submitting OpenCare Proof Kit for grant or reviewer evaluation.

## Public Repository

- Repository: https://github.com/KirillNedoboy/open-care-proof-kit
- Submission branch: `phase-1-github-grant-readiness`
- Current submission state includes the grant readiness docs, grant submission answers, visual demo screenshots, and demo video script.

## Reviewer Materials

- Grant answers: [docs/grant_submission_answers.md](grant_submission_answers.md)
- Grant application pack: [docs/grant_application_pack.md](grant_application_pack.md)
- Short pitch variants: [docs/grant_short_pitch.md](grant_short_pitch.md)
- Milestones: [docs/grant_milestones.md](grant_milestones.md)
- Screenshots guide: [docs/screenshots.md](screenshots.md)
- Screenshot assets:
  - [docs/assets/screenshots/landing.png](assets/screenshots/landing.png)
  - [docs/assets/screenshots/demo.png](assets/screenshots/demo.png)
  - [docs/assets/screenshots/sertraline-report.png](assets/screenshots/sertraline-report.png)
  - [docs/assets/screenshots/aspirin-safe-no-claim.png](assets/screenshots/aspirin-safe-no-claim.png)
- Demo video script: [docs/demo_video_script.md](demo_video_script.md)
- Reviewer quickstart: [docs/reviewer_quickstart.md](reviewer_quickstart.md)
- Project status: [docs/project_status.md](project_status.md)
- Eval results: [docs/eval_results.md](eval_results.md)

## Local Validation Summary

Run the full validation set from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check app tests evals
.\.venv\Scripts\python.exe -m mypy app evals
.\.venv\Scripts\python.exe -m evals.runner
```

Expected baseline for the final submission state:

```txt
pytest: 35 passed
ruff: all checks passed
mypy: no issues in 29 source files
evals.runner: 12 passed cases, 0 failed cases
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

## Safety Boundaries

OpenCare Proof Kit is not an AI doctor, diagnostic system, medication recommendation engine, or clinical decision-support product.

The final submission must preserve these boundaries:

- no diagnosis;
- no treatment plan;
- no dosage recommendation;
- no instruction to start, stop, or change medication;
- no real patient data;
- no real genetic data;
- no FASTQ, BAM, WGS, or AlphaMissense clinical interpretation pipeline;
- no SaaS auth, payments, Telegram bot, blockchain, or cloud raw genotype upload;
- no source-less medical claims;
- no actionable claim from weak, uncertain, or model-only evidence.

Every generated report must keep the safety note, clinician review note, evidence level, limitations, sources, and audit metadata.

## Manual GitHub Steps

- Confirm `phase-1-github-grant-readiness` is pushed.
- Open the repository page and verify README image links render.
- Confirm the repository license, security policy, contribution guide, roadmap, release checklist, reviewer quickstart, grant docs, screenshots, and demo video script are visible on GitHub.
- Confirm generated `reports/` artifacts remain ignored and are not shown as repository files.
- Confirm repository visibility is public before submitting the grant link.
- Do not change the default branch automatically unless the maintainer explicitly decides to do it.
- Do not merge additional feature work into the submission branch before review.
