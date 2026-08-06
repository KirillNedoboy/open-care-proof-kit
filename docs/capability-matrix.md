# Capability Matrix

This matrix describes the Phase 2 implementation on public `main` as of
2026-08-04. The published `v0.1.0` tag remains the controlled private-alpha
baseline; the Phase 2 boundary is published as `v0.2.0`.

| Capability | Status | Repository evidence or boundary |
|---|---|---|
| People | `PARTIAL` | Actor-scoped Product Core People are persisted and explicitly owner-created; broader health entities remain demo-only. |
| Family relationships | `IMPLEMENTED` | `app/family_access/` persists and policy-filters Families, memberships, and relationships without treating them as grants. |
| Health vault entities | `DEMO_ONLY` | `app/health_vault/models.py`, `app/health_vault/loader.py`, `app/health_vault/read_model.py` |
| Local JSON vault | `PARTIAL` | `app/health_vault/loader.py`, `app/health_vault/runtime_loader.py`, `app/config.py`, `app/main.py`, `docs/examples/local-family-vault.template.json` |
| Persistent editable vault | `PARTIAL` | Medication/Visit lifecycle, active People, Family permissions, and actor-scoped JSON API are implemented; broader fact types remain out of scope. |
| Document upload | `OUT_OF_SCOPE` | No upload route or handler in `app/main.py`; reviewer UI explicitly rejects this scope |
| Immutable source storage | `IMPLEMENTED` | `app/product_core/services.py`, `app/product_core/migrations.py`, and focused source integrity/compensation tests |
| Extraction | `PARTIAL` | Explicit plain-text source registration exists; no document extraction, OCR, or model extraction |
| Review inbox | `PARTIAL` | Medication review UI at `/workspace`; broader review remains unsupported |
| Canonical confirmed records | `PARTIAL` | Medication-only confirmation is transactional and active-state backed in `app/product_core/` |
| Timeline | `PARTIAL` | Medication confirmation creates one deterministic timeline event atomically; demo read model remains separate |
| Medications | `PARTIAL` | Product Core medication candidate/canonical lifecycle in `app/product_core/`; synthetic Health/Family Vault remains demo-only |
| Conditions | `DEMO_ONLY` | `Condition` model and read-model rendering in `app/health_vault/models.py`, `app/health_vault/read_model.py`, `app/main.py` |
| Labs | `DEMO_ONLY` | `LabResult` model and read-model rendering in `app/health_vault/models.py`, `app/health_vault/read_model.py`, `app/main.py` |
| Encounters / visits | `PARTIAL` | Persistent Person-scoped Visits in `app/product_core/`; synthetic Health/Family Vault visits remain demo-only |
| Questions | `PARTIAL` | Persistent user-authored Visit Questions in `app/product_core/`; no generated answers or broad question workspace |
| Visit preparation | `IMPLEMENTED` | Workspace supports persistent Visits, Questions, Visit-scoped immutable Brief revisions, confirmed-evidence selection, preparation notes, restore history, and audited Markdown export; the earlier transient endpoint remains compatible |
| Guarded chat | `IMPLEMENTED` | Live chat requires an Actor session, accessible active Person, and `chat.use`; the server builds isolated Product Core context from the question-only request. |
| External LLM provider | `PARTIAL` | Opt-in `OpenAIResponsesProvider` in `app/agent/provider.py`, configuration gates in `app/config.py`, tests in `tests/test_agent.py`; not required by default |
| Citation validation | `IMPLEMENTED` | `app/agent/validation.py`, `app/agent/service.py`, `app/agent/portable.py`, `tests/test_agent.py`, `tests/test_portable_agent_cli.py` |
| Audit | `IMPLEMENTED` | Metadata-only agent/report audit plus atomic schema v5 access audit for sensitive mutations and exports; denial-audit failure preserves denial. |
| Evaluations | `IMPLEMENTED` | `evals/runner.py`, `evals/cases/`, `evals/trust_metrics.py`, `tests/test_evals_runner.py`, `tests/test_trust_metrics.py` |
| Wheel distribution | `IMPLEMENTED` | The source checkout and non-editable wheel startup have accepted validation evidence; runtime assets are packaged. |
| Constrained Python 3.12 | `IMPLEMENTED` | `constraints/python312.txt` pins the accepted Python 3.12 release/test environment. |
| PGx | `DEMO_ONLY` | `app/pgx/`, `app/demo_pipeline.py`, `data/evidence_packs/pgx_demo_pack.json`, `tests/test_pgx_matcher.py`, `tests/test_demo_pipeline.py` |
| Genetics | `DEMO_ONLY` | Demo parser only in `app/genetics/`, `data/demo_patients/demo_patient_a_23andme.txt`, `tests/test_genotype_parser.py`; no Product Core genetics workflow |
| Deployment | `PARTIAL` | Production Compose persists Product Core and backups while keeping `OPENCARE_SESSION_DB_PATH` on non-persistent `/run/opencare` tmpfs; this is not a deployment or production-readiness claim. |
| Backup and export | `PARTIAL` | Person export v2 and offline schema v5 backup/verify/preflight/recover preserve durable access state but no sessions. No import, merge, encryption, or populated-target recovery exists. |
| Agent tools | `PARTIAL` | Portable context and answer validation CLI in `app/agent/cli.py`, `app/agent/portable.py`, `skills/opencare-health-agent/`; no read-only Product Core tool surface |
| Family permissions | `IMPLEMENTED` | Fixed owner/caregiver scopes, explicit consent/assignments, high-risk owner confirmation, private invitations, last-owner/admin invariants, and filtered management UI/API. |

## Reading rules

`IMPLEMENTED` means executable runtime behavior is present and covered by
inspected tests or configuration. `PARTIAL` means a bounded subset exists but
the capability is not a complete Product Core workflow. `DEMO_ONLY` means the
behavior is synthetic, read-only, reference-only, or otherwise not a complete
user-owned feature. `PLANNED` means approved future work. `OUT_OF_SCOPE` means
explicitly excluded from the current phase.

The statuses do not imply clinical validation or production readiness.
