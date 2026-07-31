# Production Deployment

OpenCare Proof Kit V2C documents one validated remote deployment path only:

- single-node VPS;
- Docker Compose;
- Caddy reverse proxy with HTTPS/TLS;
- read-only mounted local vault JSON file;
- private password gate for non-health routes.

This is a self-hosted read-only MVP. It is not clinical software. It does not provide diagnosis, treatment recommendation, dosage guidance, medication selection advice, start/stop medication advice, uploads, LLM generation, or genetics support in this phase.

## Supported Production Path

This document covers only:

- `docker-compose.prod.yml`;
- `deploy/Caddyfile.example`;
- `deploy/env.production.example`;
- `scripts/smoke_check.py`.

Advanced operators can adapt the container to other reverse proxies or orchestrators later, but that is outside the validated V2C path.

## Operator Prerequisites

- a Linux VPS you control;
- Docker Engine with Compose plugin installed;
- a public DNS record pointed at the VPS;
- ports `80` and `443` open to the VPS for Caddy TLS;
- a local vault JSON file you control on the VPS host;
- strong values for `OPENCARE_SECRET_KEY` and `OPENCARE_ACCESS_PASSWORD`.

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
OPENCARE_LOCAL_VAULT_PATH=/absolute/or/repo-relative/path/to/local-family-vault.json
OPENCARE_PRODUCT_DATA_DIR=./private/opencare-product-core
OPENCARE_BACKUP_DIR=./private/opencare-backups
```

Rules:

- `OPENCARE_SECRET_KEY` must be at least 32 characters;
- `OPENCARE_ACCESS_PASSWORD` should be unique and strong;
- `OPENCARE_LOCAL_VAULT_PATH` must point to a host file you control;
- the mounted vault file stays read-only in the container;
- `OPENCARE_PRODUCT_DATA_DIR` and `OPENCARE_BACKUP_DIR` are required host directories;
- do not point this path at a committed private data file.

For a safe dry run, you can temporarily use `docs/examples/local-family-vault.template.json`.

## Product Core host storage

Production Compose binds two operator-controlled host directories:

| Host variable | Container path | Contents |
|---|---|---|
| `OPENCARE_PRODUCT_DATA_DIR` | `/var/lib/opencare/product-core` | `database.sqlite3` and immutable `sources/` payloads |
| `OPENCARE_BACKUP_DIR` | `/var/backups/opencare` | operator-created installation backups |

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
- sets `OPENCARE_VAULT_SOURCE=local_file`;
- sets `OPENCARE_VAULT_FILE=/vault/local-family-vault.json`;
- mounts the host vault file read-only;
- mounts persistent Product Core state at `/var/lib/opencare/product-core`;
- mounts operator backups at `/var/backups/opencare`;
- keeps the app container off public ports;
- publishes only Caddy on `80` and `443`;
- includes a container healthcheck and restart policy.

Bring the stack up with your operator env file:

```powershell
docker compose --env-file deploy/env.production -f docker-compose.prod.yml up -d --build
```

Stop it:

```powershell
docker compose --env-file deploy/env.production -f docker-compose.prod.yml down
```

Recreating the `opencare` container preserves People, Sources and immutable
payloads, CandidateFacts and review state, canonical medications, Timeline
Events, Visits, Visit Questions, persisted Visit Brief revisions, and Product
Core audit rows because they remain in `OPENCARE_PRODUCT_DATA_DIR` on the host.

## Smoke Check

After deployment, verify health and vault access:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_check.py --base-url https://opencare.example.com --password "<your access password>"
```

The smoke check:

- requires `/healthz` to return `200`;
- requires `/readyz` to return `200`;
- accepts `/vault` returning `200` in public/demo mode;
- detects `/vault` redirecting to `/access` in private mode;
- when a password is supplied, verifies the `/access` login flow and unlocked `/vault`;
- exits non-zero on failure;
- never prints the password value.

## Health And Access Model

Public endpoints in the documented production path:

- `/health`
- `/healthz`
- `/readyz`

Protected behavior in the documented production path:

- `/vault` requires the private gate;
- `/access` serves the password form;
- successful login sets the signed cookie;
- non-health routes stay behind the private gate.

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

Backups exclude `.env`, passwords, `OPENCARE_SECRET_KEY`, provider credentials,
cookies, sessions, TLS material, deployment configuration, and generated
reports. Store the mounted local vault JSON separately; it is not Product Core
state.

Recovery is an offline maintenance operation. Stop application access first;
the CLI cannot prove that the service is stopped. Do not run recovery against
the active mounted Product Core directory. It requires an absent or real empty
target and does not support populated-target overwrite or merge. This deployment
path does not define an in-place Compose recovery command.

## Security Checklist

- Use a strong `OPENCARE_SECRET_KEY`.
- Use a strong `OPENCARE_ACCESS_PASSWORD`.
- Use real HTTPS/TLS through Caddy.
- Open only the firewall ports you need, typically `80` and `443`.
- Do not expose the app container directly without the reverse proxy.
- Do not commit private vault files.
- Keep the vault mount read-only.
- Keep `deploy/env.production` and `deploy/Caddyfile` uncommitted.

## Boundaries

- Self-hosted read-only MVP only.
- Not clinical software.
- No medical advice.
- No clinical decision support.
- No uploads.
- Product Core persistence depends on the two required host bind mounts.
- No user accounts.
- No LLM generation in this deployment path.
- No genetics support in this deployment path.

