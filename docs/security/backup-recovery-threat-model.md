# Backup and recovery threat model

## Status and boundary

Phase 1F-A portable export, Phase 1F-B local operator backup/verification, and
Phase 1F-C fail-closed recovery are implemented. These artifacts contain sensitive
health data in plaintext. They require operator-controlled destinations and
local handling. Phase 1F does not add encryption, signing, cloud storage,
scheduled jobs, sharing or public backup and recovery HTTP endpoints.

SHA-256 checksums detect changed bytes after an expected checksum is available.
They do not encrypt content and do not establish the identity of the artifact
creator.

| Threat | Required control | Failure behavior |
|---|---|---|
| Accidental disclosure or plaintext theft | Sensitive-data warning, operator-controlled destination, restrictive destination permissions and no secret values in artifacts/logs. | Refuse unsafe/unwritable destination where permissions can be checked; report metadata only. |
| Malicious archive path or symlink | Reject absolute/traversal/duplicate normalized paths, symlinks and special files before extraction. | Abort before activation. |
| Zip bomb or resource exhaustion | Enforce implementation-defined maximum archive bytes, entry count, per-file size and extracted total before writing files. | Abort and remove temporary staging. |
| Corrupted or substituted backup | Verify completion marker, exact manifest checksum, every payload checksum, SQLite integrity/FKs and lifecycle hashes. | Fail closed; do not activate. |
| Incomplete source store | Enumerate every persisted source ID from the database snapshot; verify each copied payload path, regular-file status, size and hash. | Backup is incomplete without marker; verifier and recovery reject it. |
| Tampered Brief revision | Recompute supported Brief content/Markdown hash and reject unsupported versions. | Fail closed; do not expose the restored installation. |
| Stale backup | Include creation timestamp and version metadata in report; do not claim freshness. | Operator explicitly decides whether to recover an older complete backup. |
| Restore into wrong/populated installation | Require an absent or real empty target, explicit maintenance acknowledgement, path-overlap/link checks, and a safe target path report. | Refuse populated target. |
| Interrupted activation | Stage under target filesystem; activate with atomic rename and retain rollback material until post-checks pass. | Restore prior empty target layout and leave service unavailable. |
| Temporary extraction leakage | Use protected temporary directories, no user-controlled names, cleanup on success/failure, no content logging. | Cleanup failure is reported as an operator action, never treated as success. |
| Restored access state | Preserve and verify durable Actor, credential, administrator, Family, relationship, consent, assignment, invitation-hash, and access-audit state. Exclude plaintext passwords, invitation codes, secret key, cookies, and the runtime session database. | Revoked access in the selected snapshot stays revoked; every Actor logs in again and creates a new session. |

The implemented verifier opens only the supplied backup directory. It does not
consult environment defaults, the active Product Core database, active source
directory, or runtime HTTP services. It checks `COMPLETE`, canonical manifest
bytes/checksum, exact declared layout, payloads, SQLite/FK/lifecycle consistency,
source metadata, Brief revision integrity, role-scope policy, and active
Actor/admin/assignment/own-Person-link invariants before reporting success.

Recovery preflight is strictly read-only and recovery requires explicit paths,
an absent or real empty target, and `--confirm-maintenance`. The flag records
operator acknowledgement rather than proving the application is stopped.
Recovery restores durable credential verifiers but no plaintext passwords,
secret key, provider key, cookie, Actor session, TLS, or deployment
configuration. A fresh runtime session store starts empty and recovered Actors
must authenticate again. Recovery uses
same-filesystem staging and guarded renames, verifies after activation, and
rolls back handled failures. It does not guarantee a crash- or power-loss-safe
state between filesystem operations; exact private abandoned artifacts block a
later operation for manual diagnosis.

## Review and test requirements

Tests assert no secret leakage or sensitive logging, source/checksum
verification, strictly read-only preflight, safe temporary-directory cleanup,
path/symlink rejection, empty-target refusal, guarded activation, rollback, and
a verified post-recovery lifecycle.
