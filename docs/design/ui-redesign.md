# OpenCare UI Redesign

## 1. Status / scope

**UI-R0 — Product UI Architecture + Design Direction** is the planning contract for the first OpenCare UI redesign stage. Its working direction is **Private Evidence Workspace**. This phrase names a product-UI direction, not a marketing brand.

This document defines the information architecture, shared visual language, component vocabulary, responsive and accessibility contracts, and the R1–R4 sequence. R0 changes no runtime HTML, CSS, JavaScript, routes, localization catalogs, backend behavior, authorization semantics, or trust policy.

Current sequencing truth:

- D2 Document Intelligence, P3 Genetics Research Studio, R6 provider productization, and AlphaGenome Foundation/A through C.1 are done and published.
- Product Core is v11, Family Access is v4, portable export is v6, and Visit Brief is v2.
- AlphaGenome is paused after C.1; this redesign does not begin D.
- R7 Docker is paused.
- The active product line is UI Redesign.

## 2. Product truths that design must preserve

- OpenCare is a local-first, self-hosted Personal and Family Health Workspace.
- The product remains useful without genetics or an LLM. Genetics is an optional, deeper research workspace.
- Person scope is explicit and authorization remains deny-by-default. Relationships do not imply grants; ordinary health access does not imply genetics access.
- The durable health flow remains source → candidate record → human review → canonical state. AI never becomes canonical truth or mutates canonical records.
- Provenance stays close to meaningful claims. Unsupported, conflicting, absent, no-call, build-incompatible, and ambiguous states stay explicit.
- External execution and disclosure remain explicit, bounded, consent-aware, and receipted. Raw genome never enters provider context.
- OpenCare does not diagnose, prescribe, recommend dosage, or make medication start/stop decisions.
- OpenCare remains OpenCare: not a genetics-first or AlphaGenome-first product, generic medical chatbot, or generic trust product.

## 3. Current UI inventory

| Surface | Existing route | Current functional structure to preserve |
|---|---|---|
| Overview | `/workspace` and `/workspace#overview` | Person context, attention/review summaries, recent information and quick actions |
| Health | `/workspace#records` | Candidate review and canonical medication, condition, lab, procedure, recommendation, and follow-up records |
| Documents | `/workspace#documents` | Bounded PDF/TXT upload, extraction state, source details and selected evidence |
| Activity | `/workspace#timeline` | Record lifecycle and recent changes |
| Visit preparation | Existing local Workspace section | Visits, questions, selected evidence, Visit Brief and revisions |
| Chat | `/chat` | Authorized context, disclosure preparation/consent, answer, evidence and refusal/receipt behavior |
| Genetics | `/genetics` | Import, variants, findings/evidence, PGx, health/traits views, family comparison and Research Mode |
| Family Access | `/family-access` | Active Person, people with access, invitations/sharing, grants and family relationships |
| Settings | `/family-access#account-settings` | Account, password, provider status and sign-out; there is no `/settings` route |

The authenticated shell supplies the primary navigation, top context area, responsive navigation, active route state, EN/RU locale selection, and skip-to-content behavior. Page scripts update the shell’s active Person status.

## 4. Verified current design problems

These are implementation observations, not claims that current behavior is broken.

- **Duplicated token vocabularies.** The shell defines `--shell-*` plus shared aliases in `app/static/product_shell.css:1-31`; Workspace independently defines `--ink`, `--muted`, `--line`, `--page`, `--surface`, and related roles in `app/static/product_core_workspace.css:1-17`; Genetics repeats and expands that palette in `app/static/genetics.css:1-23`; Chat retains another compact root palette in `app/static/chat.css:1` while later rules also consume shell tokens.
- **Typography drift.** The shell uses an Inter-first stack (`app/static/product_shell.css:36-44`), Workspace uses Arial (`app/static/product_core_workspace.css:18-21`), Genetics uses Arial/Helvetica (`app/static/genetics.css:25-28`), and Chat carries an Inter/system stack (`app/static/chat.css:1-4`).
- **Containers are the dominant hierarchy mechanism.** Workspace applies surface, border, radius, and shadow to nearly every non-intro section (`app/static/product_core_workspace.css:35-38`) and then adds bordered summary items, inline forms, and records (`:57-85`). Family Access similarly elevates its intro, Person context, account settings, and each Person workspace section (`app/static/family_access_workspace.css:18-24,60-70`) before adding bordered access cards and technical records.
- **Nested surfaces are common.** Workspace sections contain summary items, inline forms, records, source details, and warnings. Genetics places bordered import panels, notices, observations, pathways, and state cards inside a bordered/shadowed tab panel (`app/static/genetics.css:78-103,120-175,248-259`). Family Access nests access cards and scope groups inside elevated sections (`app/static/family_access_workspace.css:54-70,144-183`).
- **Controls and states are page-local.** Workspace defines global page buttons/inputs, badges, and status colors (`app/static/product_core_workspace.css:61-90`); Genetics separately defines controls, tab states, seals, loading skeletons, and errors (`app/static/genetics.css:78-100,248-259`); Family Access adds scoped status, card, form, and Advanced styles; Chat restyles controls using a mixture of local and shell variables (`app/static/chat.css:20-35`).
- **Genetics is a strong mini-design-system.** Eight ARIA tabs, a two-column scientific workspace, boundary banner, source seals, epistemic labels, dense observation/evidence layouts, and dedicated loading/error states are defined in `app/templates/genetics.html:77-190` and `app/static/genetics.css:55-113,219-259`.
- **Family Access is another local presentation layer.** Human sharing, account settings, provider information, technical context, direct grants, installation accounts, and family records have page-scoped layout and component rules (`app/templates/family_access_workspace.html:42-219`; `app/static/family_access_workspace.css:18-105,292-349`).
- **Workspace is structurally dense.** One template contains Person management, eight local navigation targets, overview, review, documents, six record families, timeline, visits/briefs, and export (`app/templates/product_core_workspace.html:12-48`). Its 1,051-line script coordinates those states and interactions.
- **Mobile behavior exists, but hierarchy is primarily adaptation of desktop containers.** The shell collapses at 52rem and supports Escape-to-close; Workspace, Genetics, Chat, and Family Access each add page-local breakpoints. These preserve function, but the independent responsive rules do not yet form one structural system.

Positive behavior to preserve: real hash-aware navigation and `aria-current`, skip link and landmarks, visible `:focus-visible` rules, EN/RU selection, 44px controls on important page actions, reduced-motion handling, live status regions, labeled forms, Genetics tab semantics, and focused Family Access recovery feedback.

## 5. Information architecture

The sidebar uses only existing destinations and groups them visually without changing URLs:

1. **Workspace**
   - Overview → `/workspace#overview` (and `/workspace`)
   - Health → `/workspace#records`
   - Documents → `/workspace#documents`
   - Activity → `/workspace#timeline`
2. **Tools**
   - Chat → `/chat`
   - Genetics → `/genetics`
3. **Family and account**
   - Family Access → `/family-access`
   - Settings → `/family-access#account-settings`

The top context rail answers “Who am I viewing?” before page-specific content. It shows the active Person or an explicit no-Person state, and provides the existing Person-selection behavior where the surface permits it. The sidebar remains quiet; the context rail, page title, local navigation, and content rows establish the task hierarchy.

Local navigation may reveal existing sections within a surface. It must not manufacture backend routes, dead links, or route-like URLs for client-only states. Visit preparation and export remain existing Workspace capabilities and can be reached through Workspace local navigation rather than becoming new primary routes.

## 6. Private Evidence Workspace direction

OpenCare should feel like a private evidence workspace: calm, trustworthy, human, document-aware, and precise.

- **Entry:** quiet shell, unmistakable current destination, and obvious Person scope.
- **Work surface:** broad readable content with controlled prose measure and room for dense records where needed.
- **Hierarchy:** attention and primary task first; section headings, spacing, dividers, aligned rows, and progressive disclosure before elevation.
- **Evidence:** source, review state, confidence, and limitations remain adjacent to the claim they qualify.
- **Containment:** use a card only for an independently actionable or movable object, a selected/interactive item, a bounded warning/confirmation, or content requiring figure/ground separation.
- **Tone:** privacy and trust come from legibility, explicit boundaries, predictable behavior, and restraint—not decorative security theater.

It must not resemble a generic SaaS dashboard, hospital administration system, RPG genome dashboard, developer console, or AI chatbot wrapper.

## 7. Visual principles

1. **Person before content.** Person identity and scope are never left to inference.
2. **Tasks before subsystems.** Lead with what needs attention or what the user can do; do not assign equal weight to every backend capability.
3. **Rows before cards.** Canonical records, evidence, activity, and documents default to lists/rows with dividers. Elevation must communicate containment or interaction.
4. **Provenance at the point of trust.** A claim’s source, review state, date, and limitations stay in its reading path, with detail progressively disclosed.
5. **One visual language.** Shared typography, controls, state vocabulary, spacing, shape, and focus behavior apply to all surfaces. Scientific density may vary; meaning does not.
6. **Restrained semantic color.** Accent marks action/current selection. Status colors communicate state and are always paired with text or another non-color cue.
7. **Familiar affordances.** Standard links, buttons, tabs, tables, forms, disclosures, dialogs, and popovers should behave conventionally.
8. **Light theme only.** R1–R4 do not introduce dark-theme requirements.

## 8. Shared design tokens — semantic roles only

R1 will establish one shared vocabulary; page roots consume it rather than redefine a palette.

- **Color:** canvas; surface; raised/interactive surface; primary, secondary, and quiet text; divider and strong divider; primary action/accent and active selection; focus; success; warning; danger; information.
- **Evidence:** observed; supported; plausible; speculative; unsupported/conflicting. Each role requires a text label or icon/pattern in addition to color and must remain distinct from record lifecycle status.
- **Typography:** one UI family/stack with no external loading; body, compact body, label, metadata, heading levels, and data/numeric roles; tabular numerals for dates, measurements, counts, versions, and identifiers where alignment aids scanning.
- **Spacing:** compact control gap, related-content gap, row padding, section gap, page gutter, and readable content measure.
- **Shape:** control radius, disclosure/notice radius, and contained-surface radius. Pills are reserved for compact badges/statuses, not general containers.
- **Depth:** flat, bordered, and raised/overlay. A component uses one containment signal by default; border-plus-shadow is not the universal surface treatment.
- **Interaction:** hover, focus, active, selected, disabled, loading, success, warning, and error state roles.
- **Motion:** quick state transition and deliberate reveal; reduced-motion alternatives preserve state comprehension.

Direction only: a warm or neutral light canvas, deep tinted text, restrained petrol/green accent family, and muted accessible semantic colors. R0 selects no final CSS values.

Typography must support EN/RU, readable health/document prose, compact data labels, predictable line length, and a tighter product-UI hierarchy. R1 removes the current Inter/Arial drift without adding a web-font dependency.

## 9. Shared component vocabulary

Every interactive component must define default, hover, focus-visible, active/selected where applicable, disabled, loading, error, and success behavior. Empty and loading treatments preserve layout and explain the next action.

- **Shell:** app sidebar/navigation; mobile navigation trigger; top context rail; Person selector/context; locale selector.
- **Hierarchy:** page title/header; section header; local tabs or segmented navigation; dividers.
- **Actions:** primary, secondary, and destructive buttons; text/link action; icon-only action only with an accessible name and sufficient target.
- **Forms:** input, select, textarea, checkbox/radio, fieldset, help text, validation message, form action row.
- **Data:** data row; evidence row; document/source row; definition list; responsive table/list; status badge; metadata cluster.
- **Trust:** provenance/source disclosure; evidence confidence label; inline notice; consent/disclosure preview; confirmation block; execution receipt/refusal.
- **System states:** empty state with next step; skeleton/loading state; error with cause and recovery; success feedback; permission/no-access state.
- **Disclosure:** native details/summary, popover, and dialog only when interruption or protected focus is required. Overlays must escape clipping containers.

A card is justified by independent containment, selection, bounded interaction, or overlay depth. A section, record, statistic, or paragraph does not become a card by default; nested cards are exceptional and require a documented containment reason.

## 10. Workspace design intent

Future R2 priority:

1. **Who am I viewing?** Keep Person context first and stable across local sections.
2. **What needs attention?** Promote pending review, extraction failures, conflicts, and visit tasks into concise actionable rows with status and next action.
3. **What health information is here?** Present canonical medications, conditions, labs, procedures, recommendations, and follow-ups as records grouped by type, not equal-weight cards.
4. **What documents were added or extracted?** Show sources, extraction/review state, dates, and provenance.
5. **What changed recently?** Use a chronological activity list with meaningful event labels and links to affected records.
6. **What should I prepare for a visit?** Give Visits and Visit Brief a focused workflow over selected confirmed evidence, questions, and revisions.

Overview summarizes these priorities rather than mirroring every Product Core subsystem. Review items expose the evidence, proposed value, status, and allowed review action. Canonical and historical states remain visually distinct without implying unsupported clinical authority. Export remains explicit and warning-gated.

## 11. Documents design intent

Documents are sources and evidence, not generic file cards.

- Lead with upload/add-source action, supported PDF/TXT boundary, and current Person.
- Use source rows showing filename/title, type, added date, extraction status, review state, and relevant actions.
- Keep extracted text subordinate to source identity and integrity; use readable page/text views with locators.
- Connect candidate facts to their document/page provenance and human-review status.
- Design empty, uploading, extracting, ready-for-review, partially supported, failed, and unavailable states with explicit recovery.
- Never imply OCR, image interpretation, cloud extraction, unrestricted raw-document model context, or clinical NER.

## 12. Chat design intent

Chat is a constrained workspace over authorized user data, not OpenCare’s identity or a generic assistant feed.

The future reading order is:

1. current Person and selected context scope;
2. user question;
3. provider/external disclosure preview and explicit consent when required;
4. answer or refusal;
5. citations/evidence connected to claims;
6. execution receipt and limitations.

User questions and OpenCare answers need distinct but restrained treatments. Evidence and citations are first-class rows/disclosures, not decorative footnotes. Loading identifies whether context is being prepared or execution is in progress. Refusal states explain the boundary and safe next step. No visual change may weaken consent, validation, provenance, receipt, or canonical-mutation restrictions.

## 13. Genetics design intent

Genetics remains a first-class, optional deeper research workspace within the shared shell and component system. Preserve current Person scope, import, variants, findings/evidence, PGx, family comparison, Research Mode, and the raw-genome boundary.

- Retain denser tables, ledgers, filters, and scientific metadata where density improves comparison.
- Replace the isolated mini-system with shared tokens, controls, notices, states, and provenance patterns while keeping domain-specific evidence and epistemic labels.
- Make import/build/coverage limits and ambiguous/no-call/not-tested states visible before interpretation.
- Keep Genetics Evidence Mode and Explore Mode visibly distinct; Explore retains mandatory counterevidence/Devil’s Advocate presentation.
- Family comparison visibly requires both Person scopes and remains compatibility/IBS-style evidence, never legal or forensic kinship proof.
- Raw genome remains local and outside provider context. Research exposes only authorized, minimized, selected projections.

AlphaGenome remains paused after C.1. R3 does not add AlphaGenome D or later capabilities.

## 14. Family Access / Settings design intent

The surface hierarchy is **People**, **Sharing**, **Your account**, then **Advanced**.

- People and Sharing lead with names, relationships, role, access summary, invitation status, revocation/revision actions, and the active Person.
- Human-readable permission summaries precede machine scope strings. Permission semantics, frozen scope generations, genetics separation, and next-decision revocation remain unchanged.
- Your account contains provider status, password, and sign-out at `/family-access#account-settings`.
- Technical Actor IDs, raw scopes/assignments, consent history, audit detail, direct grants, installation accounts, and technical family records stay under explicit Advanced disclosure.
- No standalone `/settings` link or route is introduced.

## 15. Responsive behavior

Responsive change is structural, not typography shrinkage.

| Width | Required structure |
|---|---|
| Wide desktop | Persistent quiet sidebar; top Person context rail; generous main work surface; optional local rail for dense Genetics/Workspace tasks; tables where comparison requires columns |
| Normal laptop/tablet | Collapsible or compact primary navigation; context rail remains explicit; secondary rails become horizontal/local navigation or in-flow disclosures; multi-column forms collapse when labels or data become cramped |
| 390px mobile | Off-canvas/collapsed primary navigation with visible state and Escape/close behavior; single-column task flow; full-width primary actions where useful; rows recompose into labeled stacks; sticky elements must not obscure content |

All target widths require no horizontal page overflow, understandable Person context, 44px minimum important touch targets, readable lists/tables, sensible single-column forms, and dialogs/popovers that fit the viewport without clipping. Dense tables choose among labeled stacked rows, controlled internal scrolling with context, or column prioritization; the whole page must not scroll horizontally. Test realistic long EN/RU text and identifiers.

## 16. Accessibility

Target WCAG 2.2 AA behavior:

- Preserve a skip link and semantic `aside`/`nav`, `header`, and `main` landmarks.
- Use one `h1` per surface and ordered section headings that describe the visible hierarchy.
- Keep a high-visibility focus indicator on every interactive control; focus order follows visual/task order and returns sensibly after closing navigation or overlays.
- Meet 4.5:1 contrast for normal text and 3:1 for large text and meaningful UI boundaries; never communicate state through color alone.
- Keep important touch targets at least 44×44 CSS pixels.
- Give every form control a persistent label, related help, clear required state, field-level error, and actionable recovery message.
- Apply `aria-current` to the current route, `aria-selected` to tabs/options, `aria-expanded` and `aria-controls` to disclosures/navigation, and accurate accessible names to icon controls.
- Use status/live feedback for asynchronous outcomes without repeatedly interrupting the user. Move focus only when recovery or newly revealed protected work requires it.
- Empty, loading, no-access, error, confirmation, success, and stale/conflict states remain understandable to screen readers and keyboard users.
- Preserve EN/RU language declaration and translated control labels.

## 17. Motion

Motion is low priority. Later stages may use roughly 150–250ms transitions for open/close, selection, state change, loading, and reveal. Motion must begin from a usable state, never delay task completion, and preserve comprehension under `prefers-reduced-motion`.

No page-load choreography, bounce, decorative floating objects, continuous motion, parallax, or animation used only to make the product feel “AI-powered.” Skeleton movement must stop or simplify under reduced motion.

## 18. Explicit anti-patterns

- Generic SaaS dashboard, bento grid, hero-metric wall, or equal-weight subsystem tiles.
- Universal `section = card`, same-size card grids, or nested-card layout as the default.
- Purple-blue SaaS gradients, decorative gradients, glassmorphism, neon, glow halos, or decorative pure black.
- Color without semantic meaning or evidence confidence encoded by color alone.
- Rounded pills for general containers; inconsistent radii, shadows, icons, buttons, or form controls between pages.
- Decorative AI stars, brains, or chat motifs; RPG-like genome visualization; developer-console styling for ordinary users.
- Display fonts in controls/data, external font loading, or page-specific typography stacks.
- Hidden Person scope, detached provenance, unsupported certainty, or trust/security theater.
- Dead navigation, invented `/settings`, or client-only state presented as a backend route.
- Modal-first workflows, clipped popovers, hover-only information, inaccessible custom controls, or font shrinking as the responsive strategy.
- Heavy animation, marketing experimentation, or dark theme expansion during R1–R4.

## 19. R1–R4 implementation sequence

### R1 — App Shell + Design System

- Establish shared semantic tokens, one local/system typography stack, spacing/shape/depth roles, and component state contracts.
- Redesign sidebar, mobile navigation, context rail, Person context, locale selector, page/section headers, controls, notices, rows, disclosures, and system states.
- Preserve route resolution, hash-aware active state, Settings location, EN/RU behavior, skip link, keyboard/Escape behavior, and runtime trust semantics.
- Acceptance gate: shell and shared primitives work at desktop and 390px before page migration.

### R2 — Workspace + Documents

- Apply the six-level Workspace priority, actionable review queue, record-row grammar, source/evidence-oriented Documents view, Activity list, and focused Visit preparation.
- Preserve every Product Core capability and source/review/canonical transition.
- Acceptance gate: no subsystem is lost; Person, review state, provenance, and source identity remain visible and actionable at desktop and 390px.

### R3 — Chat + Genetics + Family Access / Settings

- Migrate each specialized surface to shared tokens/components while retaining justified scientific density and domain-specific trust states.
- Preserve Chat disclosure/consent/receipt/refusal, Genetics raw-genome and mode boundaries, and Family Access authorization semantics.
- Acceptance gate: all existing routes and interactions remain functional; Advanced technical data is available but no longer dominates human sharing.

### R4 — Convergence and bounded visual QA

- Audit shared-token adoption, typography/control consistency, real content ranges, all state variants, responsive overflow, keyboard navigation, WCAG AA contrast, EN/RU expansion, and overlay clipping.
- Remove obsolete page-local palette/control rules only after their consumers migrate; do not introduce compatibility aliases as a permanent second system.
- Acceptance gate: representative desktop, laptop/tablet, and 390px flows pass the measurable criteria below with no backend/security semantic change.

## 20. Acceptance criteria

Later implementation is accepted only when:

- one shared semantic token vocabulary and one shared typography system serve all authenticated surfaces;
- one button/form/control vocabulary covers complete interaction and validation states;
- no page-specific duplicated root palette remains without a documented domain-specific reason;
- there is no universal section-as-card rule or nested-card layout default;
- active Person context is consistently visible and understandable, including no-selection/no-access states;
- provenance is visually connected to the evidence or claim it qualifies;
- navigation uses only real routes and Settings remains `/family-access#account-settings`;
- EN/RU content, labels, and realistic long values remain usable;
- wide desktop, normal laptop/tablet, and 390px mobile have no page-level horizontal overflow and retain usable navigation;
- keyboard operation, focus visibility, semantic state attributes, and screen-reader feedback are complete;
- text, meaningful UI boundaries, focus, and states meet WCAG AA contrast;
- empty, loading/skeleton, success, warning, error/recovery, stale/conflict, confirmation, refusal, and permission states are designed where applicable;
- important mobile touch targets are at least 44px and overlays do not clip;
- canonical record, authorization, consent, provider disclosure, provenance, raw-genome, and security semantics are unchanged.

## 21. Non-goals

R0 does not modify runtime files or start R1. R1–R4 do not rename OpenCare, add routes, remove product functionality, change backend/API or security semantics, alter localization catalogs as part of R0, install frontend dependencies, introduce external fonts, or add a dark theme.

The redesign does not add diagnosis, treatment or dosage recommendations, medication start/stop authority, clinical validation claims, OCR, raw-genome cloud/provider upload, WGS pipelines, AlphaGenome D+, R7 Docker work, autonomous canonical mutation, SaaS expansion, payments, Telegram, blockchain, or MCP as a product objective.

## 22. External design references

Impeccable is an external process and QA reference only—not a dependency, implementation source, partnership, or endorsement. No code is copied. References were studied at snapshot `67d018fe052853c104a96d441ce175dd5ec4c39d`:

- [Impeccable repository](https://github.com/pbakaus/impeccable)
- [Impeccable documentation](https://impeccable.style)
- [Shape](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/shape.md): separate durable product truth and constraints from visual direction.
- [Operate](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/operate.md): task clarity, scanability, familiar affordances, structural responsiveness, and complete component states.
- [Craft floor](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/craft-floor.md): bounded implementation checks and resistance to card-heavy generic AI UI.
- [Audit](https://github.com/pbakaus/impeccable/blob/67d018fe052853c104a96d441ce175dd5ec4c39d/skill/reference/audit.md): evidence-based accessibility, theming, responsive, performance, and implementation-integrity review.

OpenCare deliberately does not import Impeccable’s bolder or marketing-oriented aesthetic possibilities. Its own product truth requires a calmer, privacy-sensitive Operate UI.