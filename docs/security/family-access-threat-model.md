# Family identity and access threat model

## Status and boundary

This is the Phase 2 implementation threat model for the accepted family
identity and access design in
[ADR 0005](../adr/0005-family-identity-access-boundary.md). It covers local
Actor authentication, Person-scoped authorization, invitations, audit, export,
and interaction with existing offline backup and recovery. It does not make
OpenCare a medical device, multi-tenant SaaS, cloud identity service, or
clinical authorization system.

Actors, People, family membership, and family relationships remain distinct.
Only an active explicit `person_access_assignment` can authorize Person data.
The policy is deny-by-default.

## Threats, controls, and required tests

| Threat | Required control | Failure behavior | Required test evidence |
|---|---|---|---|
| Shared-password impersonation or path-ID authorization | Actor sessions replace the shared password as the Person authorization input. A centralized policy requires an active assignment for every Person operation. | No Actor session: `401`. Unknown, inactive, or unauthorized Person target: indistinguishable `404`. | A valid old access cookie and a guessed `person_id` cannot read, write, export, or reach a source payload. |
| Relationship or family membership grants accidental access | Relationships and memberships are record context only; the policy ignores them. | `404` for a Person data request without an active assignment. | Every relationship/membership combination is denied without an assignment. |
| Installation administrator reads family health data | Installation-admin assignment is separate from Person access and has no Person scopes. | Person data request returns `404` unless the administrator also has an active Person assignment. | Administrator-only Actor cannot enumerate, read, export, or chat over a Person. |
| Lockout or privilege-removal race | `BEGIN IMMEDIATE` service checks and SQLite triggers preserve at least one active owner per Person and one active installation administrator. | The revocation/deactivation/delete transaction fails and leaves prior state intact. | Concurrent attempts cannot remove the final owner or final administrator; the two invariants are tested independently. |
| Ownerless new Person | Person creation requires `confirm_owner_assignment: true` and inserts the Person, self-granted owner consent, complete owner assignment, optional valid identity link, and access audit atomically. | No Person is created on missing confirmation, failed authentication/CSRF, constraint failure, or audit failure. | Transaction-failure cases leave no orphan Person, consent, assignment, identity link, or success audit. |
| Caregiver privilege escalation | Owner receives the fixed full ADR 0005 matrix. Caregiver has its fixed base set and only its listed optional scopes; it never receives `person.update`, `relationship.manage`, `access.read`, or `access.manage`, and a caregiver revision never becomes owner. | Out-of-set request is denied before data access. | Parameterized tests cover every owner and caregiver scope/action pair and role-transition refusal. |
| Own-Person link becomes a hidden grant | A unique own-Person link requires an active owner assignment and is not consulted by authorization. | Link creation without ownership fails; link alone returns `404` for Person data. | One-to-one constraints, active-owner prerequisite, revocation cleanup, and no-access behavior are tested. |
| Password disclosure or weak verification | Credentials store only a scrypt verifier with `n=32768` (`N=2^15`), `r=8`, `p=1`, `dklen=64`, `maxmem=67_108_864`, about 32 MiB working memory, and random salt of at least 16 bytes. Verification compares derived verifiers in constant time. | Authentication fails without echoing password or verifier detail. | Exact parameter, salt-length, verifier-only, wrong-password, and no-secret-log tests. |
| Stolen or replayed browser session | Opaque server-side session verifier at `OPENCARE_SESSION_DB_PATH`, `HttpOnly` cookie, `Secure` under HTTPS, `SameSite=Lax`, absolute eight-hour expiry, and revocation on logout/credential or Actor changes. Development uses an OS-temp installation namespace; Production Compose supplies ephemeral `/run/opencare` tmpfs with no volume. Custom deployment operators must keep a custom path runtime-only and out of backups. | Expired/revoked/missing session receives `401`; Product DB/source overlap is rejected; no session is restored from backup. | Boundary-time expiry, logout, credential replacement, Actor disablement, cookie attributes, overlap/permission checks, Compose configuration, and post-recovery reauthentication tests. |
| Cross-site mutation or login CSRF | Same-origin validation is mandatory for every state-changing Family Access `POST`, including unauthenticated bootstrap, login, invitation preview, registration, and acceptance. Authenticated unsafe methods additionally require a per-session CSRF token. CSRF material is absent from URLs and logs. | `403` without Person detail and no mutation. | Missing, invalid, cross-origin, and valid same-origin/login-CSRF cases plus authenticated CSRF cases for every protected mutation. |
| Invitation leakage or brute-force acceptance | Generate at least 32 random bytes; show once; persist only SHA-256 hash; use body-only `POST /invite/preview`, `/invite/register`, and `/invite/accept`; consume atomically. Valid caregiver and owner invitation recipients may redeem. Owner invitations require `confirm_full_owner_access: true` and grant the fixed full owner matrix. | Invalid, expired, revoked, or consumed secret has the same generic non-disclosing failure result. | One-time/expiry/revocation/owner-confirmation/recipient-redemption tests and scans of URLs, logs, audit, backup, export, and errors for invitation secrets. |
| Person enumeration via responses | Person routes use the same `404` for missing, inactive, hidden, or guessed targets and their nested resources. An Actor with access to the Person but without a known action scope receives `403`. CSRF and high-risk confirmation failures also use `403`. Lists reveal no hidden names, IDs, memberships, counts, or installation totals. | No response confirms a hidden target or reveals hidden list data. | Response-equivalence tests compare missing with hidden targets; separate tests prove `403` only after Person visibility is established. |
| Sensitive mutation without evidence | Successful credential, access, family, relationship, invitation, own-Person, export, and admin mutations write metadata-only audit in the same transaction. | Audit insert failure rolls back the mutation and returns failure. | Forced audit-write errors prove state rollback and absence of a false success event. |
| Denial path leaks data when audit storage fails | Denials attempt a metadata-only audit but never disclose target state if that audit fails. Operator telemetry carries only a bounded non-secret failure code. | Same privacy-safe `404`/`403` response as the normal denial path. | Forced denial-audit failures preserve the response contract and contain no health content or secrets. |
| Credential, session, or invitation data leaks through export | Person export v2 includes selected-Person record data, relevant family/relationship/consent context, and non-secret relevant assignment history. It excludes credentials, sessions, invitation records/hashes, access-audit records, and unrelated identities. | Export fails closed on unsupported reachable graph; it never silently adds excluded identity state. | Archive-content, manifest, and byte scan tests for all excluded classes and raw secrets. |
| Actor session survives disaster recovery | Session store is separate from Product Core SQLite and is never read, copied, verified, preflighted, or restored by backup/recovery. It has no persistent volume and startup rejects overlap with Product DB/source paths. Offline `backup`, `verify`, `preflight`, and `recover` are installation-operator workflows requiring no Actor session, assignment, or Person impersonation. Durable credentials are restored; sessions are not. | Recovered installation rejects every pre-recovery session and requires a new login. | Backup layout and recovery tests prove no session-store access, durable credential recovery, preserved revocation, and creation of a new post-recovery session. |
| Unsafe migration or rollback changes health data | v5 migration creates access tables/triggers only in one transaction and does not infer data. Recovery restores matching-version bytes without migration, including durable Actor/access state exactly as represented by the selected backup. | Migration failure rolls back to v4; committed v5 has no in-place down migration; later revocations outside the selected snapshot are not preserved. | v4 preservation, injected migration failure, no inferred rows, v5 backup compatibility, selected-backup revoked-state preservation, and v4-release recovery tests. |
| Bootstrap or deactivation bypass | `/api/family-access/v1` has the approved bootstrap, session, self, password, selection, access-management, invitation, and Actor-deactivation routes. Bootstrap requires zero Actors and same-origin validation. A legacy `/access` cookie is never accepted as Actor authentication. Deactivation atomically revokes admin/access state, appends consent revocations, clears own link, and then invalidates sessions. | Bootstrap/deactivation fails without partial durable state; inactive Actor is denied even if session cleanup fails. | Route-contract, actor-list privacy, zero-Actor, bootstrap-atomicity, invitation-route, last-owner/last-admin, deactivation, and cleanup-failure tests. |
| Protected facade or demo/live crossover | `/vault`, every related live vault API, `/workspace`, `/api/product-core/v1`, `/chat`, and `/api/chat` resolve Actor sessions and policy before Person data reaches services. `/demo/health-vault` and reviewer/demo never touch Actor/live state; `/vault`, `/workspace`, and `/chat` never fall back to demo context. | Protected/live surface cannot expose Person data without session/policy; demos remain isolated. | HTTP/browser smoke tests for each protected facade, live vault API, demo/live isolation, and regression tests for demo and PGx routes. |

## Logging and operational limits

Logs and access audits may contain opaque IDs, action/outcome, bounded reason
codes, and timestamps. They must not contain health content, source payloads,
passwords, password verifiers, cookies, session tokens/verifiers, CSRF tokens,
invitation secrets or hashes, request bodies, response bodies, or URL query
strings that could carry secrets. Operators retain responsibility for local
filesystem permissions, TLS termination, device security, and backup custody.

Checksums in portable exports and backups detect modified bytes; they do not
encrypt health data, prove artifact authorship, or substitute for access
control. Backup/verify/preflight/recover remain offline operations and do not
become an HTTP administration surface.

## Out of scope

This design does not add social login, password recovery by email, cloud
identity, multi-tenant tenancy, encryption/key management, remote backups,
medical consent law compliance, diagnosis, treatment guidance, dosage advice,
new AI providers, Phase 3 read-only tools, or a change to the v0.1.0 demo and
frozen PGx surfaces.
