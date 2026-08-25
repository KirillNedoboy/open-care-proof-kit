# Production Deployment

OpenCare documents one bounded remote deployment path:

- single-node VPS;
- Docker Compose;
- Caddy reverse proxy with HTTPS/TLS;
- Product Core SQLite and immutable source storage;
- the legacy private password gate for non-Actor surfaces;
- local Actor sessions and explicit Person assignments for live Product Core data.

This is a controlled self-hosted private-alpha path, not a production-readiness
claim or clinical software. It does not provide diagnosis, treatment
recommendation, dosage guidance, medication selection advice, start/stop
medication advice, uploads, OCR, or Phase 3 ingest.

## Supported Production Path

This document covers only:

- `docker-compose.prod.yml`;
- `deploy/Caddyfile.example`;
- `deploy/env.production.example`;
- `scripts/smoke_check.py`.

The default Compose stack is Product Core-only. The legacy synthetic/reference
vault is an explicit optional override: add
`-f deploy/docker-compose.legacy-vault.yml` and set
`OPENCARE_LOCAL_VAULT_PATH` only when `/demo/health-vault` compatibility is
needed. It is never a Product Core dependency.

Advanced operators can adapt the container to other reverse proxies or orchestrators later, but that is outside the validated V2C path.

## Operator Prerequisites

- a Linux VPS you control;
- Docker Engine with Compose plugin installed;
- a public DNS record pointed at the VPS;
- ports `80` and `443` open to the VPS for Caddy TLS;
- strong values for `OPENCARE_SECRET_KEY`, `OPENCARE_ACCESS_PASSWORD`, and the
  32+ character `OPENCARE_BOOTSTRAP_SECRET`.

Do not expose the app container directly on the public internet. In V2C, the documented path is Caddy on `80/443` in front of the app container.

## Files To Prepare

Copy the example files into uncommitted operator files:

```powershell
Copy-Item deploy/env.production.example deploy/env.production
Copy-Item deploy/Caddyfile.example deploy/Caddyfile
```

Then edit:

- `deploy/env.production`
- `deploy/Caddyfile`

The repo ignores those operator-specific files so secrets and real domains do not get committed by default.

## Environment File

`deploy/env.production` should define:

```txt
OPENCARE_SECRET_KEY=<32+ character secret>
OPENCARE_ACCESS_PASSWORD=<strong private password>
OPENCARE_BOOTSTRAP_SECRET=<32+ character operator bootstrap secret>
OPENCARE_PUBLIC_REGISTRATION=false
OPENCARE_PRODUCT_DATA_DIR=./private/opencare-product-core
OPENCARE_BACKUP_DIR=./private/opencare-backups
```

Rules:

- `OPENCARE_SECRET_KEY` must be at least 32 characters;
- `OPENCARE_ACCESS_PASSWORD` should be unique and strong;
- `OPENCARE_BOOTSTRAP_SECRET` is checked constant-time during the one-time
  production bootstrap and is never stored, audited, or logged;
- `OPENCARE_PRODUCT_DATA_DIR` and `OPENCARE_BACKUP_DIR` are required host directories;
- do not point this path at a committed private data file.

Backups contain sensitive plaintext Product Core data; protect them as private
operator artifacts. This is a documented controlled self-hosted path, not a
production-readiness or clinical-readiness claim.

## Product Core host storage

Production Compose binds two operator-controlled host directories:

| Host variable | Container path | Contents |
|---|---|---|
| `OPENCARE_PRODUCT_DATA_DIR` | `/var/lib/opencare/product-core` | `database.sqlite3` and immutable `sources/` payloads |
| `OPENCARE_BACKUP_DIR` | `/var/backups/opencare` | operator-created installation backups |

Actor sessions are not a third persistent directory. Compose sets
`OPENCARE_SESSION_DB_PATH=/run/opencare/sessions.sqlite3` and mounts
`/run/opencare` as mode `0700` tmpfs. Do not add a volume for that path. A
container/runtime recreation intentionally removes sessions and requires every
Actor to log in again.

The application receives only the fixed container paths through
`OPENCARE_PRODUCT_DB_PATH` and `OPENCARE_SOURCE_DIR`; it does not receive the
host-path variables. `OPENCARE_PRODUCT_DATA_DIR=./private/opencare-product-core`
and `OPENCARE_BACKUP_DIR=./private/opencare-backups` resolve from the Compose
project directory containing `docker-compose.prod.yml`, normally the repository
root. They do not resolve relative to `deploy/env.production`.

Prepare both host directories before starting the stack. On a Linux VPS:

```bash
mkdir -p ./private/opencare-product-core ./private/opencare-backups
chmod 700 ./private/opencare-product-core ./private/opencare-backups
docker compose --env-file deploy/env.production -f docker-compose.prod.yml run --rm --no-deps --entrypoint sh opencare -c 'id -u; id -g'
sudo chown -R <container-uid>:<container-gid> ./private/opencare-product-core ./private/opencare-backups
```

The Dockerfile has no `USER` instruction, so the operator must use the reported
UID/GID rather than assuming ownership values. Keep both directories writable by
that UID/GID and restrict them to the operator; do not make them world-writable.

## Caddy File

Replace the placeholder domain in `deploy/Caddyfile`:

```txt
opencare.example.com
```

with your real public domain after DNS is ready.

The example Caddy file:

- terminates TLS at the proxy;
- forwards requests to `opencare:8000`;
- keeps app-level TLS out of scope for this MVP.

## Compose Stack

The production stack:

- runs the existing app image/build path;
- sets `OPENCARE_ENV=production`;
- sets `OPENCARE_DEMO_MODE=false`;
- sets `OPENCARE_VAULT_SOURCE=demo` only for legacy/demo compatibility;
- mounts persistent Product Core state at `/var/lib/opencare/product-core`;
- mounts operator backups at `/var/backups/opencare`;
- keeps the server-side session database on non-persistent `/run/opencare` tmpfs;
- keeps the app container off public ports;
- publishes only Caddy on `80` and `443`;
- includes a container healthcheck and restart policy.

Bring the stack up with your operator env file:

```powershell
docker compose --env-file deploy/env.production -f docker-compose.prod.yml up -d --build
```

For the optional legacy vault override:

```powershell
docker compose --env-file deploy/env.production -f docker-compose.prod.yml -f deploy/docker-compose.legacy-vault.yml up -d --build
```

Stop it:

```powershell
docker compose --env-file deploy/env.production -f docker-compose.prod.yml down
```

Recreating the `opencare` container preserves People, durable Actors and
credential verifiers, Families, relationships, consent, assignments, access
audits, Sources and immutable
payloads, CandidateFacts and review state, canonical medications, Timeline
Events, Visits, Visit Questions, persisted Visit Brief revisions, and Product
Core audit rows because they remain in `OPENCARE_PRODUCT_DATA_DIR` on the host.
It deliberately does not preserve Actor sessions.

## Smoke Check

After deployment, verify health and vault access:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_check.py --base-url https://opencare.example.com --password "<your access password>"
```

The smoke check:

- requires `/healthz` to return `200`;
- requires `/readyz` to return `200`;
- requires `/vault` to return `401` until an Actor session exists;
- detects the legacy `/access` redirect if a pre-Phase-2-compatible server uses
  it for `/vault`;
- on the Phase 2 runtime, confirms `/vault` requires an Actor session and
  `/login` is available; the optional legacy password is not Actor authentication;
- exits non-zero on failure;
- never prints the password value.

## Health And Access Model

Public endpoints in the documented production path:

- `/health`
- `/healthz`
- `/readyz`

Protected behavior in the documented production path:

- `/vault`, `/workspace`, `/family-access`, and `/chat` require a valid Actor
  session and Person policy where Person data is involved;
- `/access` serves the password form;
- a legacy gate cookie grants no Actor identity or Person access;
- `/login` is the normal username/password entry flow; `/bootstrap` is the
  one-time operator setup flow; `/invite` is the secondary family-sharing flow;
- legacy non-Actor routes stay behind the private gate in private production;
  Actor entry/live routes enforce their own session boundary directly so a
  missing Actor session redirects browser HTML GETs safely to `/login`, while
  API requests remain JSON `401` responses.

## Product Core backup and recovery

The Product Core backup artifact is plaintext sensitive health data. Create it
inside the persistent backup mount, then verify only that artifact:

```powershell
docker compose --env-file deploy/env.production -f docker-compose.prod.yml exec opencare `
  python -m app.product_core.backup_cli backup `
  --database /var/lib/opencare/product-core/database.sqlite3 `
  --source-dir /var/lib/opencare/product-core/sources `
  --destination /var/backups/opencare/<new-backup-directory>

docker compose --env-file deploy/env.production -f docker-compose.prod.yml exec opencare `
  python -m app.product_core.backup_cli verify `
  --backup /var/backups/opencare/<new-backup-directory>
```

Backups contain schema v9 durable Product Core and identity/access state, including credential
verifiers and invitation hashes. They exclude plaintext passwords, invitation
codes, `.env`, `OPENCARE_SECRET_KEY`, provider credentials, cookies, sessions,
TLS material, deployment configuration, and generated reports. Store the
mounted reference vault JSON separately; it is not Product Core state.

Recovery is an offline maintenance operation. Stop application access first;
the CLI cannot prove that the service is stopped. Do not run recovery against
the active mounted Product Core directory. It requires an absent or real empty
target and does not support populated-target overwrite or merge. This deployment
path does not define an in-place Compose recovery command.
Recovery restores durable credentials and revocations but no sessions. Before
reopening HTTP access, require new logins and review active administrators,
owners, caregivers, and outstanding invitations in the restored snapshot.

## Security Checklist

- Use a strong `OPENCARE_SECRET_KEY`.
- Use a strong `OPENCARE_ACCESS_PASSWORD`.
- Use a unique 32+ character `OPENCARE_BOOTSTRAP_SECRET`; clear it after the
  first bootstrap attempt.
- Use real HTTPS/TLS through Caddy.
- Open only the firewall ports you need, typically `80` and `443`.
- Do not expose the app container directly without the reverse proxy.
- Do not commit private vault files.
- Keep optional legacy vault mounts read-only.
- Keep `/run/opencare` ephemeral and never copy its session database into a backup.
- Keep `deploy/env.production` and `deploy/Caddyfile` uncommitted.

## Boundaries

- Controlled self-hosted private alpha only.
- Not clinical software.
- No medical advice.
- No clinical decision support.
- No uploads.
- Product Core persistence depends on the two required host bind mounts.
- Local Actor username/password accounts only. Public self-registration is
  disabled by default and, when explicitly enabled after bootstrap, is a
  controlled self-hosted capability rather than public SaaS identity. There is
  no email verification or self-service account recovery.
- No Phase 3 ingest, OCR, cloud synchronization, or deployment automation.

