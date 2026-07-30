# Export, backup, and recovery lifecycle

## Status

Phase 1F-A implements the Person-scoped portable export, its API route, and a
Workspace download warning. Phase 1F-B implements the local operator backup and
offline verifier described below. Recovery, import, encryption, and Phase 1F-C
work remain unimplemented.

## Verified current boundary

Product Core's SQLite database is configured by `OPENCARE_PRODUCT_DB_PATH` and
immutable source payloads are held under `OPENCARE_SOURCE_DIR`. Source metadata
records IDs, relative paths, size, SHA-256, type, and provenance. The source
store rejects missing, changed, or root-escaping payloads. The database contains
the medication lifecycle and timeline, Visit preparation state, persisted Brief
revisions, and metadata-only Brief audit events. Runtime configuration, session
state, external vault JSON, and generated reports are outside Product Core state.

## Portable export contract

Phase 1F-A exports exactly one Person with their supported Product Core graph:
Sources, CandidateFacts, canonical medication records, Timeline Events, Visits,
Questions, Briefs, revisions, and evidence selections. It preserves stable IDs
and relationship fields. Source inclusion is graph-derived from CandidateFacts,
canonical records, Timeline Events, and Brief selections; unrelated source files
and internal Brief audit events are excluded. A missing, changed, or unsupported
reachable record fails the export.

Its logical ZIP layout is:

```text
manifest.json
manifest.sha256
vault.json
sources/<source_id>/payload.bin
```

The JSON artifacts are canonical UTF-8 with sorted keys, fixed separators,
normalized UTC timestamps, and stable collection ordering. The manifest lists
payload byte sizes and SHA-256 checksums but not its own; `manifest.sha256`
hashes the exact canonical `manifest.json` bytes. This is an integrity contract,
not encryption, author authentication, or byte-identical ZIP contract.

## Installation backup contract

### Staged snapshot

The operator chooses a final destination directory that must not exist. The
backup service validates the active database and source root, creates a private
staging directory on the destination filesystem, and performs this exact order:

```text
SQLite snapshot
→ enumerate source rows from that snapshot
→ copy and verify source payloads
→ write compatibility metadata and checksums
→ verify staged backup
→ atomically write completion marker
```

The SQLite copy uses Python's `sqlite3.Connection.backup()` API. Only the
completed `database.sqlite3` snapshot is queried. Every snapshot `sources` row
is copied, in source-ID order, to a fixed safe path after its persisted ID,
configured-root containment, non-symlink regular-file status, byte size, and
SHA-256 are checked. Files not represented by a snapshot source row are never
included. Commits after the SQLite snapshot are outside that backup and are not
a consistency failure.

The exact completed layout is:

```text
database.sqlite3
sources/<source_id>/payload.bin
manifest.json
manifest.sha256
COMPLETE
```

`manifest.json` is canonical UTF-8 JSON and records format version, schema
version read from the snapshot, injectable UTC `created_at`, snapshot method,
optional reliable application version, deterministic source inventory, and the
path/size/SHA-256 inventory for the database and payloads. The implementation
supports only schema version 4. `manifest.sha256` is exactly 64 lowercase
hexadecimal ASCII characters followed by one newline for the exact manifest
bytes. Separate snapshots need not share a manifest because `created_at` is an
actual operation time.

The staged layout is independently verified before zero-byte `COMPLETE` is
created exclusively. Immediately before activation, the service rechecks that
the final destination remains absent, then uses a same-filesystem rename without
replacement. A destination that appears during creation is preserved; staging
cleanup is attempted and its failure is reported. Interrupted artifacts have no
completion marker and are invalid.

### Offline verification

`python -m app.product_core.backup_cli verify --backup <directory>` uses only
the given artifact. It opens the supplied SQLite snapshot read-only and does not
consult environment defaults, active database/source paths, HTTP services, or
runtime configuration. It checks exact layout, no symlinks or undeclared files,
`COMPLETE`, canonical manifest/checksum, every declared payload, schema/migration
state, SQLite integrity and foreign keys, source inventory, lifecycle ownership
and question ordering, and Brief revision hashes. The metadata-only JSON report
contains neither health content nor source display names, notes, Markdown, or
secrets.

### Recovery compatibility

The MVP accepts only explicitly supported backup and schema versions. Recovery
is deferred to Phase 1F-C and will be an operator CLI operation for an empty or
maintenance-mode target only. Portable import, merge, and semantic conversion
are separate future work.

## Security and privacy boundary

Backups are sensitive plaintext artifacts. SHA-256 detects changed bytes only;
it does not encrypt content or prove who created an artifact. Backups exclude
`.env`, passwords, `OPENCARE_SECRET_KEY`, provider credentials, cookies, virtual
environments, caches, logs, reports, test artifacts, and TLS/deployment secrets.
The implementation adds neither an HTTP/Workspace backup route, scheduled or
remote storage, cloud integration, encryption, import, nor recovery.

## Future delivery split

### Phase 1F-A: deterministic portable export

Implemented: Person-scoped canonical bundle generation, reachable-source and
Brief verification, manifest/checksum handling, and a Workspace warning. The
request-scoped ZIP has no retained server artifact and writes no export audit.

### Phase 1F-B: installation backup and verification

Implemented: local operator backup and offline verification CLI with staged
SQLite snapshots, exact `COMPLETE` marker, fixed source layout, source and Brief
integrity checks, destination-race refusal, and metadata-only reporting.

### Phase 1F-C: recovery

Planned: preflight, empty-target-only recovery, rollback, and metadata-only
operator report. It must validate all artifact and lifecycle boundaries before
activation and must not introduce populated-target merge or overwrite semantics.

## Test matrix

- backup: empty/populated snapshots, writes after snapshot, source closure,
  missing/changed/path/symlink sources, marker order, interruption, cleanup,
  destination race, and secret exclusion;
- verifier: manifest/payload/database/FK/schema/Brief corruption, undeclared
  files, unsafe paths/symlinks, lifecycle violations, and offline-only access;
- CLI: explicit paths, backup defaults, verify without defaults, exit codes,
  and metadata-only output;
- future recovery: limits, empty-target refusal, atomic activation/rollback,
  and post-activation verification.
