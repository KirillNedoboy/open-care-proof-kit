# Portable Trust fixtures (`fixtures/agent-trust/`)

> **SYNTHETIC / OFFLINE fixtures only.** These files are NOT authorization, NOT
> consent, and NOT real health data. They are generated from fixed synthetic
> inputs for portability testing and documentation. Nothing in this directory
> grants access to a live OpenCare installation; constructing or replaying a
> Snapshot, Envelope, or Receipt locally has no authority whatsoever.

## Files

| File | Contract | What it demonstrates |
|---|---|---|
| `allowed-envelope.json` | `opencare-trust-envelope/1` | A valid synthetic Envelope (person-alice, `summarize_records`) that verifies. |
| `allowed-receipt.json` | `opencare-execution-receipt/1` | A valid `completed` Receipt that links to the allowed Envelope hash and verifies. |
| `refused-before-envelope-receipt.json` | `opencare-execution-receipt/1` | A `refused` Receipt: it references the same Envelope identity but records that execution did NOT complete. |
| `unsupported-action-receipt.json` | `opencare-execution-receipt/1` | Fail-closed refusal (`unsupported_action`) that links to a placeholder (all-zero) Envelope identity — no Envelope was ever issued. |

## Semantics

- **A Receipt alone does not prove a completed Envelope.** `refused-before-envelope-receipt.json`
  uses the domain's refused-receipt shape: `status: "refused"`, no `output_sha256`,
  explicit `reason_codes`. Even though it references the same Envelope identity as
  `allowed-receipt.json`, it claims nothing was executed. Completion requires
  `status: "completed"` plus an `output_sha256` and verification against a valid,
  unexpired Envelope.
- **Unsupported actions fail closed.** `unsupported-action-receipt.json` records
  `reason_codes: ["unsupported_action"]` and its `envelope_id` is a zero placeholder
  because an unsupported action never receives an Envelope. Validating it against
  `allowed-envelope.json` fails with `receipt_exceeds_envelope`.

## Verification

The fixture clock is fixed (`2027-08-02T10:00:00Z`), so always pass `--at`:

```powershell
.\.venv\Scripts\python.exe -m app.agent_trust.cli verify-envelope --envelope fixtures/agent-trust/allowed-envelope.json --at 2027-08-02T10:00:00Z
.\.venv\Scripts\python.exe -m app.agent_trust.cli verify-receipt --receipt fixtures/agent-trust/allowed-receipt.json --envelope fixtures/agent-trust/allowed-envelope.json --at 2027-08-02T10:00:00Z
.\.venv\Scripts\python.exe -m app.agent_trust.cli verify-receipt --receipt fixtures/agent-trust/unsupported-action-receipt.json --envelope fixtures/agent-trust/allowed-envelope.json --at 2027-08-02T10:00:00Z
```

Exit codes: `0` accepted, `1` rejected. The third command exits `1`
(`receipt_exceeds_envelope`) — expected, that is the fail-closed demonstration.

## Regeneration

The JSON files are generated deterministically from the trusted synthetic
builders — never hand-authored — so they stay byte-identical to the current
contract models:

```powershell
.\.venv\Scripts\python.exe -m app.agent_trust.cli regenerate-fixtures
```

Identities are the fixed synthetic set (`actor-alice`, `credential-alice`,
`person-alice`, `evidence-medication-alice`, `consent-alice`). These are not
real Actors, credentials, People, or consent events and are not reusable as
live authorization. Do not replace these fixtures with real health data.
