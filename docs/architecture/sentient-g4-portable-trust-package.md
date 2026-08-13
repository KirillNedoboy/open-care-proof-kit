# Sentient G4 — Portable Trust Package

Status: **Binding for G4 implementation**
Parent: Sentient G1 Trust Envelope, Sentient G2 Consent-Gated Agent Runtime, Sentient G3 Model Portability
Contract versions: `opencare-trust-envelope/1`, `opencare-execution-receipt/1` (unchanged from G1; G4 invents no new schema version)

## 1. Purpose and boundary

G4 packages the portable trust contract built by G1 (Trust Envelope + Execution Receipt), G2
(Consent-Gated Agent Runtime), and G3 (Model Portability) into a distributable, spec-conformant
**Agent Plugins v1 skill-only package**, and stabilizes the generic trust surface so downstream
agents can adopt it without importing OpenCare internals.

G4 is packaging and interface stabilization, **not a new security model**. It changes no
authorization semantics, no consent semantics, no evidence/provenance rules, no provider
boundary, no Receipt contract, and no trust authority. The G1 `contract_version` literals
(`opencare-trust-envelope/1`, `opencare-execution-receipt/1`) remain exactly as specified; G4
must not invent a new version or reinterpret an existing one. Everything G1 said about what a
valid hash does and does not prove still holds: hashes are integrity and deterministic identity,
never signer authenticity, live authorization, or a bearer credential (see §6).

The deliverable has four parts:

1. a **generic trust layer** (`app/agent_trust/`) with no OpenCare coupling, exposing a stable
   public API (`app/agent_trust/api.py`) and a single `AuthorizationAdapter` Protocol;
2. **versioned, deterministic artifacts** (`schemas/agent-trust/*.json`,
   `fixtures/agent-trust/`, CLI) for offline validation and downstream integration;
3. an **Agent Plugins v1 skill-only package** (`agent-plugins/opencare-trust/`) carrying the
   OpenCare health agent skill, built deterministically from the canonical skill source; and
4. an **OpenCare health reference adapter** (`app/agent/trust_adapter.py`) that implements the
   generic Protocol against live Family Access state.

G4 does not execute agents, does not mint live authorization from the CLI, does not add MCP
servers, does not add cloud or multi-client claims, and does not add signatures, PKI,
attestation, or a transparency log. Multi-client ecosystem validation is G5 (§12).

## 2. Layering

Bottom-up, each layer depends only on the layer below:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ OpenCare health reference adapter (app/agent/trust_adapter.py)          │
│   Family Access → live AuthorizationDecision (implements the Protocol)  │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ Agent Plugins v1 package (agent-plugins/opencare-trust/)                │
│   plugin.json (strict 1.0.0) + skills/opencare-health-agent/SKILL.md    │
│   skill-only; no mcp.json (explicit MCP deferral, §12)                  │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ Stable schemas / validation / CLI                                       │
│   schemas/agent-trust/*.json (deterministic export + drift test)        │
│   fixtures/agent-trust/ (allowed / refused / unsupported)               │
│   opencare-trust console entry + python -m app.agent_trust.cli          │
└─────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────┐
│ Generic trust contract (app/agent_trust/) — portable, zero OpenCare deps│
│   models, canonicalization, hashing, validation, trusted builders,      │
│   identifiers, AuthorizationAdapter Protocol, api.py public surface     │
└─────────────────────────────────────────────────────────────────────────┘
```

The generic contract is the only layer that defines trust semantics. Everything above it is
packaging, adaptation, or offline tooling. The OpenCare reference adapter is the only layer
that knows Family Access, Product Core, SessionStore, Ollama, or Sentient.

## 3. Generic vs health-specific boundary

`app/agent_trust/` is **generic and portable**. It must not import or reference FastAPI,
ProductCoreRuntime, repositories, DB connections, Family Access, SessionStore, the web layer,
Ollama, the Sentient integration, or any OpenCare service. It defines only the abstract
`AuthorizationAdapter` Protocol (one method: authorize an actor/credential/Person/scopes at a
trusted clock instant and return an `AuthorizationDecision`), plus the contract models,
canonicalization, validation, builders, and identifiers from G1.

The concrete OpenCare authorization adapter — today `OpenCareAuthorizationAdapter` in
`app/agent_trust/authorization.py`, which wraps `FamilyAccessService` and queries live
actor/credential/assignment/consent state — **moves to `app/agent/trust_adapter.py`**. The move
is a clean cutover: no shim or re-export remains in the generic layer, and the generic layer
holds no health-specific authority code. The adapter implements the generic Protocol; it
remains the only bridge from Family Access into the trust contract, and it still "adapts"
decisions rather than becoming a second authorization system, exactly as G1 §3 specified.

G2's runtime (`app/agent/g2_runtime.py`) and G3's provider boundary
(`app/agent/providers/`) are health-runtime-side and stay where they are; G4 does not move them.

## 4. Public trust API

`app/agent_trust/api.py` is the single public entry point for downstream consumers. It
re-exports the stable, versioned concepts without exposing OpenCare internals:

- contract models — `TrustEnvelope`, `ExecutionReceipt`, `AuthorizationSnapshot`,
  `AuthorizationDecision`, `SafetyDecision`, `FinalDecision`, `EvidenceItem`,
  `ProviderDisclosure` (as specified in G1 §5);
- canonical helpers — canonical JSON, normalization, `canonical_bytes`, `sha256_hex`,
  strict JSON parsing (G1 §6);
- validators — `validate_envelope_bytes`, `validate_receipt_bytes`, stable reason codes
  (G1 §8, §10);
- trusted builders — the `TrustedEnvelopeBuilder` and its typed request; parsing JSON never
  confers authorization (G1 §7);
- the `AuthorizationAdapter` Protocol (§3 above); and
- controlled identifiers — purpose/action/tool registries (G1 §4).

The API is the stable import surface. Implementations must not require consumers to reach into
`models.py`, `builders.py`, etc. directly; the module exists to make the trust contract a
documented, testable, portable dependency. Nothing new is invented here — `api.py` is an
aggregation and stabilization of the existing G1 contract surface.

## 5. Versioned schema export

`schemas/agent-trust/` holds versioned JSON Schemas generated deterministically from the
G1 contract models by `scripts/export_agent_trust_schemas.py`:

- one file per contract version, named from the versioned `contract_version` literal, e.g.
  `schemas/agent-trust/opencare-trust-envelope-1.schema.json` and
  `schemas/agent-trust/opencare-execution-receipt-1.schema.json`;
- the generator is deterministic: identical inputs produce identical bytes on every platform
  (same OS/locale/newline independence rule as G1 §6 canonicalization);
- a **drift test** regenerates the schemas and asserts the committed files are byte-identical,
  so committed schemas cannot silently diverge from the models;
- the exported schemas describe the existing contracts; they **do not** introduce a new schema
  version and do not change `contract_version` values. G1's literal-version rule (§13)
  continues to govern evolution: any semantic change requires a new contract version, never a
  reinterpreted one.

The schemas are the offline, language-neutral face of the trust contract for downstream
packagers and validators.

## 6. Fixture contract

`fixtures/agent-trust/` is the public, committed fixture corpus for the trust contract,
organized into the categories the trust contract can produce:

- `allowed/` — authorized requests that yield a valid, verifiable Envelope (and matching
  Receipt where applicable);
- `refused/` — requests denied or refused, with the stable reason codes (G1 §10), never a
  look-executable Envelope;
- `unsupported/` — structurally invalid or non-canonical inputs (duplicate keys, BOM, unknown
  fields, wrong versions) that must fail validation.

Fixture rules:

- **All synthetic and offline.** No real Actor, Person, clinician, record, consent event,
  credential material, or raw health payload appears; content is generated deterministically.
- **Not authorization.** A fixture Envelope is a test vector, not a capability. Fixtures must
  document (in a machine-readable header or README) that a valid hash proves only integrity
  and deterministic identity and is not live authority — matching G1 §2 and §8. G2 rechecks
  everything live; no fixture can be executed as if authorized.
- **Deterministic regeneration.** A regeneration path (script and/or test) rebuilds the corpus
  and the drift test asserts committed bytes are unchanged, so the corpus is reproducible and
  reviewable.

The existing `tests/fixtures/agent_trust/` vectors remain the enforcement suite; the public
`fixtures/agent-trust/` corpus is the stable, documented, versioned distribution form of the
same contract.

## 7. Agent Plugins package structure

Researched upstream record (exact facts, quoted in §13):

- **Agent Plugins Specification 1.0.0** — repo `agentplugins/agent-plugins-spec`, inspected at
  commit `bd383552095128f6effe895b9257cfd580a6d179` (`bd38355`), 2026-08-06. Version 1.0.0 is
  the current published release (spec header "Spec Version: 1.0.0"; README "Agent Plugins
  Specification 1.0.0 is the current published release"). The repo has no release tags at
  inspection time; the version comes from the spec/README.
- **Agent Skills** — repo `agentskills/agentskills` (Apache-2.0), inspected at commit
  `69ef37e9424c0a7ea9dd2293b559e43ec8176379` (`69ef37e`), 2026-08-09. Normative document:
  `docs/specification.mdx`; reference validator: `skills-ref/`. No release tags at inspection
  time.

The G4 package is a **skill-only plugin** (no `mcp.json`), which the Agent Plugins spec
explicitly permits: §6.2 "If a fixed component location is absent, the client MUST NOT treat
that as an error." Layout:

```text
agent-plugins/opencare-trust/
├── plugin.json
└── skills/
    └── opencare-health-agent/
        └── SKILL.md
```

`plugin.json` conforms strictly to `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "opencare-trust",
  "version": "0.1.0",
  "description": "OpenCare portable trust package: authorized, Person-scoped health context for constrained agent use.",
  "repository": "https://github.com/KirillNedoboy/open-care-proof-kit",
  "license": "Apache-2.0",
  "keywords": ["opencare", "health", "trust", "consent", "agent"]
}
```

Only the ten permitted root fields appear (`$schema`, `name`, `version`, `description`,
`author`, `homepage`, `repository`, `license`, `keywords`, `extensions`); `name` satisfies the
plugin name constraints (§11); the skill directory is an immediate child of `skills/`; and the
skill frontmatter `name` matches its parent directory (`opencare-health-agent`), per the Agent
Skills spec. There is deliberately **no `mcp.json`** — see §12.

## 8. Skill source-of-truth strategy

The canonical skill source is the existing, reviewed `skills/opencare-health-agent/SKILL.md`
(committed at the repository root). G4 treats it as the **single source of truth**:

```text
skills/opencare-health-agent/SKILL.md   (canonical source, edited in place)
        │  deterministic packaging script (agent-plugins packaging step)
        ▼
agent-plugins/opencare-trust/skills/opencare-health-agent/SKILL.md   (committed copy)
        │  drift test
        ▼
byte-identical assertion
```

- The packaging script copies the canonical file (and any canonical bundled resources) into the
  plugin tree deterministically — same inputs, byte-identical output.
- The plugin copy is **committed**, not generated at install time; consumers receive a complete,
  self-contained package.
- **No symlinks.** The plugin tree must be fully self-contained real files; symlinks/junctions/
  reparse points are forbidden (Windows portability, and Agent Plugins §4.1 containment).
- A **drift test** asserts the committed plugin copy is byte-identical to the canonical source,
  so the two can never diverge. Editing the skill means editing the canonical file and running
  the packaging script; the script is the only writer of the plugin copy.

## 9. CLI contract

The trust CLI is exposed two ways, with one implementation:

- `opencare-trust` console entry (declared in `pyproject.toml` `[project.scripts]`, pointing at
  `app.agent_trust.cli:main`); and
- `python -m app.agent_trust.cli` (unchanged module path).

Exit codes are deterministic: `0` success; `1` verification failure or refusal; `2` argument/
usage errors. Machine output is JSON. Commands:

- `verify-envelope --envelope PATH [--at UTC]` — offline integrity/schema/invariant verification
  (G1 §8); never live authority.
- `inspect-envelope --envelope PATH` — verified, redacted summary; never prints payloads or
  credentials (G1 §11).
- `verify-receipt --receipt PATH --envelope PATH [--at UTC]` — Receipt integrity and Envelope
  subset constraints.
- `export-envelope` — unchanged from G1: constructs an Envelope **only** from the repository's
  synthetic/demo authority; it cannot accept an authorization decision, final decision, Envelope
  identity, or arbitrary Envelope JSON (G1 §11).
- `export-schemas` — offline, deterministic schema export to `schemas/agent-trust/`
  (§5); pure artifact generation.

There is **no live-authorization minting path** in this package: no command queries live Family
Access or session state, and no command turns arbitrary JSON into an authorized Envelope. The
synthetic export exists solely for offline testing and fixture regeneration.

## 10. Extension interfaces

Two extension points, both already defined; G4 documents and stabilizes them, it does not
rewrite them.

**Authorization adapter (generic).** `app/agent_trust/` defines the `AuthorizationAdapter`
Protocol — the single seam through which any downstream system supplies authorization truth to
the trust contract. The OpenCare implementation is `app/agent/trust_adapter.py` (§3), and its
`authorize(...)` returns an `AuthorizationDecision` (allow with snapshot, or deny with reason
codes). The trust package does not authenticate users and does not decide policy; the adapter
supplies the live decision, exactly as the G1 builder requires (G1 §7: "The public builder
accepts typed trusted inputs and authority adapters, not a caller-supplied decision").

**Provider adapter (health-runtime, G3).** The G3 extension point lives in
`app/agent/providers/contract.py` and is documented here, not duplicated:

```text
Trust Envelope / G2 projection
   → build_provider_execution_request (ProviderExecutionRequest: question, purpose/action,
     evidence projection, allowed tools/fields, output contract, instructions,
     disclosure constraints, prohibited operations)
   → AgentProvider.execute(request) -> ProviderExecutionResult
   → answer_conforms_to_schema / G2 answer validation (untrusted output)
   → ExecutionReceipt (observed facts only)
```

`AgentProvider` is the portability slot: switching providers is observationally indistinguishable
downstream except for provider/model identifiers (G3). The provider never receives
ProductCoreRuntime, repositories, DB connections, Family Access objects, credentials, session
stores, or the broad `AgentContext`; input is the exact projection, output is bounded and
validated, and no provider becomes a source of truth. `MAX_TOOL_ROUNDS = 1` and the
`EnvelopeToolMediator` rules from G2/G3 are unchanged. G4 adds nothing to this chain.

## 11. Package conformance rules

The committed `agent-plugins/opencare-trust/` package must satisfy all of the following,
enforced by conformance tests:

1. **plugin.json strict 1.0.0** — `$schema` equals the canonical identifier
   `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`; only the ten permitted root
   fields appear; no unknown fields; no `permissions`/`scopes`/`trust`/`consent`/`health`/
   `tools`/`capabilities` or other invented fields anywhere.
2. **Name constraints** — plugin `name` is 1–64 chars, lowercase alphanumeric plus `-`/`.`,
   alphanumeric start/end, no `--` or `..` (§5.5).
3. **Skills discovery** — skills are discovered from **immediate child directories** of
   `skills/`, each containing exactly a regular file named `SKILL.md`; no recursive descent
   (§7.1).
4. **Frontmatter valid** — `SKILL.md` frontmatter is well-formed YAML with the required `name`
   and `description`; optional fields conform to their constraints; body follows progressive
   disclosure.
5. **Name matches directory** — the skill frontmatter `name` must exactly match its parent
   directory name (`opencare-health-agent`).
6. **Package containment** — every packaged path resolves within the plugin root: no `..` or
   absolute escapes; symlink/junction/reparse-point targets outside the plugin root are
   rejected (§4.1). Package artifacts declare no plugin-relative path escaping the root.
7. **Secret/path scan** — the packaged tree contains no credentials, `.env`, private keys,
   tokens, absolute host paths, real person data, or raw health payloads (G1 invariant 13:
   "No secret, credential material, raw session token, filesystem path, or unselected raw
   source content").
8. **Deterministic build** — packaging the canonical source yields byte-identical output;
   the committed copy matches the canonical source (drift test, §8).
9. **No `mcp.json`** — the package is skill-only by design (§12).

## 12. Explicit MCP deferral and G5 handoff

**MCP deferral.** G4 deliberately ships **no `mcp.json`** and no MCP server. A future optional
read-only MCP adapter — exposing only Envelope-allow-listed, read-only operations behind the
same Person-scoped Envelope, G2 consent, evidence projection, and validation semantics — is
explicitly deferred until ecosystem demand is demonstrated (G5). MCP is a wire/transport layer,
not a trust model; it must not bypass or broaden any G1/G2/G3 invariant. Nothing in G4 claims
MCP support.

**G5 handoff.** G5 is **Sentient G5 — Evaluation and Ecosystem Validation**: install the
skill-only plugin in independent Agent Plugins-compatible clients, verify discovery,
conformance, and behavior across clients, gather ecosystem feedback, and only then evaluate
the optional read-only MCP adapter. G4 makes **no multi-client validation claim**; its
conformance evidence is the offline rules above plus the synthetic fixture matrix, not a claim
that any external client has loaded the package.

## 13. Upstream specification record

Exact quotes from the inspected upstream documents (recorded verbatim for the design record).

### 13.1 Agent Plugins Specification 1.0.0

- Repo: `https://github.com/agentplugins/agent-plugins-spec`; site `https://agent-plugins.org`.
- Inspected commit: `bd383552095128f6effe895b9257cfd580a6d179` (short `bd38355`), dated
  2026-08-06. Version: **1.0.0** ("Spec Version: 1.0.0"; "Agent Plugins Specification 1.0.0 is
  the current published release"). No release tags on the repo at inspection time.
- **Manifest `$schema`** (§5.2): "For Agent Plugins 1.0.0, its value MUST be the canonical
  identifier `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`." (Schema `$id`:
  same; `$schema` property is a `const`.)
- **Allowed root fields** (§5.2): "Its schema is closed: the only permitted top-level fields
  are `$schema`, `name`, `version`, `description`, `author`, `homepage`, `repository`,
  `license`, `keywords`, and `extensions`." Required: `$schema` and `name` (§5.3); every other
  field optional (§5.4); `additionalProperties: false` in the machine schema.
- **Name constraints** (§5.5): 1–64 characters; character set `a-z`, `0-9`, `-`, `.`; first and
  last characters alphanumeric; no consecutive hyphens (`--`) or consecutive periods (`..`).
  "Periods are allowed in plugin names." Schema pattern:
  `^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$`.
- **Skill-only package** (§6.2): "If a fixed component location is absent, the client MUST NOT
  treat that as an error." — `mcp.json` is therefore optional; a plugin with only skills is
  conformant.
- **Package layout** (§4.2, §6.1): manifest at `plugin.json` in the plugin root; fixed
  component locations are `skills/` ("Subdirectories containing `SKILL.md`") and `mcp.json`.
- **Skills discovery** (§7.1): "The fixed discovery location is `skills/`. Each immediate child
  directory containing a path named exactly `SKILL.md` that resolves to a regular file is
  treated as one skill. Clients MUST NOT recursively search deeper descendants for additional
  skills." Skill format is defined by the Agent Skills specification ("That specification is
  the source of truth for the `SKILL.md` format, frontmatter fields, and directory layout
  (`scripts/`, `references/`, `assets/`)").
- **Containment** (§4.1): "When a client discovers, reads, or executes a file or directory
  supplied by the plugin package, the filesystem-resolved path MUST remain within the
  filesystem-resolved plugin root. Symlinks, junctions, reparse points, and equivalent
  filesystem mechanisms MAY resolve to targets within the plugin root, but clients MUST reject
  package paths that resolve outside it."
- **Unknown fields** (§5.2): "If `plugin.json` contains any other top-level field, it does not
  conform to the schema." Clients report and ignore unknown fields; our conformance rule is
  stricter: we never emit them and our validator rejects non-conforming manifests.
- **Versioning** (§10): clients MUST NOT silently downgrade or reinterpret one version as
  another; unsupported versions are rejected.

### 13.2 Agent Skills

- Repo: `https://github.com/agentskills/agentskills`; site `https://agentskills.io`; Apache-2.0.
- Inspected commit: `69ef37e9424c0a7ea9dd2293b559e43ec8176379` (short `69ef37e`), dated
  2026-08-09. Normative: `docs/specification.mdx`; reference validator: `skills-ref/` (a
  community validator also exists at `agent-ecosystem/skill-validator`). No release tags on the
  repo at inspection time.
- **Required frontmatter** — only `name` and `description` are required. Optional fields:
  `license`, `compatibility`, `metadata`, and `allowed-tools` (marked "Experimental").
- **`name`** — "Must be 1-64 characters"; "May only contain unicode lowercase alphanumeric
  characters (`a-z`, `0-9`) and hyphens (`-`)"; "Must not start or end with a hyphen";
  "Must not contain consecutive hyphens (`--`)"; **"Must match the parent directory name."**
- **`description`** — "Must be 1-1024 characters"; "Should describe both what the skill does
  and when to use it"; "Should include specific keywords that help agents identify relevant
  tasks."
- **`$schema` for SKILL.md** — none defined; SKILL.md has no `$schema` field in the format.
- **Progressive disclosure** — metadata (`name`/`description`, ~100 tokens) loaded at startup;
  the `SKILL.md` body loaded on activation ("< 5000 tokens recommended", "Keep your main
  `SKILL.md` under 500 lines"); `scripts/`, `references/`, `assets/` loaded on demand; "Keep
  file references one level deep from `SKILL.md`."
- **Validation** — `skills-ref validate ./my-skill` checks frontmatter validity and naming
  conventions.

### 13.3 Spec discrepancy note

The task baseline (plugin.json with `$schema`/`name`/`description`/`repository`/`license`/
`keywords`, and no invented `permissions`/`scopes`/`trust`/`consent`/`health`/`tools`/
`capabilities`) matches the actual 1.0.0 spec: all baseline fields are permitted root fields
and the schema is closed, so any invented field is non-conformant. No material discrepancy was
found. One nuance recorded: Agent Plugins §5.2 says clients "MUST report and ignore" unknown
top-level fields rather than fail the plugin, while the machine schema has
`additionalProperties: false`; G4 adopts the strict interpretation (we never emit unknown
fields, and our own validator rejects them).

## 14. Acceptance boundary

The G4 implementation must deliver:

- `app/agent_trust/api.py` (stable public surface, §4) and the generic layer free of OpenCare
  imports (§3);
- `app/agent/trust_adapter.py` (clean move of the OpenCare authorization adapter; no shim in
  the generic layer, §3);
- `schemas/agent-trust/*.json` + `scripts/export_agent_trust_schemas.py` + drift test (§5);
- `fixtures/agent-trust/` (allowed/refused/unsupported; synthetic, offline, not-authorization;
  deterministic regeneration, §6);
- `agent-plugins/opencare-trust/` (plugin.json + `skills/opencare-health-agent/SKILL.md`;
  skill-only, no `mcp.json`, §7);
- deterministic packaging script + drift test from the canonical skill source, no symlinks (§8);
- `opencare-trust` console entry plus unchanged `python -m app.agent_trust.cli`, deterministic
  exit codes, no live-authorization minting path (§9);
- conformance tests for all of §11; and
- existing G1/G2/G3 tests, Ruff, strict mypy, and the existing pytest suite passing; the G1
  canonical-vector requirement (same bytes and digest on Windows and Linux) still holds.

G4 does **not** add: an MCP server or `mcp.json`; a new contract/schema version; live-authority
CLI minting; signatures/PKI/attestation/transparency; new providers or consent semantics;
multi-client validation claims (deferred to G5); or any change to G1/G2/G3 trust behavior.
