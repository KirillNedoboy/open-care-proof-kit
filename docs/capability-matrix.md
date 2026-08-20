# Capability Matrix

This matrix describes the integrated P1/P2/D1 Product Core boundary and the
P3 Genetics Research Studio on `codex/p3-genetics-research-studio`. The
published `v0.1.0` tag remains the controlled private-alpha baseline; P1, P2,
and D1 have no separate release tag.

P1 medication/condition/lab lifecycle, P2 workspace, and D1 document ingest are
implemented in this branch baseline. P3 adds a bounded, local-first genetics
workflow without claiming clinical genetics or general VCF support.

| Capability | Status | Repository evidence or boundary |
|---|---|---|
| People | `PARTIAL` | Actor-scoped Product Core People are persisted and explicitly owner-created; broader health entities remain demo-only. |
| Family relationships | `IMPLEMENTED` | `app/family_access/` persists and policy-filters Families, memberships, and relationships without treating them as grants. |
| Health vault entities | `DEMO_ONLY` | `app/health_vault/models.py`, `app/health_vault/loader.py`, `app/health_vault/read_model.py` |
| Local JSON vault | `PARTIAL` | `app/health_vault/loader.py`, `app/health_vault/runtime_loader.py`, `app/config.py`, `app/main.py`, `docs/examples/local-family-vault.template.json` |
| Persistent editable vault | `PARTIAL` | Product Core medication/condition/lab and Visit lifecycle, active People, Family permissions, and actor-scoped JSON API are implemented; other fact families remain out of scope. |
| Document upload | `IMPLEMENTED` | Authenticated Person-scoped PDF/TXT upload; exact raw bytes are immutable. |
| Immutable source storage | `IMPLEMENTED` | `app/product_core/services.py`, `app/product_core/migrations.py`, source integrity tests, and P3 genetics source hashes. |
| Extraction | `IMPLEMENTED` | Bounded deterministic embedded-text extraction; OCR and model extraction remain out of scope. |
| Review inbox | `IMPLEMENTED` | P2 workspace: unified medication + condition + lab candidate review at `/workspace`; broader fact families remain unsupported. |
| Canonical confirmed records | `IMPLEMENTED` | P1/P2: all three fact families (medication/condition/lab) confirm transactionally into `canonical_records` with typed detail; no other fact families. |
| Timeline | `IMPLEMENTED` | P2 workspace: medication/condition/lab confirmation and correction events with readable current/history presentation; demo read model remains separate. |
| Medications | `PARTIAL` | Product Core medication candidate/canonical lifecycle in `app/product_core/`; synthetic Health/Family Vault remains demo-only |
| Conditions | `IMPLEMENTED` | Source-backed recorded-condition lifecycle in `app/product_core/` (candidate → provenance → review → canonical condition record); explicitly a record, not a diagnosis. |
| Labs | `IMPLEMENTED` | Source-preserving lab lifecycle in `app/product_core/` (typed text values, source flags as-provided); no unit conversion or interpretation. |
| Encounters / visits | `PARTIAL` | Persistent Person-scoped Visits in `app/product_core/`; synthetic Health/Family Vault visits remain demo-only |
| Questions | `PARTIAL` | Persistent user-authored Visit Questions in `app/product_core/`; no generated answers or broad question workspace |
| Visit preparation | `IMPLEMENTED` | P2 workspace supports persistent Visits, Questions, Visit Brief revisions, all-three-type confirmed-evidence selection, preparation notes, restore history, and audited Markdown export; content schema v2 and readable v1 revisions. |
| Guarded chat | `IMPLEMENTED` | Live chat requires an Actor session, accessible active Person, and `chat.use`; the server builds isolated Product Core context from the question-only request and includes confirmed condition/lab evidence items. |
| External LLM provider | `PARTIAL` | Opt-in `OpenAIResponsesProvider` in `app/agent/provider.py`, configuration gates in `app/config.py`, tests in `tests/test_agent.py`; not required by default |
| Model provider portability | `IMPLEMENTED` | Provider-independent G2 execution contract and shared `build_provider_execution_request` in `app/agent/providers/contract.py`; loopback/non-loopback disclosure classification in `app/agent/providers/endpoints.py`; same G1/G2 validation and Receipts for every provider; conformance and trust suites in `tests/provider_*` |
| Self-hosted model runtime (Ollama) | `PARTIAL` | One self-hosted Ollama adapter in `app/agent/providers/ollama.py` (stdlib `urllib`, zero new deps, JSON-schema `format`, model-identity check, no-redirect, fail-closed); operator-only `OPENCARE_OLLAMA_*` config in `app/config.py`; live smoke `tests/provider_live_smoke.py` skips without a real Ollama, so status is `READY_FOR_LIVE_SMOKE` |
| Portable trust package (Sentient G4) | `IMPLEMENTED` | Generic trust layer with a stable public API in `app/agent_trust/api.py` and zero OpenCare coupling; generic `AuthorizationAdapter` Protocol with the OpenCare adapter in `app/agent/trust_adapter.py`; deterministic JSON Schemas in `schemas/agent-trust/` with export script and drift test; synthetic offline fixture corpus in `fixtures/agent-trust/` with deterministic regeneration; `opencare-trust` CLI (also `python -m app.agent_trust.cli`) with deterministic exit codes and no live-authorization minting path |
| Agent Plugins v1 skill package | `IMPLEMENTED` | Skill-only package at `agent-plugins/opencare-trust/` with strict 1.0.0 `plugin.json` and a `skills/` tree (including the canonical `opencare-health-agent` skill); deterministic build from the canonical skill sources with a drift test, no symlinks, package containment and secret/path scans, and no `mcp.json` |
| MCP adapter | `OUT_OF_SCOPE` | No `mcp.json` and no MCP server in G4; an optional read-only MCP adapter is explicitly deferred until G5 ecosystem validation |
| Multi-client ecosystem validation | `PLANNED` | Sentient G5: install and evaluate the skill-only package in independent clients; not claimed by G4 |
| Citation validation | `IMPLEMENTED` | `app/agent/validation.py`, `app/agent/service.py`, `app/agent/portable.py`, `tests/test_agent.py`, `tests/test_portable_agent_cli.py` |
| Audit | `IMPLEMENTED` | Metadata-only agent/report audit, schema v9 access audit, genetics review/research receipts, and denial-audit fail-closed behavior. |
| Evaluations | `IMPLEMENTED` | Deterministic G1/G2/G5/P1/P2/D1/P3 reviewers and focused tests; `python -m evals.p3_review` is offline. |
| Wheel distribution | `IMPLEMENTED` | The source checkout and non-editable wheel startup have accepted validation evidence; runtime assets are packaged. |
| Constrained Python 3.12 | `IMPLEMENTED` | `constraints/python312.txt` pins the accepted Python 3.12 release/test environment. |
| PGx | `IMPLEMENTED/PARTIAL` | Deterministic reviewed genetics finding × exact confirmed medication intersection; association display only, no dosage/start/stop action. |
| Genetics source | `IMPLEMENTED` (P3 branch) | Immutable local consumer-genotype Source, bounded TXT import, schema v9 dataset/observation/finding/research tables; VCF remains demo-only. |
| Genetics Workspace | `IMPLEMENTED` (P3 branch) | `/genetics` responsive tabs for overview, variants, PGx, associations, traits/systems, evidence, family comparison, and Research Studio. |
| Research Mode | `IMPLEMENTED` (P3 branch) | Offline deterministic Evidence/Explore contracts with structured epistemic labels, citations, counterevidence, and no canonical mutation path. |
| Deployment | `PARTIAL` | Production Compose persists Product Core and backups while keeping `OPENCARE_SESSION_DB_PATH` on non-persistent `/run/opencare` tmpfs; this is not a deployment or production-readiness claim. |
| Backup and export | `IMPLEMENTED/PARTIAL` | Ordinary vault export excludes genetics; explicit OpenCare Genetics Package v1 includes authorized raw source and indexed/reviewed data; installation backup/recovery preserves schema v9 and source hashes. |
| Agent tools | `PARTIAL` | Existing trust tools remain unchanged; Research Mode uses a minimized genetics packet and metadata-only receipt boundary. |
| Family permissions | `IMPLEMENTED` | Legacy family-access generations remain frozen; separate explicit `genetics.read/write/research/compare/export` grants are required and revocable. |


## Reading rules

`IMPLEMENTED` means executable runtime behavior is present and covered by
inspected tests or configuration. `PARTIAL` means a bounded subset exists but
the capability is not a complete Product Core workflow. `DEMO_ONLY` means the
behavior is synthetic, read-only, reference-only, or otherwise not a complete
user-owned feature. `PLANNED` means approved future work. `OUT_OF_SCOPE` means
explicitly excluded from the current phase.

The statuses do not imply clinical validation or production readiness.
