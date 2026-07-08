# Deployment

OpenCare Proof Kit V2B is a self-hosted read-only MVP for a private personal/family medical workspace.

This is not clinical software. It does not provide diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice. It does not support real genetics, raw genotype, VCF, FASTQ, BAM, or WGS uploads in this phase.

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
```

Do not bake secrets into the image. Set them through the host environment, a local `.env` file that stays uncommitted, or your deployment system's secret store.
Do not commit private health data. Keep local vault files outside Git or in ignored paths such as `private/` or `vault.local.json`.

## Local Run

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
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

The compose service exposes port `8000` and mounts `./reports` to `/app/reports`.

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

## Private Access Gate

When `OPENCARE_ENV=production` and `OPENCARE_DEMO_MODE=false`:

- `/health`, `/healthz`, and `/readyz` stay public;
- `/access` serves the password form;
- `/vault` requires the configured access password;
- `/demo/health-vault` stays public in demo mode for reviewer/demo compatibility;
- other non-health routes require the configured access password;
- successful login sets a signed `HttpOnly` cookie;
- this is a minimal single-password gate, not a multi-user auth system.

## Readiness Model

`/readyz` verifies the current configuration and the local assets required by the shipped app:

- demo patient JSON;
- demo family vault JSON;
- reviewer quickstart markdown;
- committed vault manifest;
- template and static directories.

If `OPENCARE_VAULT_SOURCE=local_file`, readiness also checks that the configured local vault file path exists.

If any of these are missing, readiness fails closed.

## Security Boundaries

- Self-hosted MVP only.
- Synthetic/demo-only data in the shipped repo.
- Operator-mounted local file mode is read-only and private-by-operator, not a sharing or upload feature.
- No real genetics support in this phase.
- No upload support in this phase.
- No medical advice.
- No clinical decision support.
- No user account system.
- No database persistence workflow.
- No secrets committed to source control.

For broader product and safety context, also read [README.md](../README.md) and [privacy_safety_threat_model.md](privacy_safety_threat_model.md).
