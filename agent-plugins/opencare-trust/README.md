# opencare-trust

Portable, skill-only Agent Plugins v1 package for the OpenCare trust contract.

## Contents

- `plugin.json` — strict Agent Plugins 1.0.0 manifest (closed field set;
  `additionalProperties: false`).
- `skills/opencare-trust-envelope/` — generic trust skill: inspect Trust
  Envelopes, verify Execution Receipts, understand provenance / policy /
  disclosure fields, and distinguish verification from current authorization.
  Bundles the three trust JSON Schemas and two synthetic fixtures in `assets/`
  and the field-by-field contract reference in `references/PROTOCOL.md`.
- `skills/opencare-health-agent/` — OpenCare health agent skill: summarizes a
  supplied source-backed context packet, traces claims to sources, and prepares
  clinician questions. Never diagnoses or recommends. Bundles
  `context.schema.json`, `answer.schema.json`, and installation/examples docs.
- `README.md` — this file.

There is deliberately **no `mcp.json`**: the package is skill-only (Agent
Plugins 1.0.0 §6.2 permits a missing MCP location).

## Why there is no `version` field

`plugin.json` intentionally omits `version`. The root `pyproject.toml` version
(`0.1.0`) predates the published Git release history (the project has since
released `v0.2.0`), so reusing it would publish a stale release claim. A
portable plugin version should be minted with the first actual plugin release;
until then the manifest carries no version rather than a wrong one. The root
project version is unchanged.

## Source of truth

| Canonical source | Packaged copy |
| --- | --- |
| health skill `SKILL.md` + schemas | `skills/opencare-health-agent/` |
| health skill docs | `skills/opencare-health-agent/references/` |
| trust skill `SKILL.md` + `references/PROTOCOL.md` | `skills/opencare-trust-envelope/` |
| `schemas/agent-trust/*.schema.json` | `skills/opencare-trust-envelope/assets/` |
| `fixtures/agent-trust/allowed-*.json` | `skills/opencare-trust-envelope/assets/` |

`scripts/build_agent_plugin.py` is the only writer of this package; editing a
skill means editing the canonical file and rerunning the script. A drift test
(`tests/test_agent_plugin_drift.py`) asserts the committed copy stays
byte-identical to the canonical sources. The build is deterministic, offline,
and creates no symlinks.
