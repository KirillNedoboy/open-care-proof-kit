# Security Policy

OpenCare Proof Kit is an open-source, self-hosted Personal and Family Health
Workspace with local-first trust, provenance, review, and authorization
boundaries. Public repository content is synthetic/de-identified only. The
self-hosted runtime is designed to store user-owned sensitive health, document,
and genetic data locally; this is not a clinical-readiness or compliance claim.

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

Self-hosted runtime operators are responsible for protecting local Product Core
databases, immutable Source directories, backups, exports, and recovery media.
Sources are Person-bound and immutable; access is Actor- and consent-scoped.
Genetics uses separate `genetics.read`, `genetics.write`, `genetics.research`,
`genetics.compare`, and `genetics.export` grants rather than inheriting ordinary
Family Access.

Ordinary Person portable vault export excludes genetics. Genetics Export is a
separate high-friction artifact containing especially sensitive raw and derived
data. Installation backups may contain sensitive database and Source state.
Raw genome content must never enter provider context. External provider
disclosure requires explicit genetics-specific consent; self-hosted providers
receive only authorized selected context.

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
