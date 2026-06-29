# Screenshot Guide

Phase 1.9 includes committed screenshots captured from the local FastAPI demo using synthetic/demo data only. These screenshots are intended for GitHub and grant review. Recapture them when the web demo presentation changes.

The report-view screenshots use neutral "Medication-to-Doctor Briefing demo" subtitle copy so supported and unsupported drug pages do not imply the page is sertraline-specific.

Start the server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Screenshot Files

### Landing Page

URL:

```txt
http://127.0.0.1:8000/
```

Caption:

```txt
OpenCare Proof Kit landing page showing the local-first, evidence-grounded health AI proof-kit framing and reviewer navigation.
```

File:

```txt
docs/assets/screenshots/landing.png
```

What it proves:

```txt
The repository has a reviewer-facing local web entry point with explicit boundaries and quick links.
```

### Demo Patient And Pipeline

URL:

```txt
http://127.0.0.1:8000/demo
```

Caption:

```txt
Synthetic demo patient view with the Medication-to-Doctor Briefing question and deterministic local pipeline steps.
```

File:

```txt
docs/assets/screenshots/demo.png
```

What it proves:

```txt
The demo is synthetic-only and shows the local pipeline before report generation.
```

### Sertraline Matched Demo Rule Report

URL:

```txt
http://127.0.0.1:8000/demo/report-view?drug=sertraline
```

Caption:

```txt
Clinician-reviewable sertraline briefing generated from synthetic data, local demo evidence, safety policy checks, and JSON audit metadata.
```

File:

```txt
docs/assets/screenshots/sertraline-report.png
```

What it proves:

```txt
The supported-drug demo path produces a source-cited, safety-bounded report with audit metadata.
```

### Aspirin Unsupported-Drug No-Claim Report

URL:

```txt
http://127.0.0.1:8000/demo/report-view?drug=aspirin
```

Caption:

```txt
Unsupported-drug aspirin path showing safe no-claim behavior and explicit demo evidence-pack coverage limits.
```

File:

```txt
docs/assets/screenshots/aspirin-safe-no-claim.png
```

What it proves:

```txt
The unsupported-drug path fails closed: no invented clinical claim and explicit demo-only coverage limits.
```

## Manual Capture Fallback

If automated screenshot tooling is not available:

1. Start the local server with the command above.
2. Open each URL listed in this guide.
3. Capture the page content only, without browser address bars when possible.
4. Save files to the exact paths listed above.
5. Verify screenshots contain only synthetic/demo data and no private desktop paths, secrets, tokens, real patient data, or real genetic data.

## Safety Reminder

Screenshots must not include real patient data, secrets, private URLs, API keys, or non-demo generated reports. The current demo pages should show synthetic/demo content only.
