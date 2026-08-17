# ADR 0006: G5 engineering closure and ecosystem validation status

- Status: Accepted
- Date: 2026-08-17
- Decision owners: OpenCare maintainers
- Implementation: Integrated on `main` (fast-forward) after the published `v0.2.0` baseline; not a release tag

## Context

Sentient G5 — Ecosystem Validation — evaluated the existing G1–G4 system: a
deterministic offline adversarial corpus, a single-reviewer route, trust
metrics, an OWASP taxonomy mapping, plugin supply-chain checks, and
cross-client loading evidence for the skill-only Agent Plugins package
`agent-plugins/opencare-trust/`. The engineering and automated security
evaluation work is complete; the remaining evidence depends on external
client/account availability, not on internal implementation.

This ADR records the G5 engineering closure. It changes no runtime behavior,
no G1–G4 contract, no security test, and no machine gate.

## Decision

### G5 engineering work is closed and may be integrated

Completed evidence:

- adversarial corpus complete (`evals/g5/corpus.json`, 20 cases, eight
  security-invariant families);
- reviewer route complete (`python -m evals.g5_review` — 20/20 cases pass,
  all security-invariant counters zero);
- trust metrics complete (context precision/recall, minimization, provenance
  coverage, refusal correctness, receipt completeness);
- OWASP taxonomy mapping complete;
- package supply-chain checks green (containment, no secrets, no `mcp.json`,
  byte-identity);
- deterministic replay green;
- Agent Skills interoperability proven on OMP 17.3.5 (local) and Hermes Agent
  v0.19.0 (remote VPS) with byte-identical committed Skills — Trust positive,
  Trust negative, and Health safety smokes pass on both clients;
- Cursor 3.0.13 root `plugin.json` loading proven for one client (both Skills
  discovered, package bytes unmodified).

### Outstanding limitation (externally dependent)

- Two independent clients consuming the root Agent Plugins `plugin.json`
  have not been proven;
- Cursor 3.0.13 behavioral smoke is blocked by usage quota;
- Kiro 1.0.293 root-plugin evidence is blocked by account/sign-in;
- this is externally dependent interoperability evidence, not an OpenCare
  security defect.

### Non-claims

G5 does not claim: universal client interoperability; root Agent Plugins
portability proven across two clients; prompt-injection elimination; clinical
validation; MCP support; signer authenticity.

### Management decision

The remaining root-plugin two-client limitation is non-blocking for P1. Future
client evidence can be appended to
`docs/assets/g5/client-interop-evidence.md` without reopening G5 architecture.
The machine gate keeps reporting `READY_FOR_SECOND_CLIENT_SMOKE` until the
root-plugin two-client condition is actually satisfied.
