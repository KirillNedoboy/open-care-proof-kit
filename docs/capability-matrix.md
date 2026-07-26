# Capability Matrix

This matrix describes verified repository capability as of 2026-07-26. A
status is about the current implementation, not the approved future direction.

| Capability | Status | Repository evidence or boundary |
|---|---|---|
| People | `DEMO_ONLY` | `app/health_vault/models.py`, `app/health_vault/read_model.py`, `data/demo_patients/demo_family_vault.json`, `app/main.py` |
| Family relationships | `DEMO_ONLY` | `app/health_vault/models.py`, `app/health_vault/read_model.py`, `app/templates/health_vault.html` |
| Health vault entities | `DEMO_ONLY` | `app/health_vault/models.py`, `app/health_vault/loader.py`, `app/health_vault/read_model.py` |
| Local JSON vault | `PARTIAL` | `app/health_vault/loader.py`, `app/health_vault/runtime_loader.py`, `app/config.py`, `app/main.py`, `docs/examples/local-family-vault.template.json` |
| Persistent editable vault | `PARTIAL` | Medication-only lifecycle and JSON API in `app/product_core/`; no UI, people table, per-person authorization, or broader fact types |
| Document upload | `OUT_OF_SCOPE` | No upload route or handler in `app/main.py`; reviewer UI explicitly rejects this scope |
| Immutable source storage | `IMPLEMENTED` | `app/product_core/services.py`, `app/product_core/migrations.py`, and focused source integrity/compensation tests |
| Extraction | `PARTIAL` | Explicit plain-text source registration exists; no document extraction, OCR, or model extraction |
| Review inbox | `PARTIAL` | Candidate review service and API routes exist without a UI in `app/product_core/` |
| Canonical confirmed records | `PARTIAL` | Medication-only confirmation is transactional and active-state backed in `app/product_core/` |
| Timeline | `PARTIAL` | Medication confirmation creates one deterministic timeline event atomically; demo read model remains separate |
| Medications | `PARTIAL` | Product Core medication candidate/canonical lifecycle in `app/product_core/`; synthetic Health/Family Vault remains demo-only |
| Conditions | `DEMO_ONLY` | `Condition` model and read-model rendering in `app/health_vault/models.py`, `app/health_vault/read_model.py`, `app/main.py` |
| Labs | `DEMO_ONLY` | `LabResult` model and read-model rendering in `app/health_vault/models.py`, `app/health_vault/read_model.py`, `app/main.py` |
| Encounters / visits | `DEMO_ONLY` | `Visit` model and read-model rendering in `app/health_vault/models.py`, `app/health_vault/read_model.py`, `app/main.py` |
| Questions | `DEMO_ONLY` | `QuestionThread` model, read model, page rendering, and guarded question response in `app/health_vault/models.py`, `app/health_vault/read_model.py`, `app/agent/service.py` |
| Visit preparation | `PARTIAL` | Deterministic Product Core Visit Brief service and API exist; UI and broader visit workflow remain deferred |
| Guarded chat | `IMPLEMENTED` | Routes in `app/main.py`; policy, service, validation, and audit in `app/agent/`; coverage in `tests/test_agent.py`, `tests/test_chat_api.py`, `tests/test_api.py` |
| External LLM provider | `PARTIAL` | Opt-in `OpenAIResponsesProvider` in `app/agent/provider.py`, configuration gates in `app/config.py`, tests in `tests/test_agent.py`; not required by default |
| Citation validation | `IMPLEMENTED` | `app/agent/validation.py`, `app/agent/service.py`, `app/agent/portable.py`, `tests/test_agent.py`, `tests/test_portable_agent_cli.py` |
| Audit | `IMPLEMENTED` | Metadata-only agent audit in `app/agent/audit.py`; report audit in `app/reports/json_audit.py`; tests in `tests/test_agent.py`, `tests/test_report_generation.py` |
| Evaluations | `IMPLEMENTED` | `evals/runner.py`, `evals/cases/`, `evals/trust_metrics.py`, `tests/test_evals_runner.py`, `tests/test_trust_metrics.py` |
| PGx | `DEMO_ONLY` | `app/pgx/`, `app/demo_pipeline.py`, `data/evidence_packs/pgx_demo_pack.json`, `tests/test_pgx_matcher.py`, `tests/test_demo_pipeline.py` |
| Genetics | `DEMO_ONLY` | Demo parser only in `app/genetics/`, `data/demo_patients/demo_patient_a_23andme.txt`, `tests/test_genotype_parser.py`; no Product Core genetics workflow |
| Deployment | `PARTIAL` | `Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`, `deploy/`, `scripts/smoke_check.py`, `docs/deployment.md`, `docs/production_deployment.md` |
| Backup and export | `PLANNED` | Report output exists, but no vault backup/export workflow; operator guidance is documentation only |
| Agent tools | `PARTIAL` | Portable context and answer validation CLI in `app/agent/cli.py`, `app/agent/portable.py`, `skills/opencare-health-agent/`; no read-only Product Core tool surface |
| Family permissions | `OUT_OF_SCOPE` | No permission or caregiver authorization model in the runtime |

## Reading rules

`IMPLEMENTED` means executable runtime behavior is present and covered by
inspected tests or configuration. `PARTIAL` means a bounded subset exists but
the capability is not a complete Product Core workflow. `DEMO_ONLY` means the
behavior is synthetic, read-only, reference-only, or otherwise not a complete
user-owned feature. `PLANNED` means approved future work. `OUT_OF_SCOPE` means
explicitly excluded from the current phase.

The statuses do not imply clinical validation or production readiness.
