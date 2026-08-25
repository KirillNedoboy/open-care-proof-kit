# Controlled private-alpha operator checklist

## 1. Eligibility

- [ ] Confirm this is a private controlled installation, not public exposure
  without a reviewed reverse proxy and password gate.
- [ ] Confirm no user expects clinical advice, diagnosis, or treatment guidance.
- [ ] Confirm authority and consent to store test data; prefer synthetic data
  for first acceptance.

## 2. Host preparation

- [ ] Choose a Python 3.12 source/wheel path or the production Docker path.
- [ ] Create dedicated Product Core and backup storage with restrictive
  filesystem permissions, separate from secrets and configuration.
- [ ] Keep `OPENCARE_SESSION_DB_PATH` in runtime-only storage. In production
  Compose it is `/run/opencare/sessions.sqlite3` on tmpfs; do not add a session
  backup volume.
- [ ] Generate `OPENCARE_SECRET_KEY`, set a strong access password, and review
  TLS/reverse-proxy boundaries where applicable.

## 3. Installation verification

- [ ] Complete constrained source or wheel installation and run `pip check`.
- [ ] Verify `/health`, `/readyz`, `/login`, `/bootstrap`, `/workspace`,
  `/family-access`, `/chat`, `/openapi.json`, and static assets.
- [ ] Verify the password gate in private production mode.
- [ ] Bootstrap exactly one first Actor, record who holds installation-admin
  responsibility, and confirm that administrator status alone reveals no
  Person data.
- [ ] Keep `OPENCARE_PUBLIC_REGISTRATION=false` unless controlled public account
  creation is explicitly intended; if enabled, verify bootstrap completed first.
- [ ] Verify normal username/password login works without an invitation and that
  each self-registered account receives only its own Person and owner access.

## 4. Synthetic acceptance flow

For G2 acceptance, review the ten named trust eval fixtures and record their
individual outcomes. Treat them as local deterministic checks only; do not
interpret passing registration/evaluation fixtures as evidence that an external
provider, deployment, or ecosystem integration is available.

- [ ] Create a Person only with the explicit owner-assignment confirmation;
  verify the creating Actor becomes that Person's owner atomically.
- [ ] Create a caregiver invitation through `/invite`, transfer its code out of
  band, and confirm the code never appears in a URL or log.
- [ ] Confirm invitations remain the explicit family-sharing path and preserve
  existing-account acceptance, owner confirmation, and caregiver scopes.
- [ ] Exercise Person switching and confirm inaccessible People, Family members,
  and installation totals are absent rather than merely disabled in the UI.
- [ ] Add a manual Medication source.
- [ ] Review each CandidateFact; confirm, correct, or reject it.
- [ ] Verify the canonical record and Timeline, then create a Visit and Questions.
- [ ] Generate and edit a Visit Brief, then export the Person vault.

## 5. Backup verification

- [ ] Create and verify an installation backup; record its operator-controlled
  location.
- [ ] Confirm that backups are plaintext sensitive artifacts and that secrets
  and sessions are excluded. Treat durable credential verifiers and invitation
  hashes inside schema v5 as sensitive installation state.

## 6. Recovery drill

- [ ] Stop application access and enter maintenance mode.
- [ ] Use only an absent or empty target; run `preflight`, then `recover`, then
  verify the recovered installation.
- [ ] Confirm no old Actor session works after recovery, then authenticate with
  a restored credential to create a new session. Review active administrators,
  owners, caregivers, revocations, and outstanding invitations before reopening.
- [ ] Never overwrite active or populated state, and never treat recovery as
  import or merge.

## 7. Private-alpha operation

- [ ] Restrict users, maintain manual backups, and report defects without
  medical data, secrets, exports, or backups.
- [ ] Do not upload exported artifacts to issue trackers or rely on OpenCare for
  diagnosis or treatment decisions.

## 8. Exit criteria

Stop the alpha after unexplained data loss, provenance mismatch, failed backup
verification, unexpected external data transmission, authentication bypass,
corrupted source payload, recovery failure, or unsupported clinical use.
