# ADR 0005: Family identity and access boundary

- Status: Accepted
- Date: 2026-08-02
- Decision owners: OpenCare maintainers

## Context

Product Core schema v4 has active People and Person-scoped records, but the
shared installation password is not an identity system and does not authorize
one person to see another person's data. A `person_id` path parameter is not
proof of access. The existing local Workspace, Product Core API, and chat
facade must gain a single authorization boundary before family sharing is
introduced.

This is a self-hosted, local-first identity design. It is not multi-tenant
SaaS, a medical authorization claim, a cloud identity provider, or a change to
the frozen PGx reference workflow. It specifies Phase 2 implementation; this
ADR itself changes no runtime behavior.

## Decision

### Separation of actor, Person, and administrator

An **Actor** is an authenticated human account. A **Person** is the subject of
health records. They are different entities. No Actor receives Person access
from a matching name, a family relationship, a family membership, being an
installation administrator, or possession of an own-Person link.

An installation administrator administers the local installation and identity
surface. It has no implicit Person scope and cannot read records, sources,
exports, or chat context merely because it is an administrator. Person owners
and installation administrators are independently assigned roles, and the
last-owner and last-administrator invariants are independently enforced.

### Schema v5 durable state

Migration 5 adds the following Product Core tables. IDs are opaque stable text
IDs; timestamps are normalized UTC text; active-state changes retain their
history rather than silently overwriting it.

| Table | Purpose and required constraints |
|---|---|
| `actors` | Durable local account identity, status (`active` or `disabled`), creation and disable metadata. It contains no health profile fields. |
| `actor_credentials` | One active local-password credential per Actor. It stores algorithm/version, salt, derived verifier, creation time, and replacement/revocation metadata; never a password. A unique active credential per Actor is enforced. |
| `installation_admin_assignments` | Active/inactive installation-administrator assignment for an Actor. It carries no Person ID or Person scope. |
| `families` | A local family container with creation metadata only. It is not an authorization grant. |
| `family_memberships` | Active/inactive membership from a Person to a Family. An active Person has at most one active membership in a Family. |
| `person_relationships` | Recorded relationship between two distinct People in the same Family, with controlled relationship type and active state. Duplicate active directed relationships are rejected. Relationships never grant access. |
| `person_access_assignments` | Actor-to-Person assignment, role (`owner` or `caregiver`), scope set, active state, grantor, and consent reference where required. There may be at most one active assignment for an Actor/Person pair. |
| `person_access_consent_history` | Append-only owner and caregiver grant, acceptance, revision, revoke, and expiry history. It records the acting owner, recipient Actor, target Person, bounded scopes, reason code, and time; it contains no medical content. |
| `own_person_links` | A one-to-zero-or-one mapping in each direction between an Actor and a Person. Creation and continued validity require an active owner assignment for that same Actor and Person. It is a selection convenience only, never an authorization grant. |
| `access_invitations` | One-time invitation metadata: inviter, target Person, requested permitted role/scopes, expiry, state, redemption metadata, and a secret hash only. No plaintext invitation secret is persisted. |
| `access_audit_events` | Metadata-only authorization and sensitive-access audit events: actor, action code, target class/opaque ID, outcome, bounded reason code, and timestamp. It contains no health content, password, session token, CSRF token, invitation secret, request body, or response body. |

The v5 database also contains indexes for active assignment lookups and audit
ordering, foreign keys for all durable references, and database triggers that
refuse an operation that would leave a Person without an active owner or the
installation without an active administrator. Application services perform the
same checks in their `BEGIN IMMEDIATE` transaction; triggers are the final
database guard against a future bypass.

Actor sessions are deliberately not Product Core state. The runtime maintains
opaque, server-side session records at `OPENCARE_SESSION_DB_PATH` in a separate
local session store. A record contains only a session-token verifier, Actor ID,
issued/expiry/revocation metadata, and bounded transport metadata. It contains
no Person scope, health content, password, or raw cookie token. Development
defaults to an installation-namespaced path in the operating-system temporary
directory. Production defaults to `/run/opencare/sessions.sqlite3` on a
restrictive tmpfs. Production Compose enforces ephemeral `/run/opencare` tmpfs
with no volume. Creation requires restrictive owner-only directory and file
permissions. Startup rejects a session path that overlaps the Product Core
database, source root, or either parent/child path. The application cannot
determine whether an arbitrary custom host path is persistent; custom
deployments must keep it runtime-only and excluded from persistent volumes and
backup.

The session store is not part of Product Core SQLite backup, portable export,
offline verifier, preflight, or recovery target. Backup, verify, preflight, and
recovery must not open, copy, validate, create, or restore it. A recovery
therefore restores no live actor session; every user must authenticate again
after recovery.

### Credentials, sessions, and CSRF

Local-password verification is fixed for this phase:

```text
hashlib.scrypt(
    password_utf8, salt, n=32768, r=8, p=1, dklen=64, maxmem=67_108_864
)
```

`n=32768` is `N=2^15`; `r=8` and `p=1` are fixed. The selected parameters use
about 32 MiB of scrypt working memory and impose a 64 MiB Python `maxmem`
limit. Each credential receives a cryptographically random salt of at least 16
bytes. The resulting 64-byte verifier and salt may be stored; the password is
never stored, exported, backed up as plaintext, logged, audited, or returned.
Failed and successful verification use constant-time verifier comparison. This
phase does not add a runtime dependency for password hashing.

Authentication creates an opaque cookie whose server-side record expires eight
hours after issuance. Expiry is absolute, not silently extended by activity.
Cookies are `HttpOnly`, `Secure` when HTTPS is in use, and `SameSite=Lax`; the
token is not written to JavaScript-accessible storage. Login, logout, password
replacement, Actor disablement, and administrator revocation invalidate the
relevant sessions.

Every state-changing Family Access `POST`, including unauthenticated
`bootstrap`, `login`, invitation `preview`, `register`, and `accept`, requires
same-origin validation. Authenticated unsafe methods additionally require a
per-session CSRF token. The CSRF token is compared server-side and is not
accepted from a URL. Missing, malformed, or invalid same-origin or CSRF
validation is a privacy-safe `403` with no Person or assignment detail.

### Invitations

An invitation secret is generated from at least 32 cryptographically random
bytes and is shown once to the inviter for out-of-band delivery. The durable
record stores only a SHA-256 hash of that high-entropy secret. Redemption is a
single `POST` body value and atomically verifies, consumes, and records the
invitation. The secret must never appear in a URL, query string, path,
fragment, browser history, log, audit event, backup, portable export, error
message, analytics payload, or telemetry. Backup may contain the invitation
metadata and hash; it never contains the secret.

The generic invitation flow uses body-only API routes:
`POST /api/family-access/v1/invite/preview`,
`POST /api/family-access/v1/invite/register`, and
`POST /api/family-access/v1/invite/accept`. These routes accept the secret only
in the request body and provide the same generic failure response for an
invalid, expired, revoked, or consumed invitation. A valid recipient of either
a caregiver or owner invitation may register and redeem it. Caregivers cannot
issue or manage invitations, create owners, or upgrade an invitation to owner.

### Centralized Person policy

Every Person-scoped service, repository-facing application operation, export,
source payload read, and future read-only tool calls one centralized,
deny-by-default `PersonAccessPolicy`. Routers and templates do not infer
authorization from a path, selected Person, family membership, relationship,
or UI visibility. The policy resolves an authenticated Actor and an active
assignment for the requested Person before the operation reads or mutates the
target's data.

An owner assignment always grants exactly this fixed full scope set:

```text
person.read, person.update, source.read, source.write, candidate.read,
candidate.review, medication.read, medication.write, timeline.read,
visit.read, visit.write, brief.read, brief.write, brief.export, vault.export,
relationship.read, relationship.manage, access.read, access.manage, chat.use
```

It is not an arbitrary caller-supplied scope list. Every caregiver starts with
this fixed base set:

```text
person.read, source.read, candidate.read, medication.read, timeline.read,
visit.read, brief.read, relationship.read, chat.use
```

An owner may additionally select only these optional caregiver scopes:

```text
source.write, candidate.review, medication.write, visit.write, brief.write,
brief.export, vault.export
```

Caregivers never receive `person.update`, `relationship.manage`, `access.read`,
or `access.manage`; they cannot create or change owners/caregivers, issue or
manage access invitations, link an own Person, manage credentials, or administer
the installation. Optional caregiver scope revision changes only the bounded
caregiver set. A caregiver-to-owner upgrade is prohibited through scope revision
and must instead be a new explicit owner grant or owner invitation with
`confirm_full_owner_access: true`; no conversion is silent. New Person
operations are denied until this matrix is explicitly extended by a new ADR.

Owner invitations, owner assignment creation, and owner assignment
reactivation are high-risk operations. Each requires the exact request field
`confirm_full_owner_access: true`; an omitted or false value performs no write
and returns `403 owner_confirmation_required` only after the caller has been
authorized to manage that Person. An owner invitation grants the fixed full
owner scope set above. The same transaction validates the proposed post-write
owner count and inserts its audit event. `confirm_owner_assignment: true` is
reserved for authenticated Person creation and must not authorize an owner
invitation or assignment change.

Creating a Person from the authenticated workspace is atomic: the caller must
send `confirm_owner_assignment: true`, and one transaction inserts the Person,
an active fixed-scope owner assignment for the Actor, and the success audit
event. Any validation, authorization, constraint, or audit failure rolls back
all three rows. The service never creates an ownerless new Person.

Existing v4 People are not automatically assigned to an Actor. Bootstrap is
available only when there are zero Actors, and, in private production, is also
behind the existing outer `/access` gate. It is not a remote unauthenticated
bootstrap path. The bootstrap transaction creates the first Actor, credential,
and installation-administrator assignment, plus the selected existing-Person
owner consent records, fixed full owner assignments, and success audits. An
empty installation may select no existing Person. Failure rolls back the whole
transaction. An authorized administrator can then create or invite an owner
for each pre-existing Person with `confirm_full_owner_access: true`. Until
claimed, a migrated Person is inaccessible through the actor-protected
Workspace and API. Migration does not infer identity from names or create
relationships, consent, access, or health data.

### Family access API and deactivation

The authentication and access-management surface is
`/api/family-access/v1`. It provides exactly these initial auth routes:

| Route | Purpose |
|---|---|
| `GET /bootstrap-status` | Reports only whether bootstrap is available; it reveals no Actor, Person, membership, or installation totals. |
| `POST /bootstrap` | Performs the zero-Actor atomic bootstrap described above. |
| `POST /login` | Verifies a credential and creates an eight-hour Actor session. |
| `POST /logout` | Revokes the current session. |
| `GET /me` | Returns only the current Actor's permitted self metadata and active selection, never hidden People or assignments. |
| `POST /password:change` | Replaces the current Actor credential after CSRF and current-password verification. |
| `PUT /active-person` | Changes the Actor's selected own/accessible Person only after `PersonAccessPolicy` approval; the selection is not a grant. |
| `GET /actors` | Installation-admin-only, privacy-minimal actor administration list. |
| `POST /actors/{actor_id}:deactivate` | Installation-admin-only durable Actor deactivation. |
| `POST /invite/preview` | Body-only generic invitation preview; it never exposes invitation state through an error. |
| `POST /invite/register` | Body-only registration for a valid caregiver or owner invitation recipient. |
| `POST /invite/accept` | Body-only, atomic caregiver or owner invitation acceptance. |

All list responses, including `GET /actors`, return no hidden names, opaque IDs,
memberships, counts, or installation totals. Unauthorized callers receive the
same non-disclosing response shape. Any Person-targeted list follows the same
`404` policy as a single Person read.

Actor deactivation runs in one `BEGIN IMMEDIATE` transaction. Before mutation,
it independently checks the post-write last-administrator and last-owner
invariants. The transaction marks the Actor inactive, revokes its
installation-admin assignment, revokes every active Person access assignment,
appends consent-revocation history, clears its own-Person link, and writes all
required metadata-only audits. Credentials remain durable but unusable. After
commit, the runtime invalidates every session for that Actor. If session cleanup
fails, the inactive Actor state remains decisive and every request rejects it;
the cleanup failure is an operator-safe error without secrets or health data.

### Audit atomicity and HTTP privacy semantics

For every successful sensitive mutation (credentials, installation
administrators, assignments, consent, family membership, relationships,
own-Person links, invitations, and Person export), the state change and its
success audit insert run in one transaction. If the audit insert fails, the
mutation is rolled back and the request fails. A successful sensitive mutation
without durable audit is therefore impossible.

Denied Person access is audited best-effort with metadata only. If writing that
denial audit fails, the response remains privacy-safe and does not reveal
whether the Person, assignment, invitation, or relationship exists. The
failure is surfaced only through a local operator-safe health/error signal
without request secrets or health content.

HTTP responses are fixed as follows:

| Status | Meaning |
|---|---|
| `401` | No valid, unexpired Actor session. API responses do not disclose target existence; browser facades may redirect only to the actor sign-in route. |
| `403` | Authenticated Actor reached a non-Person-scoped protected control but lacks the required installation privilege, CSRF validation, or explicit high-risk confirmation. It reveals no Person record state. |
| `404` | A Person-scoped route returns the same response for an unknown Person, an inactive Person, missing resource beneath that Person, or a Person policy denial. This prevents Person enumeration. |

The actor session guard protects `/vault`, `/workspace`, every related live
vault API, every `/api/product-core/v1` route, `/chat`, and `/api/chat`. The
facade must obtain the Actor from the session and invoke `PersonAccessPolicy`; it
may not hand a raw Person ID to Product Core services. Existing synthetic
demo/reviewer surfaces and the frozen PGx workflow remain unchanged.
`/demo/health-vault` and all reviewer/demo surfaces never touch Actor or live
access state. Conversely, `/vault`, `/workspace`, and `/chat` live routes never
fall back to demo context.
The old installation password gate may remain an outer deployment gate during
transition, but it is not an Actor session and cannot satisfy this policy.

### Export, backup, verify, and recovery

Person portable export advances to format v2 when v5 is implemented. It retains
the v1 canonical layout and Person-owned medical graph, and adds the selected
Person's family membership, Person relationships involving that Person,
consent-history entries where that Person is the subject, and non-secret
relevant access-assignment history. It excludes credentials, sessions,
installation-admin assignments, own-Person links, invitation records/hashes,
access-audit records, raw invitation secrets, CSRF data, and unrelated Actor
identity data. Export authorization is scope-based: any active assignment with
`vault.export` may export. Owners always have it; caregivers have it only when
the owner explicitly grants that optional caregiver scope. `brief.export` is
likewise available to any active assignment carrying that scope. Each export is
a sensitive audited operation.

Installation backup remains an offline Product Core snapshot and can contain
v5 durable Product Core metadata, including credential verifiers and invitation
hashes, but never raw passwords, raw invitation secrets, cookies, or session
records. `backup`, `verify`, `preflight`, and `recover` never open, copy,
validate, create, or restore the session store. Recovery restores durable
Actor, credential, installation-administrator, access-assignment, consent,
invitation, and audit state exactly as it exists in the selected verified
backup. It cannot preserve a revocation made after that snapshot. The operator
must select the intended restore point and review active Actors,
administrators, assignments, and outstanding invitations before reopening the
live HTTP service. Sessions are never restored. Recovery never migrates,
normalizes, or invents state. These are installation-operator workflows that
require no Actor session, Person access assignment, or Person impersonation.

Migration 5 is one `BEGIN IMMEDIATE` v4-to-v5 transaction. It creates only the
v5 tables, indexes, and invariant triggers; it leaves v4 Person and medical
rows unchanged and inserts no Actors, credentials, families, memberships,
relationships, consents, assignments, invitations, audits, or sessions. A
failed migration rolls back to an intact v4 database. After a committed v5
migration there is no in-place down migration: rollback means recover a
verified v4 backup with the v4 release into an absent or empty target, or
restore an operator-created pre-migration snapshot. The v5 recovery path
accepts only an explicitly supported complete v5 backup and does not apply
migrations during recovery.

### Required implementation verification

The implementation must add focused tests for:

- fresh v5 creation, v4-to-v5 preservation, transactional migration failure,
  and the absence of inferred actor/access data;
- scrypt parameters, random salt length, verifier-only storage, constant-time
  comparison boundary, eight-hour absolute expiry, logout/revocation,
  same-origin login-CSRF protection, and authenticated CSRF;
- one-to-one own-Person links and their no-access property;
- fixed owner scopes, every caregiver scope boundary, centralized deny by
  default, and `404` indistinguishability for Person denial;
- the approved owner/caregiver matrix, owner invitation confirmation with
  `confirm_full_owner_access: true`, atomic Person-plus-owner creation with
  `confirm_owner_assignment: true`, and separate last-owner/last-admin refusal
  under concurrent transactions;
- `OPENCARE_SESSION_DB_PATH` defaults, restrictive path creation, overlap
  rejection, Compose tmpfs/no-volume enforcement, custom-deployment operator
  requirement, and no backup/recovery/export access;
- zero-Actor bootstrap and every `/api/family-access/v1` route, atomic Actor
  deactivation, post-commit session invalidation, and no hidden list data;
- invitation one-time redemption, expiry/revocation, hash-only storage, and
  scans proving that secrets do not enter URLs, logs, audit, backup, or export;
- audit success rollback, denial-audit failure privacy behavior, and
  metadata-only audit content;
- Workspace, Product Core API, and chat facade protection while preserving demo
  surfaces and the PGx reference workflow; and
- scope-based v2 export closure/exclusions plus offline v5 backup, verify,
  preflight, and recovery proving that sessions are never present or restored
  and that revocations in the selected backup remain revoked.

Repository validation remains the applicable `pytest`, `ruff check app tests
evals`, `mypy app evals`, and `python -m evals.runner` sequence when runtime
work lands. No Phase 3 agent/tool capability, new runtime dependency, release
version change, or v0.1.0 demo-surface change is part of this decision.

## Rejected alternatives

- Reusing the shared installation password as an individual identity or
  authorization grant.
- Deriving access from a Person ID, matching name, relationship, family
  membership, administrator role, or own-Person link.
- Giving installation administrators automatic record access.
- Making owner scopes caller-configurable or allowing caregivers to manage
  access outside their approved fixed/optional scope matrix.
- Persisting actor sessions in the Product Core database or carrying them
  through backup and recovery.
- Emailing or URL-encoding invitation secrets.
- Allowing a sensitive write to succeed when its audit event cannot be stored.
- Treating schema rollback as a destructive in-place down migration.

## Consequences

Phase 2 can add explicit local family access without changing the source,
review, canonical-record, provenance, medical-safety, or local-first
boundaries. It also creates deliberate operational work: the first local
administrator must bootstrap an installation, existing People must be
explicitly claimed by owners, and all new Person endpoints must use the one
policy boundary.
