# Changelog

## [Unreleased]

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

### Security

- Independently protects the final active Person owner and final active
  installation administrator.
- Makes owner grants and Person creation explicit high-risk atomic operations;
  required audit failure rolls back sensitive mutations.
- Keeps invitation codes out of URLs, persistence, logs, audits, exports, and
  backups; only a hash is durable.
- Keeps `/demo/health-vault` and reviewer routes synthetic and separate from
  actor-scoped live surfaces.

## [0.1.0] - 2026-07-31

Published as tag `v0.1.0`, the controlled private-alpha baseline. It is not
production-ready, clinically validated, or clinical software. Phase 2 changes
above are unreleased and do not alter this tag.

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
