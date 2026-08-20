# Capability Matrix

This matrix describes the current P2 workspace and integrated P1 Product Core
implementation on public `main` after the published `v0.2.0` boundary. The
published `v0.1.0` tag remains the controlled private-alpha baseline; P1 and
P2 have no separate release tag.

The historical Phase-2 date above is preserved. P1's source-backed
medication/condition/lab lifecycle and P2's workspace updates are marked
inline below.

| Capability | Status | Repository evidence or boundary |
|---|---|---|
| People | `PARTIAL` | Actor-scoped Product Core People are persisted and explicitly owner-created; broader health entities remain demo-only. |
| Family relationships | `IMPLEMENTED` | `app/family_access/` persists and policy-filters Families, memberships, and relationships without treating them as grants. |
| Health vault entities | `DEMO_ONLY` | `app/health_vault/models.py`, `app/health_vault/loader.py`, `app/health_vault/read_model.py` |
| Local JSON vault | `PARTIAL` | `app/health_vault/loader.py`, `app/health_vault/runtime_loader.py`, `app/config.py`, `app/main.py`, `docs/examples/local-family-vault.template.json` |
| Persistent editable vault | `PARTIAL` | Product Core medication/condition/lab and Visit lifecycle, active People, Family permissions, and actor-scoped JSON API are implemented; other fact families remain out of scope. |
| Document upload | `OUT_OF_SCOPE` | No upload route or handler in `app/main.py`; document upload remains outside P2. |
| Immutable source storage | `IMPLEMENTED` | `app/product_core/services.py`, `app/product_core/migrations.py`, and focused source integrity/compensation tests |
| Extraction | `PARTIAL` | Explicit plain-text and structured source registration exists; no document extraction, OCR, or model extraction. |
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
| Audit | `IMPLEMENTED` | Metadata-only agent/report audit plus atomic schema v7 access audit for sensitive mutations and exports; denial-audit failure preserves denial. |
| Evaluations | `IMPLEMENTED` | `evals/runner.py`, `evals/cases/`, `evals/trust_metrics.py`, `tests/test_evals_runner.py`, `tests/test_trust_metrics.py`; deterministic P1 reviewer `python -m evals.p1_review` and P2 reviewer `python -m evals.p2_review` with focused reviewer tests and guides. |
| Wheel distribution | `IMPLEMENTED` | The source checkout and non-editable wheel startup have accepted validation evidence; runtime assets are packaged. |
| Constrained Python 3.12 | `IMPLEMENTED` | `constraints/python312.txt` pins the accepted Python 3.12 release/test environment. |
| PGx | `DEMO_ONLY` | `app/pgx/`, `app/demo_pipeline.py`, `data/evidence_packs/pgx_demo_pack.json`, `tests/test_pgx_matcher.py`, `tests/test_demo_pipeline.py` |
| Genetics | `DEMO_ONLY` | Demo parser only in `app/genetics/`, `data/demo_patients/demo_patient_a_23andme.txt`, `tests/test_genotype_parser.py`; no Product Core genetics workflow |
| Deployment | `PARTIAL` | Production Compose persists Product Core and backups while keeping `OPENCARE_SESSION_DB_PATH` on non-persistent `/run/opencare` tmpfs; this is not a deployment or production-readiness claim. |
| Backup and export | `PARTIAL` | Person export format v3 with condition/lab entities and offline schema backup/verify/preflight/recover on schema v7 preserve durable access state but no sessions. No import, merge, encryption, or populated-target recovery exists. |
| Agent tools | `PARTIAL` | Portable context and answer validation CLI in `app/agent/cli.py`, `app/agent/portable.py`, `skills/opencare-health-agent/`; no read-only Product Core tool surface |
| Family permissions | `IMPLEMENTED` | Versioned scope generations — `family-access-v1` frozen verbatim, `family-access-v2` current and adds `condition.read/write` and `lab.read/write`; generation inferred from stored scopes (no silent privilege expansion); explicit caregiver/owner upgrades; fixed owner/caregiver scopes, explicit consent/assignments, high-risk owner confirmation, private invitations, last-owner/admin invariants, and filtered management UI/API. |

## Reading rules

`IMPLEMENTED` means executable runtime behavior is present and covered by
inspected tests or configuration. `PARTIAL` means a bounded subset exists but
the capability is not a complete Product Core workflow. `DEMO_ONLY` means the
behavior is synthetic, read-only, reference-only, or otherwise not a complete
user-owned feature. `PLANNED` means approved future work. `OUT_OF_SCOPE` means
explicitly excluded from the current phase.

The statuses do not imply clinical validation or production readiness.
