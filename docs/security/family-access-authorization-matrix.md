# Family access authorization matrix

This is the implemented versioned Family Access policy for the live Workspace,
Product Core HTTP API, live vault, chat, and the P3 Genetics Workspace.
`family-access-v1`, `family-access-v2`, and `family-access-v3` are frozen
generations. The server resolves the Actor, active Person, and resource
ownership; a client-supplied Person or resource ID never grants access.
Installation administration, Family membership, relationships, and an
own-Person link are not authorization inputs.

The synthetic `/demo/health-vault` and reviewer routes remain outside this
live-data policy. Offline `backup`, `verify`, `preflight`, and `recover` are
installation-operator commands and require no Actor session or Person
impersonation.

## Policy generations

The scope model is versioned (see `app/family_access/policy.py`):

- `family-access-v1` — pre-P1 scope sets, frozen verbatim.
- `family-access-v2` — P1/P2 scope sets, frozen; v1 plus
  `condition.read`, `condition.write`, `lab.read`, and `lab.write`.
- `family-access-v3` — current legacy generation; v2 plus
  `document.read` and `document.write` with the owner/base/optional split
  below. Genetics authority is deliberately separate from every generation.
An assignment's generation is inferred purely from its stored `scopes_json`
(any generation-only scope string identifies that generation) and validated
against that generation's frozen sets; `scope_generation` is derived metadata
only. Existing delegated consent never automatically gains new access.
Owner/caregiver upgrades are explicit, audited assignment updates recording
the exact selected scopes. A role name, policy version, `source.read`, or
fact-family write scope never silently expands document access.

## Fixed role scopes

An owner always receives the complete owner set for its generation. A caregiver
always receives the base set and may receive only the listed optional scopes.
Partial owner assignments and caregiver-to-owner scope revisions are invalid
durable state.

| Scope | Owner | Caregiver base | Caregiver optional | Protected action |
|---|:---:|:---:|:---:|---|
| `person.read` | Yes | Yes | — | Read an accessible Person and include them in filtered lists. |
| `person.update` | Yes | No | No | Change an accessible Person profile. |
| `source.read` | Yes | Yes | — | Resolve source metadata needed by an authorized record operation. |
| `source.write` | Yes | No | Yes | Register a manual or plain-text source. |
| `document.read` | Yes (v3 only) | Yes (v3 only) | — | Read authorized document metadata and persisted extracted text; never raw bytes. |
| `document.write` | Yes (v3 only) | No | Yes (v3 only) | Upload an authenticated Person-scoped PDF/TXT document. |
| `candidate.read` | Yes | Yes | — | Read or list candidate facts. |
| `candidate.review` | Yes | No | Yes | Create, correct, reject, unsupported, or review a candidate. |
| `medication.read` | Yes | Yes | — | Read confirmed medication records. |
| `medication.write` | Yes | No | Yes | Confirm a medication candidate into canonical state. |
| `condition.read` | Yes | Yes (v2 only) | — | Read recorded condition candidates and canonical records. |
| `condition.write` | Yes | No | Yes (v2 only) | Confirm a condition candidate into canonical state. |
| `lab.read` | Yes | Yes (v2 only) | — | Read lab candidates and canonical records. |
| `lab.write` | Yes | No | Yes (v2 only) | Confirm a lab candidate into canonical state. |
| `timeline.read` | Yes | Yes | — | Read Person timeline events. |
| `visit.read` | Yes | Yes | — | Read Visits and Visit Questions. |
| `visit.write` | Yes | No | Yes | Create or update Visits and Questions. |
| `brief.read` | Yes | Yes | — | Read Brief state, revisions, and eligible evidence. |
| `brief.write` | Yes | No | Yes | Initialize, generate, edit, validate, or restore a Brief. |
| `brief.export` | Yes | No | Yes | Export the current Visit Brief. |
| `vault.export` | Yes | No | Yes | Create deterministic Person export (format v3). |
| `relationship.read` | Yes | Yes | — | Read visible Family context for accessible People. |
| `relationship.manage` | Yes | No | No | Create/end memberships and relationships or archive a visible Family. |
| `access.read` | Yes | No | No | Read assignment, consent, and access-audit history for a Person. |
| `access.manage` | Yes | No | No | Grant, revise, revoke, invite, or manage Person access (including generation upgrades). |
| `chat.use` | Yes | Yes | — | Ask a question using server-built context for the active Person. |

Where an operation needs more than one scope, every listed scope is required.
Confirmation, for example, requires both `candidate.review` and the
fact-type write scope (`medication.write`, `condition.write`, or `lab.write`
matched to the candidate's fact type).
## Document metadata versus content


`source.read` authorizes source metadata needed by an already authorized
record operation; it is not a content oracle. Document metadata (safe filename,
media type, size, hash, upload time, page count, and extraction status) and
persisted extracted text are distinct surfaces. The latter requires
`document.read`, which is checked dynamically for document detail and
document-backed candidate operations. D1 exposes no raw-document download.

Creating or reviewing a document-backed candidate requires `document.read` plus
the applicable fact-family review/write scopes. Ingestion itself creates no
candidate and no canonical record.

## Genetics-specific authorization

P3 stores genetics consent separately in `genetic_access_grants`. The explicit
capabilities are `genetics.read`, `genetics.write`, `genetics.research`,
`genetics.compare`, and `genetics.export`. Existing v1/v2/v3 assignments never
inherit these capabilities. Consent is confirmed per Person and actor, grants
are checked before retrieval, and revocation blocks all subsequent genetics
reads, research, comparison, and export. A caregiver with ordinary health or
document access therefore cannot discover that a Person has a genetics dataset.

Family comparison requires active `genetics.compare` grants for both Persons.
Alice's grant does not authorize Bob or Child, and a failed hidden-Person check
returns the same non-disclosing not-found result regardless of whether that
Person has genetic data. Research packets contain only explicitly selected
reviewed findings and canonical records; raw genotype bytes never enter a
provider context or receipt.


## Access-management rules

- Owner grants and owner invitations require
  `confirm_full_owner_access: true` and always use the complete owner set.
- Caregivers cannot create, upgrade, revise, or revoke owners and cannot manage
  any assignment or invitation.
- D1 document scope upgrades are explicit owner/caregiver assignment updates,
  audited with the exact selected scopes. Existing v1/v2 assignments remain
  unchanged; no silent expansion occurs.
- Person creation is a bounded private-alpha exception: any authenticated,
  active Actor may submit `confirm_owner_assignment: true`. One transaction
  creates the Person, self-granted owner consent, complete owner assignment,
  optional valid own-Person link, and access audit. Installation-admin status
  is neither required nor sufficient.
- Revoking an assignment also clears its active own-Person link. The link never
  substitutes for an assignment.
- The final active owner of a Person cannot be removed. The final active
  installation administrator cannot be deactivated. These are independent
  invariants.

## HTTP privacy contract

| Situation | Status |
|---|---:|
| Missing, expired, revoked, or otherwise invalid Actor session | `401` |
| Invalid same-origin or CSRF proof | `403` |
| Actor can access the Person but lacks the known action scope | `403` |
| Hidden, inactive, or guessed Person, or a nested resource owned by one | `404` |
| Invalid, expired, revoked, or replayed invitation | One generic response |

List filtering happens before serialization. Responses contain no hidden
Person names or IDs, Family members, hidden counts, or installation totals from
which hidden counts could be derived.

Sensitive successful mutations and their access audits share one transaction;
an audit failure rolls back the mutation. A denial-audit failure never changes
the decision: the original privacy-safe denial is returned and only a
non-sensitive operational error is recorded.
