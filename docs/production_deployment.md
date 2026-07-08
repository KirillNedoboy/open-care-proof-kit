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
```

Rules:

- `OPENCARE_SECRET_KEY` must be at least 32 characters;
- `OPENCARE_ACCESS_PASSWORD` should be unique and strong;
- `OPENCARE_LOCAL_VAULT_PATH` must point to a host file you control;
- the mounted vault file stays read-only in the container;
- do not point this path at a committed private data file.

For a safe dry run, you can temporarily use `docs/examples/local-family-vault.template.json`.

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

## Backup Guidance

The local vault JSON is operator-owned host data. In V2C, backup/export guidance means copying that host file, not exporting through the app.

Recommended practice:

- keep the vault JSON outside Git or under an ignored path;
- store at least one offline or encrypted backup copy you control;
- version backups at the host or filesystem level;
- test restore by replacing the mounted host file with a backup copy;
- never edit the mounted file from inside the container.

The container mount is read-only by design. Recovery is done by restoring the host file and restarting the stack if needed.

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
- No database persistence.
- No user accounts.
- No LLM generation in this deployment path.
- No genetics support in this deployment path.

