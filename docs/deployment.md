# Deployment

Current boundary: Product Core SQLite, immutable sources, and backups are the
default self-hosted persistence. Sessions live on `/run/opencare` tmpfs in
production. The legacy local-file vault is optional compatibility only; enable
it with `deploy/docker-compose.legacy-vault.yml`, never as a Product Core
dependency. Production requires a 32+ character `OPENCARE_BOOTSTRAP_SECRET` at
startup; the value is checked during bootstrap and never persisted. Backups are sensitive
plaintext operator artifacts; this path is controlled self-hosting, not a
production-readiness or clinical-readiness claim.

OpenCare Proof Kit R7 is a self-hosted personal/family health workspace with a
bounded Docker distribution. The supported remote path is one Linux host with
Docker Compose, Caddy, and local persistent Product Core storage.

This is not clinical software. It does not provide diagnosis, treatment
recommendation, dosage guidance, medication selection advice, or start/stop
medication advice. D1/D2 supports authenticated PDF/TXT document ingest with
bounded embedded-text extraction; P3 supports bounded local consumer-genotype
import and selective research projections. OCR, raw-genome provider disclosure,
VCF/FASTQ/BAM/WGS pipelines, and clinical genetics authority remain out of
scope.

This document covers:

- local run and local demo mode;
- private local-file mode;
- Docker development/demo usage;
- the handoff to the single documented VPS production path.

For the full remote deployment flow, use [docs/production_deployment.md](production_deployment.md).

## Runtime Modes

- `OPENCARE_ENV=development` keeps local startup easy and leaves the current demo/reviewer routes public.
- `OPENCARE_ENV=production` enables production validation.
- `OPENCARE_DEMO_MODE=true` keeps the current demo/reviewer routes public.
- `OPENCARE_DEMO_MODE=false` enables the minimal private access gate for non-health routes.
- `OPENCARE_VAULT_SOURCE=demo` renders the shipped synthetic vault.
- `OPENCARE_VAULT_SOURCE=local_file` renders an operator-mounted local vault JSON file through `/vault`.

## Vault Sources

### Demo source

Default:

```txt
OPENCARE_VAULT_SOURCE=demo
```

Routes:

- `/demo/health-vault` stays the reviewer/demo surface with trace graph and committed trust flags.
- `/vault` also works and renders the active runtime source, which is the synthetic demo vault in this mode.

### Local file source

Local-file mode is read-only. It is not uploads, not persistence, and not user accounts.

Required:

```txt
OPENCARE_VAULT_SOURCE=local_file
OPENCARE_VAULT_FILE=/vault/local-family-vault.json
```

Rules:

- the file must exist;
- the file must be readable;
- the file must validate against the Health/Family Vault schema;
- production use requires private mode protection;
- the UI shows only the mounted file basename, not the full path.

## Required Production Environment Variables

```txt
OPENCARE_ENV=production
OPENCARE_DEMO_MODE=true|false
OPENCARE_SECRET_KEY=<at least 32 characters>
OPENCARE_VAULT_SOURCE=demo|local_file
```

Additional requirement for private production mode:

```txt
OPENCARE_ACCESS_PASSWORD=<required when OPENCARE_DEMO_MODE=false>
```

Additional requirement for local-file mode:

```txt
OPENCARE_VAULT_FILE=/vault/local-family-vault.json
```

Optional path overrides:

```txt
OPENCARE_DATA_DIR=data
OPENCARE_REPORTS_DIR=reports
OPENCARE_ALLOW_CLOUD_LLM=false
OPENCARE_AGENT_MODE=demo
OPENCARE_AGENT_ALLOW_EXTERNAL_LLM=false
```

Compose passes through the supported R6 operator provider settings for
Responses, OpenRouter, and Ollama. AlphaGenome remains paused and is not
productized or passed through by the R7 deployment; see
[`deploy/env.production.example`](../deploy/env.production.example).

Do not bake secrets into the image. Set them through the host environment, a local `.env` file that stays uncommitted, or your deployment system's secret store.
Do not commit private health data. Keep local vault files outside Git or in ignored paths such as `private/` or `vault.local.json`.

## Local Run

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -c constraints/python312.txt -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Health checks:

```txt
http://127.0.0.1:8000/health
http://127.0.0.1:8000/healthz
http://127.0.0.1:8000/readyz
```

Current app routes:

```txt
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo
http://127.0.0.1:8000/demo/health-vault
http://127.0.0.1:8000/vault
http://127.0.0.1:8000/access
```

Example local-file run:

```powershell
$Env:OPENCARE_ENV="production"
$Env:OPENCARE_DEMO_MODE="false"
$Env:OPENCARE_SECRET_KEY="replace-with-a-32-character-local-test-secret"
$Env:OPENCARE_ACCESS_PASSWORD="replace-with-a-local-test-password"
$Env:OPENCARE_VAULT_SOURCE="local_file"
$Env:OPENCARE_VAULT_FILE="C:\vault\local-family-vault.json"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use [docs/examples/local-family-vault.template.json](examples/local-family-vault.template.json) as a schema-safe starting point. It is synthetic/template-only and must not be replaced with committed private data.

## Docker Run

Build:

```powershell
docker build -t opencare-proof-kit:local .
```

Development/demo-style run:

```powershell
docker run --rm -p 8000:8000 `
  -e OPENCARE_ENV=development `
  -e OPENCARE_DEMO_MODE=true `
  opencare-proof-kit:local
```

Private production-style run:

```powershell
docker run --rm -p 8000:8000 `
  -e OPENCARE_ENV=production `
  -e OPENCARE_DEMO_MODE=false `
  -e OPENCARE_SECRET_KEY=replace-with-a-32-character-secret `
  -e OPENCARE_ACCESS_PASSWORD=replace-with-a-private-password `
  -e OPENCARE_VAULT_SOURCE=local_file `
  -e OPENCARE_VAULT_FILE=/vault/local-family-vault.json `
  -v C:\path\to\local-family-vault.json:/vault/local-family-vault.json:ro `
  opencare-proof-kit:local
```

## Docker Compose

Use `.env.example` as a template and keep your real `.env` uncommitted.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Stop:

```powershell
docker compose down
```

The development compose service exposes port `8000`, mounts `./reports` to
`/app/reports`, and stores Product Core SQLite/source data in the named
`opencare_product_data` volume at `/var/lib/opencare/product-core`. Production
Compose publishes only Caddy on `80/443`; the app port is internal to the
Compose networks.

For local-file mode, set:

```txt
OPENCARE_VAULT_SOURCE=local_file
OPENCARE_VAULT_FILE=/vault/local-family-vault.json
```

Then add a read-only bind mount such as:

```yaml
volumes:
  - ./reports:/app/reports
  - ./docs/examples/local-family-vault.template.json:/vault/local-family-vault.json:ro
```

For real private data, replace the example file with your own local file in an ignored host path. Do not commit it.

## Single-VPS Production Path

The documented supported remote deployment path in R7 is:

- one VPS;
- `docker-compose.prod.yml`;
- Caddy reverse proxy on `80/443`;
- TLS at the proxy;
- app container on an internal compose network;
- `OPENCARE_DEMO_MODE=false`;
- `OPENCARE_VAULT_SOURCE=demo` by default, with the legacy local-file vault as
  an explicit override;
- explicit production bind mounts for Product Core SQLite, immutable sources, and
  operator backup artifacts.
- D1/D2 PDF/TXT ingest and P3 consumer-genotype import remain available through
  the authenticated Product Core workspace.

Use [docs/production_deployment.md](production_deployment.md) for the complete operator flow. That document includes:

- `deploy/env.production.example`;
- `deploy/Caddyfile.example`;
- DNS/firewall expectations;
- the `scripts/smoke_check.py` command;
- Product Core host storage and backup guidance;
- the production security checklist.

Do not expose the app container directly without the reverse proxy.

## Private Access Gate

When `OPENCARE_ENV=production` and `OPENCARE_DEMO_MODE=false`:

- `/health`, `/healthz`, and `/readyz` stay public;
- `/access` serves the password form;
- `/vault` requires a valid Actor session and Person scope;
- `/demo/health-vault` stays public in demo mode for reviewer/demo compatibility;
- other non-health routes require the configured access password when they are
  outside the Actor session boundary;
- successful login sets a signed `HttpOnly` cookie;
- this is a minimal outer access gate; Actor username/password accounts remain
  the normal application authentication system.

## Readiness Model

`/readyz` verifies the current configuration and the local assets required by the shipped app:

- demo patient JSON;
- demo family vault JSON;
- reviewer quickstart markdown;
- committed vault manifest;
- template and static directories.

If `OPENCARE_VAULT_SOURCE=local_file`, readiness also checks that the configured local vault file path exists.

When the Product Core runtime is initialized, readiness also performs a local
SQLite integrity/schema check and confirms that the configured immutable Source
directory is an accessible directory. It makes no provider or other network
calls and returns only a generic storage failure reason; host paths are not
included in that response.

If any of these are missing, readiness fails closed.

## Security Boundaries

- Self-hosted MVP only.
- Synthetic/demo-only data in the shipped repo.
- Operator-mounted local file mode is read-only and private-by-operator, not a sharing or upload feature.
- The documented remote production path is Caddy plus Docker Compose on one VPS.
- TLS is strongly recommended for any remote deployment and handled at the reverse proxy.
- Bounded local consumer-genotype import and selective Genetics Research are
  supported; raw genome bytes never enter provider context.
- Authenticated PDF/TXT document upload is supported within D1/D2 limits; OCR
  and image interpretation are not.
- No medical advice.
- No clinical decision support.
- Local username/password Actor accounts are available after operator bootstrap.
  Public self-registration is disabled by default and can be enabled only as a
  controlled self-hosted capability with `OPENCARE_PUBLIC_REGISTRATION=true`;
  this is not public SaaS readiness.
- Product Core persistence is available only through the required production host mounts.
- No secrets committed to source control.

For broader product and safety context, also read [README.md](../README.md) and [privacy_safety_threat_model.md](privacy_safety_threat_model.md).

## Smoke Check

Use the standard-library smoke-check script after local or remote deployment:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_check.py --base-url http://127.0.0.1:8000
.\.venv\Scripts\python.exe scripts/smoke_check.py --base-url https://opencare.example.com --password "<your access password>"
```

The script checks:

- `/healthz`;
- `/readyz`;
- `/vault` public behavior in demo/public mode;
- `/vault` private redirect behavior;
- `/access` login flow and unlocked `/vault` when a password is provided.
