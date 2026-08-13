# Changelog

## [0.2.0] - 2026-08-04

### Added

- Product Core schema v5 with local Actors, versioned scrypt credentials,
  installation administrators, Families, relationships, append-only consent,
  Person assignments, hash-only invitations, own-Person links, and access audit.
- Central deny-by-default Person policy for live Workspace, vault, Product Core
  API, and chat, with fixed owner/caregiver scopes and privacy-safe
  `401`/`403`/`404` behavior.
- Server-side eight-hour Actor sessions in a separate runtime database,
  same-origin checks, CSRF enforcement, login/bootstrap, Person switching, and
  Family/access management flows.
- Deterministic Person export v2 and schema v5 offline backup/recovery checks,
  including restored credentials and revocations without restored sessions.
- Focused scrypt validation on Windows and Linux CPython 3.12 CI paths.
- Sentient G1 Trust Envelope contract and `app/agent_trust/` implementation:
  frozen versioned models, controlled actions, canonical UTF-8 JSON, SHA-256
  content identities, trusted builders, integrity validators, OpenCare Family
  Access adapter, synthetic fixtures/evals, and export/verify/inspect CLI tools.
- Ten named Sentient G2 trust-evaluation fixtures and eval-registration
  coverage for consent, mediation, refusal, isolation, TOCTOU, and audit
  acceptance categories. These fixtures do not claim external integration.

### Security

- Independently protects the final active Person owner and final active
  installation administrator.
- Makes owner grants and Person creation explicit high-risk atomic operations;
  required audit failure rolls back sensitive mutations.
- Keeps invitation codes out of URLs, persistence, logs, audits, exports, and
  backups; only a hash is durable.
- Keeps `/demo/health-vault` and reviewer routes synthetic and separate from
  actor-scoped live surfaces.
- Treats Envelope hashes as tamper detection only, never live authorization;
  arbitrary JSON cannot mint an authorized Envelope, and G2 must reauthorize
  actor, Person, consent, evidence, safety, provider, and expiry before use.

## [0.1.0] - 2026-07-31

Published as tag `v0.1.0`, the controlled private-alpha baseline. It is not
production-ready, clinically validated, or clinical software. The Phase 2
Family Identity and Access Boundary is published separately as `v0.2.0` and
does not change the claims or limitations of this baseline.

### Included

- Persistent People and a Medication source, candidate, review, canonical, and
  timeline lifecycle.
- Visits, Questions, and persisted editable Visit Brief revisions.
- Deterministic Person vault export plus installation backup, verify, preflight,
  and fail-closed recovery.
- Product Core Workspace UI and wheel-packaged runtime assets.
- Production Compose Product Core persistence through explicit bind mounts.
- Python 3.12 constraints and deterministic tests, evals, and trust checks.

### Limitations

This candidate does not provide diagnosis, treatment advice, clinical
validation, production readiness, import/merge, populated-target recovery,
destructive overwrite, encryption, or cloud backup.
