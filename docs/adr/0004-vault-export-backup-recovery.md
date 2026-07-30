# ADR 0004: Vault export, installation backup, and recovery

- Status: Accepted
- Date: 2026-07-30
- Decision owners: OpenCare maintainers

## Context

Product Core persists Person-scoped data in SQLite at
`OPENCARE_PRODUCT_DB_PATH`. Immutable source payloads live separately at
`OPENCARE_SOURCE_DIR`; each persisted Source records a relative path, byte size
and SHA-256 hash. The current source store verifies those values when it reads a
payload. SQLite migrations and Product Core writes use explicit transactions.

Product Core now has People, Sources, CandidateFacts, confirmed medication
records, Timeline Events, Visits, Visit Questions, persisted Visit Briefs,
immutable Brief revisions, evidence selections and metadata-only Brief audit
events. The earlier Markdown Visit Brief download is a single-document export,
not a vault export or installation backup. Generated report artifacts are
ignored and are not installation state.

The installation-wide password gate uses externally supplied
`OPENCARE_SECRET_KEY` and `OPENCARE_ACCESS_PASSWORD`. Its signed cookie is not
Product Core data. Neither value may enter an export or backup.

## Decision

Phase 1F defines three separate capabilities. Phase 1F-A, Phase 1F-B, and
Phase 1F-C are implemented.

### Portable vault export

The initial export is a Person-scoped, versioned logical bundle. It is intended
for user possession, inspection, future import and transfer between OpenCare
installations. It is not an SQLite dump and does not expose storage paths or
database implementation details.

The bundle contains the selected Person and all supported Product Core entities
that belong to that Person: Sources, CandidateFacts, canonical medication
records, Timeline Events, Visits, Visit Questions, Visit Briefs, Brief
revisions and their evidence selections/provenance snapshots. Stable IDs and
references are preserved. Unknown future record types are not silently dropped:
an exporter that cannot represent a reachable supported record fails with an
unsupported-record error.

It includes only source payloads reachable from included CandidateFacts,
canonical records, Timeline Events and Brief evidence selections. Unrelated
installation sources are excluded. A required source whose payload is missing,
has a different size, or fails its recorded SHA-256 check causes a fail-closed
export.

Payload paths are fixed and safe: `sources/<source_id>/payload.bin`. They never
derive from a source filename or suffix. `vault.json` stores source type, media
type and any future display filename as metadata only. Internal Brief audit
events stay out of portable export; they are operational installation history.

The bundle layout is:

```text
manifest.json
manifest.sha256
vault.json
sources/<source_id>/payload.bin
```

`vault.json` and `manifest.json` use canonical UTF-8 JSON: sorted keys, fixed
separators, normalized UTC timestamps and specified stable ordering. The
manifest names the export format version, Product Core schema version, bundle
scope, payload inventory and SHA-256 checksum for every payload other than the
manifest. `manifest.sha256` is the SHA-256 of the exact canonical UTF-8 bytes of
`manifest.json`; the manifest does not contain its own checksum.

Identical logical state must produce identical canonical JSON and checksums. A
byte-identical archive is not promised: archive container metadata and transport
are not logical state. Checksums detect accidental or malicious modification but
do not encrypt data or establish who produced it.

Phase 1F-A implements this bundle as `POST
/api/product-core/v1/people/{person_id}/vault-export` and an explicit Workspace
download warning. It uses a request-scoped spooled ZIP artifact, checks each
reachable source for a regular non-symlink file, configured-root containment,
size, and SHA-256, and verifies every persisted Brief revision hash before a
response is produced. It creates no audit event and retains no server-side
export artifact. Portable import and encryption are still not implemented.

### Installation backup

An installation backup is an operator-controlled operational snapshot, not a
user-facing interchange format. It contains a consistent SQLite snapshot,
every immutable source payload represented by a `sources` row in that snapshot,
Product Core audit data already in the database, compatibility metadata,
payload checksums, and a completion marker.

The chosen snapshot mechanism is Python's SQLite backup API. It creates a
consistent database copy while avoiding unsafe direct copying of a live SQLite
database. `VACUUM INTO` is not selected because the runtime already owns SQLite
through Python connections and the backup API provides the clearest transaction
and error boundary for this application.

The implementation order is mandatory:

```text
SQLite snapshot
→ enumerate referenced immutable sources from that snapshot
→ copy and verify source payloads
→ write compatibility metadata and checksums
→ verify the complete staged backup
→ atomically write the completion marker
```

Writes committed after the SQLite snapshot are outside that backup. They are not
loss or an inconsistency in the completed snapshot. A backup is incomplete until
the final marker is present and all preceding checks pass. The implemented layout
is exactly:

```text
database.sqlite3
sources/<source_id>/payload.bin
manifest.json
manifest.sha256
COMPLETE
```

`COMPLETE` is a zero-byte exclusive marker created only after an independent
staged verification. `manifest.sha256` is exactly the 64 lowercase hexadecimal
SHA-256 characters for the canonical `manifest.json`, followed by one newline.
The manifest records the schema version read from the completed SQLite snapshot;
the current implementation accepts exactly Product Core schema version 4.

Backups exclude `.env`, passwords, `OPENCARE_SECRET_KEY`, provider keys, session
cookies, virtual environments, caches, logs, generated reports, test artifacts,
and TLS/deployment secrets. They do not attempt to recreate host configuration;
operators provide configuration and credentials separately.

### Recovery

Recovery is an operator CLI procedure for an absent or real empty target. It
requires `--confirm-maintenance` as an operator acknowledgement that the target
is not being used by OpenCare; the CLI cannot prove this. It does not merge
records into a populated installation, and a populated target is always
rejected.

Recovery validates the artifact before activation: format/schema compatibility,
completion marker, paths, symlinks, resource limits, checksums, SQLite integrity
and foreign keys, source payload hashes, Product Core lifecycle relations and
persisted Brief revision hashes. It stages reconstruction in a protected
temporary directory and atomically activates verified data with same-filesystem
renames. The database is restored byte-for-byte without migrations,
normalization, or new domain/audit rows. Handled failures restore the prior
absent state or original empty directory. Crash or power-loss consistency
between filesystem operations is not guaranteed; exact abandoned recovery
artifacts are detected and block a subsequent run.

Recovery does not claim to invalidate existing browser sessions. The current
access cookie remains valid only if the separately managed secret key is the
same; backup deliberately excludes that key and access password.

## Interfaces and boundaries

The future Workspace interface is limited to an explicit Person export action,
a sensitive-data warning, a deterministic safe filename and no persistent
server-retained export artifact. A request-scoped temporary artifact is allowed
only when needed for transport and must be removed on success and failure.

The implemented operator CLI owns installation backup and verification:
`python -m app.product_core.backup_cli backup` and `verify`. Verification opens
only the supplied backup directory and has no dependency on active runtime
settings, database, source directory, or HTTP services. Recovery is operator
CLI work: `preflight --backup <directory> --target-root <root>` is read-only,
and `recover --backup <directory> --target-root <root> --confirm-maintenance`
requires an absent or empty target. Full backup and recovery must not be exposed
through ordinary HTTP or Workspace routes.

Portable export does not mean import is implemented. Arbitrary merge, conflict
resolution, identity remapping, partial import, cross-version semantic
migration, external healthcare formats and FHIR breadth remain deferred.

## Consequences

The design supports reproducible logical inspection without binding users to
SQLite internals, while retaining a separate path for disaster recovery. It
requires future implementations to enforce source completeness and artifact
validation rather than treating an archive as trustworthy by default.

Cloud backup, scheduled jobs, remote object storage, encryption and key
management, sharing, Identity, caregiver permissions, family relationships,
upload/OCR, Sentient/EvoSkill work and deployment changes remain out of scope.

## Rejected alternatives

- Treating an SQLite file as portable export: leaks implementation details and
  cannot safely represent a future cross-installation contract.
- Metadata-only Person export: cannot reconstruct source-backed lifecycle or
  independently verify included evidence.
- Direct copy of live SQLite files: unsafe with journal/WAL state and concurrent
  writers.
- Full backup/recovery HTTP endpoints: unsuitable for sensitive operational
  artifacts and installation-level destructive actions.
- Silent partial export or restore: turns missing sources and unsupported data
  into undetectable loss.
