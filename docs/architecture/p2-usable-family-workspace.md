# P2: Usable Family Workspace

- Status: Design binding (implementation phase begins on `codex/p2-usable-family-workspace`)
- Branch: `codex/p2-usable-family-workspace` (from `54192207d9ae8b55931c040e291f257dc14ad8ca`)
- Decision owners: OpenCare maintainers
- Scope: reframe the Visit Preparation Workspace into an "OpenCare Health Workspace" — a capability-aware, Person-switch-safe, readable Personal/Family Health Workspace — with a unified review inbox, current/historical record semantics, human-readable provenance, a readable timeline, usable Visits + Visit Brief with three-type evidence, and a v3 export filename. P2 is UX/product only: **no** schema migration (Product Core stays at v7), **no** portable vault v4, **no** Visit Brief v3, **no** family-access-v3, **no** G1 contract change, **no** document upload/OCR/model extraction, **no** genetics/PGx, **no** new trust layer, **no** SPA framework, **no** new JS runtime dependencies, **no** backend authorization relaxation (the UI capability map is advisory presentation only; the server stays authoritative).

This document is the implementation contract for P2. Every acceptance criterion at the end is judged against the concrete decisions below.

## Verified baseline (2026-08-20, commit `54192207d9ae8b55931c040e291f257dc14ad8ca`)

- Worktree clean; `HEAD` == `origin/main` == `54192207d9ae8b55931c040e291f257dc14ad8ca`; tags exactly `v0.1.0`, `v0.2.0`.
- `app/product_core/migrations.py`: `PRODUCT_MIGRATIONS` contains v1..v7; latest version == **7**.
- `app/family_access/policy.py`: `POLICY_VERSION == "family-access-v2"`, `V1_POLICY_VERSION == "family-access-v1"` (frozen legacy). `RECORD_READ_SCOPES = {"condition.read", "lab.read"}`, `RECORD_WRITE_SCOPES = {"condition.write", "lab.write"}`, `V2_ONLY_SCOPES = RECORD_READ_SCOPES | RECORD_WRITE_SCOPES`; `OWNER_SCOPES_V2 = OWNER_SCOPES_V1 | RECORD_READ_SCOPES | RECORD_WRITE_SCOPES`; `CAREGIVER_BASE_SCOPES_V2 = CAREGIVER_BASE_SCOPES_V1 | RECORD_READ_SCOPES`; `CAREGIVER_OPTIONAL_SCOPES_V2 = CAREGIVER_OPTIONAL_SCOPES_V1 | RECORD_WRITE_SCOPES`.
- `app/product_core/portable_vault_export.py`: `PORTABLE_VAULT_FORMAT_VERSION == 3`; `PRODUCT_CORE_SCHEMA_VERSION == PRODUCT_MIGRATIONS[-1].version`.
- `app/product_core/persisted_visit_briefs.py`: `CONTENT_SCHEMA_VERSION == 2`, `SUPPORTED_CONTENT_SCHEMA_VERSIONS == frozenset({1, 2})`, `RENDER_VERSION == 1`.
- `docs/project-status.md`: G5 machine state `READY_FOR_SECOND_CLIENT_SMOKE`.
- Current workspace surface: `app/templates/product_core_workspace.html` titled "Visit Preparation Workspace · OpenCare"; `app/static/product_core_workspace.js` (one 545-line IIFE); export `Content-Disposition` filename `opencare-person-vault-v2.zip` (server, `app/product_core/api.py`) and `link.download = "opencare-person-vault-v2.zip"` (client, `product_core_workspace.js`); `GET /people/{person_id}/medications|conditions|labs` each accept `include_inactive: bool = False`; canonical listing filters `is_active = 1` unless `include_inactive` is true.

---

## 1. Current UX problem

The current workspace page is framed as a **Visit Preparation Workspace** — one long sequential list of forms/sections. Known debts, each of which P2 must address:

1. **Wrong framing.** The page title and framing ("Visit Preparation Workspace") present a narrow preparation tool, not the family health workspace the installation actually is.
2. **Single long column.** All sections stack into one sequential column with no hierarchy, overview, or navigation; there is no way to jump to a section.
3. **Medication is structurally special.** Medication is a structurally baked-in HTML section, while conditions and labs are dynamically built by JS — inconsistent rendering, inconsistent behavior, duplicated logic.
4. **Probe-based discovery.** `app/static/product_core_workspace.js` uses probe requests (401/403/404) to discover whether condition/lab families are accessible, instead of asking the server once for a capability map.
5. **Blanket `enableWorkspace()`.** All controls are enabled at once regardless of the Actor's actual scopes; capability state is not derived from the server per Person.
6. **`include_inactive` not requested on normal loads.** Condition/lab (and medication) lists are loaded without `include_inactive=true`, so historical/superseded records are invisible in the UI even though the backend supports them.
7. **Medication history inconsistency.** History lists exist for conditions/labs but medication history is not rendered consistently with them.
8. **JSON-first provenance.** Provenance is rendered as raw `JSON.stringify(provenance_locator)` — not human-readable, leaks structure, and is the primary presentation.
9. **Stale Brief selector wording.** The Brief evidence selector is a fieldset titled "Select confirmed medication evidence" with only `brief-medication-options`, even though Visit Brief content schema v2 supports medication/condition/lab selections.
10. **Monolithic JS.** One 545-line IIFE mixes discovery, rendering, review, history, Brief, and export logic with no conceptual separation.
11. **Export filename drift.** The download uses `opencare-person-vault-v2.zip` while the portable vault format is v3 — user-visible filename contradicts the actual format version.

## 2. User roles

The UI must reflect the current Actor's own rights on the selected Person without revealing any other Actor's rights, assignment structure, or hidden data.

- **Owner** — broad read/write/review/export: sees full workspace (Person context, Overview, Review, all three record families, Timeline, Visits & Brief, Export) with write/review/export controls.
- **Caregiver with bounded write authority** — base read scopes plus whatever optional write scopes were granted (e.g., `medication.write`, `visit.write`, `brief.write`, `candidate.review`, `vault.export`); sees only the controls its scopes justify, in the families it can read.
- **Read-only caregiver** — sees only read surfaces; no enabled write/review/export action anywhere (a disabled-looking but server-rejected action is a bug; see §5, §21).
- **Legacy family-access-v1 Actor** — assigned under the frozen v1 scope sets; MUST NOT gain Condition/Lab UI access (no `condition.read`/`lab.read`/`condition.write`/`lab.write` — those scopes exist only in v2 sets). The condition/lab sections are not rendered, not probed into existence, and not reachable by direct HTTP (server rejects).
- **Revoked Actor** — the next API request fails closed (403/404 per §14); the UI must surface the changed state and refresh its capability map, never silently keep rendering controls that will now fail.

Invariant: **no role surface reveals another Actor's existence, assignments, scope sets, or hidden counts.** The capability endpoint (§5) returns only the current Actor's booleans for the selected Person.

## 3. Core task flows

The workspace must answer the ten mission questions, each as a first-class flow:

1. **Whose workspace is this?** Selected Person is always obvious (persistent Person context bar; §4, §24).
2. **What needs review?** Review inbox (§7) defaulted to pending across every accessible fact family.
3. **What are the current confirmed facts?** Records sections (§8) showing current canonical records only by default, per family, labeled "Current record".
4. **What historical/superseded records exist?** Same sections, historical records loaded via `include_inactive=true` and shown collapsed/secondary, labeled "Historical record"/"Superseded record".
5. **Where did this fact come from?** Provenance panel (§9) per record/candidate: human-readable source lineage via progressive disclosure.
6. **What changed over time?** Timeline (§10): readable record history with distinct date semantics.
7. **Which Visits are being prepared?** Visits list (§11) with deterministic sorting; scheduled and unscheduled Visits both valid.
8. **What does the current Visit Brief say / what evidence is selected?** Visit Brief view (§11) with revision history, v2 selections restored, v1 revisions readable.
9. **What actions am I allowed to take?** Capability-aware controls (§5) derived from the server, not from probes; no misleading enabled write controls.
10. **Family Person switching without stale/foreign data?** Person switcher with the generation/cancellation privacy model (§6).

## 4. Information architecture

- **Reframe**: the page is renamed to **"OpenCare Health Workspace"** (personal/family health workspace), replacing the "Visit Preparation Workspace" title and framing. The route and template file names may stay (`/workspace`, `product_core_workspace.html`), but all visible framing, headings, and `<title>` change.
- **Section order** (fixed): **Person context → Overview → Review → Records (Medications, Recorded conditions, Labs) → Timeline → Visits & Visit Brief → Export**.
- **Rendering model**: server-rendered HTML + vanilla JS. No SPA, no framework, no bundler.
- **Navigation**: a compact internal section navigation using normal anchor links to section `id`s (smooth-scroll via CSS `scroll-behavior` respecting `prefers-reduced-motion`). **No complex ARIA tab widget** — plain anchors with standard heading semantics.

## 5. Capability-aware UI contract

New read-only endpoint:

```
GET /api/product-core/v1/people/{person_id}/workspace-capabilities
```

Closed, stable response shape (exactly these keys; adding a key is a breaking change requiring endpoint version bump):

```json
{
  "person_id": "<string>",
  "capabilities": {
    "person_update": bool, "source_write": bool, "candidate_review": bool,
    "medication_read": bool, "medication_write": bool,
    "condition_read": bool, "condition_write": bool,
    "lab_read": bool, "lab_write": bool,
    "timeline_read": bool,
    "visit_read": bool, "visit_write": bool,
    "brief_read": bool, "brief_write": bool, "brief_export": bool,
    "vault_export": bool,
    "chat_use": bool
  }
}
```

Each boolean maps 1:1 to the existing scope string of the same name (`person_update` → `person.update`, `medication_write` → `medication.write`, etc.) for the **current Actor's assignment on that Person** (v1 or v2 sets; no inference of v2 for v1 grants). `candidate.read` is a precondition for inbox listing but is present in every role's base set and is NOT part of the response shape.

Requirements and invariants:

- Requires a **visible Person**: hidden Person → **404** (same privacy semantics as all Person-scoped endpoints).
- Returns **only the current Actor's capabilities** on that Person. NO other-Actor information, NO assignment history, NO Family membership names, NO hidden counts, NO policy internals, NO scope lists (booleans only).
- **Performs no mutation.** Read-only endpoint; no audit event required beyond normal request handling.
- **Never replaces server-side authorization.** Explicitly forbidden: "if UI says allowed → skip backend authorization." The map is advisory for rendering only; every mutation endpoint keeps its existing `require_*` checks unchanged.
- **TOCTOU contract**: capability visible → assignment revoked → the mutation attempt MUST still be denied by the backend; on denial the UI must refresh its capability state and re-render (§14, §21).
- `person.read` remains the implicit precondition for the endpoint itself; a Person the Actor cannot read never returns a capability payload.
- The UI renders condition/lab sections **only** when `condition_read`/`lab_read` are true; it never probes for them, never renders them for v1 Actors.

## 6. Person-switch privacy model

- **Workspace generation**: the client maintains a monotonically increasing workspace epoch (`generation`). Every Person-scoped request is bound to the generation in which it was issued.
- **Cancellation**: on Person switch, the client calls `AbortController.abort()` on all in-flight Person-scoped requests and increments the generation.
- **Stale-response drop**: when a response resolves, if its captured generation != current generation, it is **silently dropped** — never rendered, never merged, never surfaced as an error. Switching Alice→Bob must make it impossible for a delayed Alice response to render into Bob's workspace.
- **State clear on switch**: selected Visit, Brief revision, correction form, source details, export action, pending async status, review filters — all Person-specific interactive state is cleared (or re-initialized from the new Person's data). Dirty preparation notes follow §11's unsaved-warning rule; the warning is shown before the switch clears the draft, and the switch is not blocked by default.
- **Staleness is silent and safe**: no partial render, no error toast claiming failure; the dropped response simply has no effect.
- **Browser state is never an authorization source.** No client-side "family database"; no caching of other People's data in memory beyond the currently selected Person's loaded workspace.
- **Person list**: server-filtered only — the list endpoint returns accessible People only: no inaccessible members, no hidden counts, no Actor/assignment IDs, no private relationship data.

## 7. Review inbox behavior

- **First-class workflow**: a Review section (default view = **pending**) across every accessible fact family (medication, condition, lab). Not an afterthought of the records lists.
- **Filters**: fact type (All / Medication / Condition / Lab — only families the Actor can read), status (Waiting for review / Confirmed / Corrected / Rejected / Unsupported by source), optional local text search. Filters are local to the loaded inbox data; no new server endpoint is required (existing candidate listing is reused).
- **Status labels** (display-only mapping; stored literals unchanged):

  | Stored | UI label |
  |---|---|
  | `pending` | "Waiting for review" |
  | `confirmed` | "Confirmed" |
  | `corrected` | "Corrected" |
  | `rejected` | "Rejected" |
  | `unsupported` | "Unsupported by source" |

- **Review card** shows: fact type, proposed values, source reference, provenance (§9), creation time, correction predecessor if any (i.e., "correction of <original record>"), current status.
- **Lab card**: shows result/unit/reference-range/observed-date/source-flag; the flag is marked **"(as reported)"**. **No interpretation** (see §19).
- **Condition card**: shows "Recorded condition", `status_text` marked as source text, onset date described as **"Onset date (as recorded)"**. **No interpretation.**
- **Action gating** (backend enforces; UI renders per capability map):
  - **Confirm** → requires `candidate.review` **plus** the corresponding fact-family write scope (`medication.write` / `condition.write` / `lab.write`).
  - **Reject** → requires `candidate.review`.
  - **Mark unsupported by source** → requires `candidate.review`.
  - **Create correction** → uses the existing backend correction authority for the fact family (e.g., `medication.write` via the existing correction endpoint). **Do not invent broader rights.**
- **Action language** (exact UI strings): "Confirm record", "Reject candidate", "Mark unsupported by source", "Create correction". Forbidden wording: "Approve diagnosis", "Validate medical result", "Confirm treatment".

## 8. Record / current / history semantics

- **`is_active` semantics**: canonical `is_active` means **current canonical record vs superseded historical record** (lifecycle currency), NOT disease/lab clinical activity. UI wording: **"Current record"**, **"Historical record"**, **"Superseded record"**. Forbidden as interpretation: "Active disease" / "Resolved condition" — unless that exact wording is source text inside `status_text` (then it is quoted source text, never endorsed).
- **Loading**: where read access exists, Medication, Condition, and Lab lists are loaded with `include_inactive=true` on normal loads, then separated **client-side** into current vs historical. (Backend contract unchanged; this is a client call-parameter fix.)
- **Presentation**: historical records are collapsed / visually secondary by default; expanding shows the full record plus why it was superseded.
- **Correction chain**: original record → correction candidate → replacement current record. The chain must be understandable in the UI (the correction candidate references its predecessor; the superseded record references its replacement), without using raw internal IDs as the primary explanation (IDs may remain in metadata/details).

## 9. Provenance presentation

- **Human-readable source lineage panel** via progressive disclosure (`<details>`/`<summary>` where appropriate), shown for candidates and records.
- Panel content: source ID + secondary metadata, source type, created/registered time, SHA-256 content hash, provenance locator in **human-readable form**, correction lineage where applicable.
- **Raw locator JSON is NOT the primary presentation** (may appear inside details as secondary technical detail at most).
- New narrowly scoped, metadata-only endpoint (reusing/extending the safe `SourceResponse` shape):

```
GET /api/product-core/v1/sources/{source_id}
```

Response shape: `source_id`, `source_type`, `content_hash`, `size_bytes`, `media_type`, `created_at`, `integrity_verified`.

- `integrity_verified`: **true only if the immutable payload hash has been verified** (prefer verifying before reporting true). On verification failure: **fail closed** with a generic Product Core integrity error (§14 maps 500 → "integrity: stored evidence could not be verified"); never silently display unverifiable provenance.
- **MUST NOT return**: filesystem `relative_path`, absolute paths, raw source payload, unrelated provenance internals, or another Person's ID/data.
- **Security**: resolve source ownership **server-side**; require `source.read`; hidden or foreign source → **404**; never trust a client-supplied Person association; no new source scope needed; do **NOT** silently expand `source.read` into raw-source download capability.
- **No raw source-content viewer in P2**: no arbitrary plain-text payload preview for caregivers; a richer viewer belongs to the future document-ingest design. (Record-level detail fields already shown by the workspace are not affected.)

## 10. Timeline presentation

- Readable record history rows: date/time, fact type, human-readable action, record title, source link/details.
- **Event code → neutral UI language** (display-only mapping; stored event codes unchanged):

  | Stored event code | UI label |
  |---|---|
  | `medication_confirmed` | "Medication record confirmed" |
  | `condition_confirmed` | "Condition record confirmed" |
  | `lab_confirmed` | "Lab record confirmed" |
  | `*_corrected` | "Record superseded by reviewed correction" |

- **Date-semantics separation** (distinct labels, never conflated):
  - `event_at` → lifecycle timestamp labeled **"Recorded in OpenCare"**.
  - condition `onset_date` → labeled **"Onset date (as recorded)"**.
  - lab `observed_date` → labeled **"Observed date (as reported)"**.
  - scheduled Visit date → labeled **"Scheduled visit"**.
- **Filters**: simple local filters All / Medication / Condition / Lab.
- **Never mix scheduled Visits into canonical record-event semantics**; if Visits appear on the timeline they are labeled separately ("Scheduled visit"), never presented as record lifecycle events.

## 11. Visit preparation workflow

- **Flow**: Visits list → selected Visit → Questions → Visit Brief.
- **Deterministic sorting** of the Visits list (stable key, e.g., scheduled date then creation time then ID); scheduled Visits show title/specialist/scheduled date; unscheduled Visits remain valid and clearly labeled.
- **Capability separation (do not conflate)**:
  - `visit.read` → list/view Visits + Questions.
  - `visit.write` → create/edit Visit + add/edit/reorder/remove Questions.
  - No editing controls in read-only mode.
  - `brief.read` → view Brief + revision history + eligible evidence.
  - `brief.write` → initialize/validate/generate/preparation-note revision/restore.
  - `brief.export` → audited/download export.
- **Evidence selector**: wording changed from "Select confirmed medication evidence" to **"Select confirmed evidence"**; eligible evidence grouped visually by **Medications / Recorded conditions / Labs** with enough identifying info; **no interpretation**. Only **active confirmed records**, **same Person only**.
- **Revisions**: v1 Brief revisions remain readable (content schema v1, immutable); current v2 selections **pre-select correctly** when rendering an existing Brief; viewing a historical revision **never mutates** it.
- **Source/provenance** inspectable from Brief evidence (§9).
- **Unsaved preparation-notes warning remains**; Person switch clears dirty state safely (§6).
- **Staleness UX** (neutral language, backend reason/state as source of truth): "Current" / "Evidence changed since this revision" / "Selected record or source changed" / "Revision unavailable". **Never silently regenerate a stale Brief** — the user explicitly generates a new revision.
- **NO Visit Brief schema v3** for presentation-only changes.

## 12. Overview

Compact summary for the selected Person, showing **only already-authorized, already-loaded information**:

- Records waiting for review (count, from the inbox data).
- Current Medication count.
- Current Condition count — **only if `condition_read`**.
- Current Lab count — **only if `lab_read`**.
- Visit count / selected Visit (if `visit_read`).
- Latest record-history items (if `timeline_read`).

Forbidden: counts for inaccessible fact families; hidden-Person totals; guessed installation totals. No value in the Overview is a medical interpretation (a count of confirmed records is not health advice).

## 13. Export

- Portable vault format stays **v3** (`PORTABLE_VAULT_FORMAT_VERSION == 3`); no v4.
- **Fix filename drift**:
  - Server `Content-Disposition` filename becomes `opencare-person-vault-v3.zip`, generated **from `PORTABLE_VAULT_FORMAT_VERSION`** (single source of truth server-side — no hand-written "v2"/"v3" literal in the API handler).
  - Browser respects the safe server Content-Disposition filename, **sanitizes** it before assigning `link.download` (strip path separators, control characters, leading dots; ensure `.zip` suffix), with a safe v3 fallback constant in exactly **one** client location.
  - Avoid duplicating version strings in multiple UI layers: the client must not hardcode the filename in several places; a drift regression test (§23) asserts the server filename version equals `PORTABLE_VAULT_FORMAT_VERSION` and that the UI never presents a mismatched version.
- Preserve: explicit warning, deliberate confirmation, `vault.export` scope check, server audit, same-Person isolation.
- If `vault_export` is false, **no enabled export action is rendered**.
- **NO import in P2.**

## 14. Error UX

Privacy-safe user-facing mapping (no hidden Person IDs, policy internals, SQL errors, source paths, filesystem paths, or stack traces ever rendered):

| HTTP | UI message |
|---|---|
| 401 | "Sign in required" / "Your session has expired. Sign in again." |
| 403 | "This action is no longer available" / "You don't currently have permission for this action." |
| 404 | "This profile or record is not available." |
| 409 | "This record changed. Refresh to see the latest version." |
| 422 | "Check the entered values and try again." |
| 500 | "Integrity: stored evidence could not be verified." |
| 503 | "Local Product Core storage is unavailable. Try again shortly." |

Unknown/unexpected statuses fall back to a generic neutral error without technical detail. §21's regression list includes the denial paths.

## 15. Loading states

Five explicit states per section/surface: **initial Person list loading → Person workspace loading → loaded → empty → error**. In addition:

- Action pending/disabled: only controls relevant to the in-flight operation are disabled (no blanket form freeze).
- Empty state is informative ("No records waiting for review", "No recorded labs yet") and never mistaken for error.
- **Never leave buttons permanently disabled after a failed request** — on failure, re-enable the control and surface the §14 error.

## 16. Accessibility

- Semantic headings (`h1`–`h3` in order); visible labels on all inputs.
- Buttons with correct `type` (default `button` unless submitting).
- `aria-live="polite"` status regions where async state changes (e.g., workspace load, review action results).
- Focus restored after correction/cancel (return focus to the originating control).
- Visible focus indicator on all interactive elements.
- No color-only status indication (status badges always include text, §7 labels).
- Minimum 44px button target (at least 44×44 CSS px hit area).
- Forms usable without pointer precision (large targets, correct labels, keyboard order).
- `<details>` provenance keyboard-usable (native details/summary keyboard behavior is preserved; no custom re-implementation).
- `prefers-reduced-motion` preserved (no forced animation; smooth-scroll disabled).
- Normal HTML semantics preferred; no custom complex ARIA widget (per §4, no tab widget).

## 17. Responsive design

- Existing no-framework approach retained. No Bootstrap/Tailwind/React/Vue; no new UI runtime dependency.
- Desktop: useful two-column/grouped layouts; records and summary cards readable without excessive scrolling.
- Mobile: one column; no horizontal overflow; actions wrap vertically; source hashes/IDs wrap safely; Visit Brief Markdown remains scrollable/readable.

## 18. Visual hierarchy

Restrained product hierarchy, not dashboard:

- Workspace context bar (Person context + switcher), section navigation, summary cards, record cards, status badges **with text** (§7 labels), `<details>` for provenance/history, grouped form actions.
- Avoid: dashboard gimmicks, clinical red/yellow/green severity coding, interpretation badges, decorative medical scoring, fake urgency. Nothing in P2 communicates "good"/"bad" clinical states.

## 19. Safety language

- **Lab**: show Result / Unit / Reference range / Flag **(as reported)** without transforming them into "abnormal", "dangerous", "healthy", or "likely disease" — unless exact words are source-provided text (quoted as source text, never endorsed).
- **Condition**: "Recorded condition", never "OpenCare diagnosis".
- **Medication**: a confirmed record means a reviewed, source-backed record exists — never "OpenCare recommends taking it". No start/stop, substitution, dosing, or medication-selection advice.
- No value shown anywhere is a medical recommendation or interpretation.

## 20. Frontend code structure

Refactor `app/static/product_core_workspace.js` for maintainability with conceptual separation. May remain one JS file if modular functions are clear; splitting into multiple plain-browser-JS files is allowed. **No frontend build system, no bundler, no npm runtime dependency.**

Conceptual modules (function/namespace boundaries, not necessarily files):

1. request/error/CSRF helpers (including generation-tagged fetch + AbortController, §6)
2. workspace state (selected Person, generation, loaded data, capability map)
3. capability handling (apply capability map to controls; refresh on denial)
4. Person loading/switching (list, select, generation bump, state clear)
5. record rendering (Medications / Recorded conditions / Labs; current vs historical, §8)
6. review rendering (inbox, filters, actions, §7)
7. provenance rendering (§9)
8. timeline rendering (§10)
9. Visit/Brief rendering (Visits, Questions, Brief, revisions, evidence, staleness, §11)

Server-rendered template structure may also be split into Jinja partials if that reduces duplication, staying within the existing server-rendered + vanilla JS model.

## 21. Security principles

**"Hiding a button is not authorization."** Every P2 route keeps the existing server authorization untouched. Regression examples that must hold:

- Hidden Person still returns 404 (capability endpoint and all Person-scoped routes).
- Guessed record still returns 404.
- Guessed source metadata still returns 404 (foreign/hidden source).
- Read-only caregiver cannot mutate by direct HTTP (POST/PATCH/DELETE rejected even though read UI renders).
- Legacy v1 Actor still cannot read Condition/Lab (no v2 scopes in a frozen v1 grant; server rejects; UI never renders those sections).
- Revocation affects the very next API call (fail closed).
- Install admin without a Person assignment has no Person authority.
- A stale UI capability can never bypass the backend (TOCTOU, §5).
- Person switch cannot cause cross-Person rendering (§6).
- No hidden counts in the Overview (§12).

## 22. Non-goals

Explicitly out of scope for P2: document upload, PDF ingestion, OCR, image extraction, model/LLM extraction, automatic entity recognition, FHIR, HL7, EHR sync, cloud sync, new health fact families, diagnoses, treatment recommendations, medication recommendations, dosage guidance, lab interpretation, unit conversion, abnormality inference, genetics, PGx expansion, MCP, EvoSkill, new Sentient adapter, new model provider, multi-agent architecture, new public identity system, mobile native app, SaaS deployment.

Additionally: **no migration v8 for UI preferences** (workspace preferences remain ephemeral/client-side); **no family-access-v3**; **no changes to frozen v1 scope sets**; **no silent v1 upgrades**; **no modification of historical consent events**.

## 23. Test strategy

### Backend tests

- **Workspace capabilities endpoint**: v2 owner (all 17 booleans true); v2 caregiver with optional scopes (exactly those true); read-only caregiver (write/review/export false); legacy v1 grant (condition_read/lab_read/condition_write/lab_write all false); install admin without assignment (404 or no Person surface); revoked assignment (fail closed immediately).
- **Source metadata endpoint**: same-Person authorized read returns the closed shape; wrong-Person request → 404; missing `source.read` with visible Person → 403; hidden Person/source → 404; tampered source payload → `integrity_verified: false` path fails closed with generic integrity error (or the request fails); response contains no `relative_path`/absolute path/raw payload/other-Person metadata.
- **Current/historical record lists**: `include_inactive=true` returns superseded records for all three fact types; default remains current-only; API regression.
- **Visit Brief evidence grouping**: evidence options include medication/condition/lab; same-Person only; active-confirmed-only.
- **Export filename v3**: server filename derived from `PORTABLE_VAULT_FORMAT_VERSION`; drift test asserts filename version == format version; client fallback constant matches.
- **Product Core API regressions** and **P1/G1–G5 regressions** (existing suites stay green; no G1 contract change).

### Workspace (frontend/behavior) tests

Only accessible People presented; inaccessible fact family not loaded/rendered; read-only user has no enabled write action; owner sees allowed write controls; pending default review state; all three fact families appear in review where authorized; historical records load via `include_inactive`; medication history consistent with conditions/labs; provenance human-readable, not JSON-only; Brief selector generic wording; Brief options grouped by family; v1 Brief revision selections still render; v2 selections restore; Person switch clears selected Visit/Brief/correction/source details; stale response cannot repopulate old Person data; export uses v3 filename; no clinical interpretation strings anywhere.

### Person-switch race test

Deterministic async/frontend state test: request Alice → before result renders, switch to Bob → Alice's response resolves late → **zero Alice data in Bob's state**. If direct DOM automation is impractical without a new dependency, **isolate the workspace-generation decision logic into a pure, testable helper** (e.g., `shouldApplyResponse(generation, responseGeneration, currentGeneration)`) and unit-test the helper; do not add a heavy browser framework solely for this test.

### Revoked-while-open test

Bob has access and the workspace loads; assignment revoked; Bob clicks an already-rendered action → backend denies, no mutation, UI reports "this action is no longer available / you don't currently have permission", capability state refreshes, denied controls disappear, no leaked Person/record details.

## 24. Acceptance criteria

Mirrors the P2 acceptance list. P2 is accepted only when **all** of the following hold:

1. Branch `codex/p2-usable-family-workspace` starts from exactly `54192207d9ae8b55931c040e291f257dc14ad8ca`.
2. No changes made directly on `main`.
3. Product Core latest migration stays **v7** with v1–v7 all valid.
4. Portable vault stays **v3**.
5. Visit Brief stays **v2** with v1 readable.
6. Family Access stays v1 frozen + v2 current.
7. No G1 contract change.
8. `/workspace` reframed as a broad Health/Family Workspace (title, framing, headings).
9. Selected Person always obvious in the UI.
10. Accessible Person switching is low-friction.
11. Stale old-Person responses cannot render after a switch.
12. Capability-aware UI is server-derived (capabilities endpoint), not probe-based.
13. Backend authorization remains authoritative; UI map is advisory only.
14. Read-only users are not shown misleading enabled write controls.
15. Legacy v1 grants gain no Condition/Lab UI access.
16. Revocation mid-session fails closed.
17. Overview reveals no hidden counts.
18. Review Inbox handles all accessible fact families.
19. Pending is the default review view.
20. Rejected/unsupported candidates remain non-canonical.
21. Current and historical Medication, Condition, and Lab records are visible.
22. Historical/superseded wording is clinically neutral.
23. Provenance is human-readable (not raw JSON as the primary presentation).
24. Direct source metadata is Person-isolated (same-Person only; no paths/payload).
25. No raw source-content viewer.
26. Timeline is readable with distinct date semantics.
27. Visits are Person-scoped.
28. Questions are editable only with `visit.write`.
29. Brief evidence is grouped across three fact types with generic "Select confirmed evidence" wording.
30. v1 Brief revisions remain valid/readable.
31. v2 Brief selection restoration works.
32. Brief write/export controls respect the separate `brief.write`/`brief.export` capabilities.
33. Export warning and deliberate confirmation remain.
34. Export filename reflects v3 (server Content-Disposition + sanitized client download).
35. No document upload/OCR/model extraction.
36. No genetics/PGx.
37. No clinical interpretation anywhere.
38. Responsive layout without a UI framework.
39. Keyboard/focus semantics usable (visible focus, restored focus, aria-live, 44px targets, no color-only status).
40. P1 reviewer passes.
41. G5 reviewer passes unchanged.
42. P2 reviewer passes (deterministic P2 review, `python -m evals.p2_review`, mirroring the P1/G5 reviewer pattern, covering the §21 security invariants).
43. Full repository test suite passes.
44. Worktree clean on the P2 branch.
45. No remote mutation (no push, no tag, no PR).
