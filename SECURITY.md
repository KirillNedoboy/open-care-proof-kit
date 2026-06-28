# Security Policy

OpenCare Proof Kit is a local-first proof kit for sensitive health-agent workflows. The current demo uses synthetic data only and is not designed to store, process, or transmit real patient data.

## Do Not Submit Sensitive Data

Do not include real patient data in:

- issues;
- pull requests;
- comments;
- screenshots;
- logs;
- generated reports;
- demo fixtures;
- eval cases.

This includes medications tied to a real person, symptoms, lab results, family history, identifiers, genomic data, or any other protected or sensitive health information.

## Responsible Disclosure

For responsible disclosure, contact the maintainer at [kirillnedoboy@gmail.com](mailto:kirillnedoboy@gmail.com). Do not include real patient data, genetic data, secrets, PHI, or private health records in public issues, pull requests, screenshots, or discussions.

Please include:

- affected files or endpoints;
- reproduction steps using synthetic data only;
- expected impact;
- suggested mitigation if known.

## Local-First Privacy Model

The reference workflow runs locally and uses synthetic/demo data. Audit metadata records whether raw health or genetic data was exported. Cloud raw genotype upload is not enabled by default and is outside the current MVP boundary.

Any future adapter that could move sensitive data outside the local environment must be reviewed as a separate privacy and security design before implementation.

## Secret Handling

- Do not commit `.env` files with secrets.
- Use `.env.example` for documented configuration shape only.
- Do not paste API keys, tokens, credentials, or private URLs into issues or PRs.
- Rotate any secret that is accidentally exposed.

## Generated Reports Policy

Generated report and audit files under `reports/` are runtime artifacts and must remain ignored by Git. They may contain sensitive content in future private use, so they should not be committed, uploaded, or pasted into public issues.

The current repository demo reports are generated from synthetic/demo data, but the same hygiene rule applies.

## Medical Safety Boundary

Security reports and contributions must preserve the medical safety boundary:

- no diagnosis;
- no dosage recommendation;
- no medication start/stop instruction;
- no treatment plan;
- no source-less medical claim;
- no real patient data;
- no cloud raw genotype upload by default.

Do not report medical questions or personal health information through this repository. This project is not a clinical service.
