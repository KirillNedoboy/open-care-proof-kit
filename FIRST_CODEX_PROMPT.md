# HISTORICAL PROJECT ARTIFACT
# DO NOT USE AS CURRENT REPOSITORY INSTRUCTIONS

Current instructions are maintained in `AGENTS.md`, `AGENTS.product-direction.md`,
and `docs/project-status.md`. This file preserves an earlier bootstrap prompt.

Read AGENTS.md and CHECKPOINT.md first.

Task:
Validate and harden the OpenCare Proof Kit bootstrap repo without changing product boundaries.

Context:
OpenCare Proof Kit is an open-source, local-first toolkit for private, evidence-grounded health AI agents.

Reference MVP:
Medication-to-Doctor Briefing from synthetic/demo health vault + demo genotype/VCF-like data + local evidence packs + deterministic rule engine + safety policy + LLM report writer.

Hard boundaries:
- no diagnosis
- no dosage recommendation
- no start/stop medication advice
- no real patient data
- no FASTQ/BAM/WGS pipeline in MVP
- no SaaS/auth/payments/Telegram in MVP
- no cloud raw genotype upload by default
- do not weaken safety policy or evals

Your tasks:
1. Run the setup and checks:
   - python -m venv .venv
   - source .venv/bin/activate
   - python -m pip install -c constraints/python312.txt -e ".[dev]"
   - pytest
   - ruff check app tests evals
   - mypy app evals
   - python -m evals.runner

2. Fix any failing tests, typing issues, import errors or lint errors.

3. Review the current architecture and improve only where it makes the MVP more reliable:
   - stricter parser validation;
   - clearer Pydantic models;
   - safer report generation;
   - stronger audit JSON;
   - better eval runner output.

4. Do not add:
   - auth;
   - payments;
   - Telegram;
   - blockchain;
   - cloud LLM upload of raw health/genetic data;
   - real patient data;
   - medical recommendations.

5. Update SESSION_NOTES.md with:
   - what you changed;
   - files changed;
   - tests run;
   - risks/blockers;
   - next safe step.

Done when:
- pytest passes;
- ruff passes;
- mypy passes;
- eval runner passes;
- demo endpoint works;
- SESSION_NOTES.md is updated;
- product boundaries remain intact.
