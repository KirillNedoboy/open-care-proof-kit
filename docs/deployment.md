# Deployment

OpenCare Proof Kit V2A is a self-hosted MVP foundation for a private personal/family medical workspace.

This is not clinical software. It does not provide diagnosis, treatment recommendation, dosage guidance, medication selection advice, or start/stop medication advice. It does not support real genetics, raw genotype, VCF, FASTQ, BAM, or WGS uploads in this phase.

## Runtime Modes

- `OPENCARE_ENV=development` keeps local startup easy and leaves the current demo/reviewer routes public.
- `OPENCARE_ENV=production` enables production validation.
- `OPENCARE_DEMO_MODE=true` keeps the current demo/reviewer routes public.
- `OPENCARE_DEMO_MODE=false` enables the minimal private access gate for non-health routes.

## Required Production Environment Variables

```txt
OPENCARE_ENV=production
OPENCARE_DEMO_MODE=true|false
OPENCARE_SECRET_KEY=<at least 32 characters>
```

Additional requirement for private production mode:

```txt
OPENCARE_ACCESS_PASSWORD=<required when OPENCARE_DEMO_MODE=false>
```

Optional path overrides:

```txt
OPENCARE_DATA_DIR=data
OPENCARE_REPORTS_DIR=reports
OPENCARE_ALLOW_CLOUD_LLM=false
```

Do not bake secrets into the image. Set them through the host environment, a local `.env` file that stays uncommitted, or your deployment system's secret store.

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

Current reviewer/demo routes:

```txt
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo
http://127.0.0.1:8000/demo/health-vault
```

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

## Private Access Gate

When `OPENCARE_ENV=production` and `OPENCARE_DEMO_MODE=false`:

- `/health`, `/healthz`, and `/readyz` stay public;
- non-health routes require the configured access password;
- successful login sets a signed `HttpOnly` cookie;
- this is a minimal single-password gate, not a multi-user auth system.

## Readiness Model

`/readyz` verifies the current configuration and the local assets required by the shipped app:

- demo patient JSON;
- demo family vault JSON;
- reviewer quickstart markdown;
- committed vault manifest;
- template and static directories.

If any of these are missing, readiness fails closed.

## Security Boundaries

- Self-hosted MVP only.
- Synthetic/demo-only data model in the shipped repo.
- No real genetics support in this phase.
- No medical advice.
- No clinical decision support.
- No user account system.
- No upload workflow.
- No secrets committed to source control.

For broader product and safety context, also read [README.md](../README.md) and [privacy_safety_threat_model.md](privacy_safety_threat_model.md).
