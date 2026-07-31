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
- [ ] Generate `OPENCARE_SECRET_KEY`, set a strong access password, and review
  TLS/reverse-proxy boundaries where applicable.

## 3. Installation verification

- [ ] Complete constrained source or wheel installation and run `pip check`.
- [ ] Verify `/health`, `/readyz`, `/workspace`, `/chat`, `/openapi.json`, and
  static assets.
- [ ] Verify the password gate in private production mode.

## 4. Synthetic acceptance flow

- [ ] Create a Person and add a manual Medication source.
- [ ] Review each CandidateFact; confirm, correct, or reject it.
- [ ] Verify the canonical record and Timeline, then create a Visit and Questions.
- [ ] Generate and edit a Visit Brief, then export the Person vault.

## 5. Backup verification

- [ ] Create and verify an installation backup; record its operator-controlled
  location.
- [ ] Confirm that backups are plaintext sensitive artifacts and that secrets
  are excluded.

## 6. Recovery drill

- [ ] Stop application access and enter maintenance mode.
- [ ] Use only an absent or empty target; run `preflight`, then `recover`, then
  verify the recovered installation.
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
