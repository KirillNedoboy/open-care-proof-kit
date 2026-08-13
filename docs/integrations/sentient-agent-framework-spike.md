# Sentient G2.5 — Sentient Agent Framework Integration Spike

**Status:** optional integration spike (design and implementation contract)
**Parent:** Sentient G2 Consent-Gated Runtime (`docs/architecture/sentient-g2-consent-runtime.md`)
**Boundary:** synthetic/demo only. This spike proves event compatibility; it is
not a production Sentient integration and is not live-vault access.

## Official sources checked

| Source | State checked (2026-08-13) |
|---|---|
| `github.com/sentient-agi/Sentient-Agent-Framework` | README; package is beta: "currently in beta and will likely change. It is not yet ready for production use." |
| `github.com/sentient-agi/Sentient-Agent-Framework-Examples` | README; examples demonstrate `AbstractAgent` + `DefaultServer` event patterns; demonstration-only |
| `github.com/sentient-agi/Sentient-Agent-Client` | referenced as the client for testing agents built with the framework |
| PyPI `sentient-agent-framework` | **version `0.3.0`** (only version verified in this spike); `requires-python >=3.9`; pure wheel (`py3-none-any`) |

Do not inspect unrelated Sentient repositories. ROMA, EvoSkill and Sentient
Enclaves are out of scope.

## Dependency compatibility (Stage 0 result)

`sentient-agent-framework==0.3.0` declares exact pins:

- `cuid2==2.0.1`
- `fastapi==0.115.12`
- `python-ulid==3.0.0`
- `uvicorn==0.34.0`

OpenCare declares `fastapi>=0.111.0`, `uvicorn[standard]>=0.30.0`, `pydantic>=2.7.0`.
Both pins satisfy OpenCare's floors, so the optional extra installs without
downgrading OpenCare requirements. This is verified by an actual isolated
Python 3.12 install in this spike; if coexistence ever fails, the spike is
`NO-GO` and OpenCare dependencies are not relaxed.

Dependency direction: OpenCare core never depends on Sentient. The package is
an optional extra:

```toml
[project.optional-dependencies]
sentient = ["sentient-agent-framework==0.3.0"]
```

`import app` and normal server startup must work with the extra absent.

## Integration surface used

- `AbstractAgent` — base class; subclass `OpenCareSentientDemoAgent`.
- `assist(session: Session, query: Query, response_handler: ResponseHandler)` — the only entry point.
- `Query.prompt` — the current user request (the only request content used).
- `ResponseHandler` — presentation-only event emission:
  `emit_json`, `emit_text_block`, `emit_error`, `complete`.
- `DefaultServer` — optional development-only `/assist` SSE server on
  localhost; it owns its own FastAPI app, so OpenCare's FastAPI application is
  not modified.

Sentient `Session`/request identifiers (`processor_id`, `activity_id`,
`request_id`, `chat_id`) are Sentient correlation identifiers. They are
**not** OpenCare `actor_id`/`person_id`, session credentials, or authorization
proofs. They are ignored by the adapter except as non-authoritative transient
metadata; nothing is persisted to Product Core.

## OpenCare G2 dependency direction

The adapter consumes the existing G2 runtime contract:

```text
Sentient Query
→ thin OpenCare Sentient adapter
→ fixed synthetic authenticated OpenCare demo context
→ G2 prepare
→ live G2 authorization semantics (existing SyntheticAuthority + G1 builder)
→ G1 Trust Envelope
→ deterministic provider (G2 provider protocol)
→ G2 answer validation (tool mediation, field bounds, Receipt)
→ canonical Execution Receipt
→ Sentient Chat events
```

The adapter contains no health policy and no authorization implementation of
its own. It orchestrates:

- `app.agent_trust.testing.SyntheticAuthority` (existing synthetic fixtures);
- `app.agent_trust.builders.TrustedEnvelopeBuilder` (existing G1 builder);
- `app.agent.g2_runtime.G2Runtime` (existing G2 consent gate);
- `app.agent.policy.classify_question` (existing OpenCare safety policy,
  pre-G2 gate);
- a deterministic local provider implementing the existing `G2Provider`
  protocol (answer derived only from the projected disclosure).

No external provider is invoked; no external-disclosure consent is required.

## Synthetic-only boundary and fail-closed rules

- The demo context is one fixed synthetic Actor (`actor-alice`) + Person
  (`person-alice`) authorization built from `SyntheticAuthority.allowed`.
- The demo `SessionStore` is always created fresh in a caller-supplied
  directory; a pre-existing session database is rejected (live-install guard).
- The demo context never opens, reads, or falls back to a live Product Core
  database. There is no supported configuration mapping a Sentient
  `processor_id` to a local Actor or a Sentient query person name to an
  active Person.
- If the synthetic authority/context cannot be constructed, the adapter fails
  closed with an explicit error; it never falls back to live state.
- No real health data is committed.

## Identity gap

Sentient's current `Session`/request model does not provide a verified OpenCare
Actor credential. The binding rule:

```text
Sentient processor_id  →  OpenCare actor_id        (never)
Sentient session history  →  Person access          (never)
Sentient Chat identity  →  OpenCare authorization   (never)
```

Person access derives only from the fixed synthetic authority inside the demo
context. A live-vault Sentient adapter is deferred until OpenCare has an
explicit authenticated identity-binding design.

## Event mapping (presentation only)

| Event name | Emitted via | Content |
|---|---|---|
| `OPENCARE_STATUS` | `emit_json` | `{"stage": "authorized\|prepared\|validated\|refused", "purpose": "...", "requested_action": "..."}` plus bounded `reason_code` on refusal. No access internals. |
| `SOURCES` | `emit_json` | Only Envelope-projected evidence descriptors (`evidence_id`, `selected_fields`) already authorized by the G2 projection. Never sources outside the Envelope. |
| `FINAL_RESPONSE` | `emit_text_block` | The already validated OpenCare answer (G2 `ExecuteResult.answer` after Receipt verification). Unvalidated provider output is never streamed. |
| `OPENCARE_RECEIPT` | `emit_json` | Redacted Receipt summary: `receipt_id`, `canonical_hash` (`receipt_sha256`), `envelope_hash` (`envelope_id`), `outcome`, `validation_result`. Never the whole Envelope. |
| `error` | `emit_error` | Bounded refusal information; never leaks another Person's existence. |

Order: `OPENCARE_STATUS` (authorized/prepared) → `SOURCES` → `FINAL_RESPONSE`
→ `OPENCARE_RECEIPT` → `complete()`. Refusal paths emit bounded
`OPENCARE_STATUS refused` + `error` (and `OPENCARE_RECEIPT` only when G2
produced a real Receipt) then `complete()`.

Receipts are only ever the Receipt produced/validated by existing G1/G2 logic;
no Sentient-specific receipt format and no fabricated hashes.

## Safety gate

`classify_question` (existing OpenCare policy) decides before G2 for urgent
and blocked clinical/genetics requests. The adapter never invents medical
policy. Refusals are bounded and the response completes correctly.

## Validation order

```text
Sentient query → OpenCare safety policy → G2 runtime → deterministic provider
→ G2 answer validation → durable/verified G2 Receipt → Sentient events
```

Forbidden: provider output → `FINAL_RESPONSE` → validation later. Only
validated output becomes the final Sentient answer.

## Limitations

- Beta SDK; not production-ready upstream.
- Synthetic/demo only; no live personal/family data through Sentient Chat.
- No production identity binding; Sentient session IDs are not authorization.
- No external LLM; deterministic provider only.
- No G3 model portability; no Agent Plugins/MCP packaging in this phase.
- Does not solve semantic prompt injection; demonstrates identity/capability
  containment for a fixed synthetic context.

## Future live identity bridge (not part of G2.5)

A future live adapter requires:

```text
verified external identity
→ explicit OpenCare Actor binding
→ authenticated session/credential exchange
→ normal G2 live authorization
```

This design is out of scope for the spike.

## Roadmap note preserved

```text
G4 Portable Trust Package
→ target Agent Plugins v1 packaging
→ skill first
→ optional read-only MCP adapter after safe runtime boundary
```

No `plugin.json`, no `mcp.json`, no Agent Plugins conformance work in G2.5.

## Acceptance

PASS requires: optional package integrates cleanly; adapter uses actual
Sentient interfaces; adapter delegates to existing G2; synthetic event path
works; validated output is emitted; Receipt surfaced safely; wrong-Person /
capability tests pass; no live-vault identity bypass; base OpenCare works
without Sentient installed. Otherwise the spike returns `NO-GO` rather than
weakening OpenCare.
