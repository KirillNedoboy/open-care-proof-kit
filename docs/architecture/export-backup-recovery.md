# Export, backup, and recovery lifecycle

## Status

This document is the proposed Phase 1F design. No vault export, installation
backup, recovery command, import path, API route or UI control is implemented
by this document.

## Verified current boundary

Product Core's SQLite database is configured by `OPENCARE_PRODUCT_DB_PATH`.
`OPENCARE_SOURCE_DIR` holds immutable source payloads; Source metadata records
their IDs, relative paths, sizes, SHA-256 hashes, types and provenance. Source
reads already fail if the file is absent, has a different size or hash, or its
path escapes the configured source root.

The database contains the medication review lifecycle and derived timeline, as
well as Visit preparation state and metadata-only Brief audit events. Brief
revisions carry a deterministic content hash over their versioned content and
stored Markdown. Runtime configuration, session state, external local-vault
JSON and generated `reports/` outputs are outside this Product Core state.

## Portable export contract

### Scope and graph closure

The first format exports exactly one Person. It includes records whose
`person_id` belongs to that Person, child records linked through their stable
IDs, and Visit Brief material linked through exported Visits. It preserves IDs
and relationship fields rather than rewriting references.

Source inclusion is graph-derived, not directory-derived. The exporter collects
source IDs referenced by exported CandidateFacts, canonical medication records,
Timeline Events and Brief evidence selections. It verifies each selected Source
metadata row and payload using the current immutable source checks before it
writes any successful bundle. Other source files in the installation are not
read or exported.

The portable bundle excludes internal `visit_brief_audit_events`: they are
installation operational metadata, not part of Person interchange. Unsupported
reachable records or malformed rows stop the operation with an explicit error.

### Logical layout

```text
manifest.json
manifest.sha256
vault.json
sources/<source_id>/payload.bin
summary.md                 # optional and explicitly non-authoritative
```

`vault.json` contains one versioned object with ordered arrays for Person,
Sources, CandidateFacts, canonical records, Timeline Events, Visits, Questions,
Briefs, Brief revisions and evidence selections. References use stored IDs.
Source metadata contains type, media type, size, hash and provenance; it does
not contain a local filesystem path. A future original display filename is only
metadata and never determines an archive path.

Sort collections by stable ownership and IDs; ordered Questions and evidence
selections preserve their explicit position before their IDs. Use canonical UTF-8
JSON with sorted object keys, separators `,` and `:`, and UTC ISO-8601 timestamp
strings. The export format version and Product Core schema version are explicit.

The manifest inventories `vault.json`, each `payload.bin`, and optional summary,
with byte sizes and SHA-256 checksums. It contains no checksum for itself.
`manifest.sha256` hashes the exact canonical bytes of `manifest.json`. A reader
checks the manifest first, then every inventory entry. These checks prove
integrity only; they do not authenticate an author or encrypt health data.

An archive container is a transport choice, not part of determinism. The logical
payload and checksums are deterministic; byte-identical ZIP output is not an
acceptance criterion.

## Installation backup contract

### Staged snapshot

The backup service writes to a newly created, operator-selected staging path on
the target filesystem. It uses the Python SQLite backup API to create
`database.sqlite3`, then queries that snapshot—not the live database—to identify
every referenced Source. It copies each payload to the fixed safe source layout,
verifies size and SHA-256 against snapshot metadata, writes compatibility
metadata and checksum inventory, and independently verifies all staged files.

Only after those checks does it atomically create `backup.complete`. Its presence
is the completion signal. An interrupted operation has no marker and is not a
recoverable backup. New records committed after the SQLite snapshot are outside
the backup and are not treated as a failed consistency check.

Metadata records backup format version, Product Core schema version, backup
creation timestamp, application/repository version when available, snapshot
method, and the source inventory. It contains no credentials, passwords,
secrets, cookies, filesystem paths, logs or generated report content.

### Recovery compatibility

The MVP accepts only explicitly supported backup and schema versions. It can
restore complete installation backups, not portable exports. Portable import,
merge and semantic conversion are separate future work.

## Recovery state machine

1. Refuse a non-empty target unless it is an explicitly entered maintenance-mode
   empty target.
2. Open the supplied artifact with size, file-count and extraction limits;
   reject absolute paths, traversal, duplicate normalized paths, special files
   and all symlinks.
3. Extract into a protected temporary directory under the destination volume;
   never trust archive path metadata.
4. Require and validate the atomic completion marker, exact manifest bytes,
   supported versions, inventory and every file checksum.
5. Open the staged SQLite database with foreign keys enabled; run SQLite
   integrity and foreign-key checks, then Product Core lifecycle checks.
6. Verify every source referenced by the staged database exists at its fixed
   staged location and matches stored size/hash. Verify every persisted Brief
   revision's supported versions and content/Markdown hash.
7. Produce a pre-activation report with entity counts, source count, versions
   and pass/fail reason codes; it contains no source content, notes or names.
8. Atomically rename verified staged database/source directories into the empty
   target on the same filesystem. If any activation action fails, restore the
   prior target layout and keep the installation unavailable.
9. Re-open the activated state and repeat database, foreign-key, source and
   Brief integrity checks. Emit a final metadata-only recovery report.

Any missing file, malformed JSON, integrity failure, unsupported version,
foreign key violation, missing/corrupt source, symlink, traversal attempt,
partial backup, stale completion marker or Brief hash mismatch fails closed.
No invalid record is skipped.

## Future delivery split

### Phase 1F-A: deterministic portable export

Deliver Person-scoped canonical bundle generation, reachable-source verification,
manifest/checksum handling and Workspace download with an explicit sensitive-data
warning. Do not add import, installation backup, encryption, server-retained
files or audit export.

Acceptance includes deterministic ordering/checksums, Person isolation, source
closure, provenance, no paths/secrets, empty/populated Person cases and Brief
revision integrity. Missing or corrupt reachable sources fail the export.

### Phase 1F-B: installation backup and verification

Deliver operator CLI backup and verify commands using the staged Python SQLite
backup sequence and atomic completion marker. Do not add recovery, cloud/scheduled
backup, remote storage, secrets, deployment changes or Workspace backup controls.

Acceptance covers concurrent writes around snapshot time, source completeness,
interruption, marker atomicity, checksum verification and excluded credential
material. No completed marker means failure.

### Phase 1F-C: recovery

Deliver operator CLI preflight, recovery, rollback and metadata-only report for
empty/maintenance targets. Do not add populated-installation merge, destructive
overwrite by default, portable import or cross-version semantic conversion.

Acceptance covers clean reconstruction, database/FK/source/Brief checks,
corruption, traversal, symlinks, resource limits, non-empty target refusal,
activation interruption and a clean post-recovery lifecycle smoke.
