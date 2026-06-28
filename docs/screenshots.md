# Screenshot Guide

Do not commit generated screenshot image files unless a maintainer explicitly requests them. This guide lists the exact local pages to capture for a README, grant application, or demo video.

Start the server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Recommended Screenshots

### Landing Page

URL:

```txt
http://127.0.0.1:8000/
```

Caption:

```txt
OpenCare Proof Kit landing page showing the local-first, evidence-grounded health AI proof-kit framing and reviewer navigation.
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

### Sertraline Matched Demo Rule Report

URL:

```txt
http://127.0.0.1:8000/demo/report-view?drug=sertraline
```

Caption:

```txt
Clinician-reviewable sertraline briefing generated from synthetic data, local demo evidence, safety policy checks, and JSON audit metadata.
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

## Safety Reminder

Screenshots must not include real patient data, secrets, private URLs, API keys, or non-demo generated reports. The current demo pages should show synthetic/demo content only.
