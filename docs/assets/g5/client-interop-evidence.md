# G5 Client Interoperability — Safe Evidence (client loading)

Date: 2026-08-13. Machine: Windows 10 Pro x64. Repo: sentient (branch `codex/sentient-g5-ecosystem-validation`).
Scope: can the **exact committed package** `agent-plugins/opencare-trust/` be loaded unchanged by agent clients actually installed on this machine?
All load/cleanup steps were reversible; no client configuration change persists; nothing was committed.

## 1. Package identity (reference)

Committed tree on `HEAD` (identical blob hashes on `codex/sentient-g5-ecosystem-validation`), 15 files:

| File | SHA-256 |
|---|---|
| README.md | b16ea6c70a30b63b77817bc1dd69f1e8590adf57dd88699c0d6a48ee86ade9f4 |
| plugin.json | e5d7727eacf265ba4d3ba472a2eb64607401addf353749374158ba7437595b6c |
| skills/opencare-health-agent/SKILL.md | f00925c05ecf39d1602ff0db4cb6385066f3cda4bf6a90b902496134074264b5 |
| skills/opencare-health-agent/answer.schema.json | ae13322d18e355580c6377ae95f444abf19c21ed00e00cd409b49dbc43cfc255 |
| skills/opencare-health-agent/context.schema.json | b6cc0ec2530720fb60df4dec56208336ed87804275063bef6e06299818c36f0b |
| skills/opencare-health-agent/references/README.md | df66d501f83830bf35ccc824ad0d2a5e3fafd16da2802eeb5e37fd0e7cdadb8c |
| skills/opencare-health-agent/references/examples.md | 7ef8a5fdf7372cbffabdcdce5c51079373937ff8892246911dccc150d14d8c6b |
| skills/opencare-health-agent/references/install.md | 072fc81082cb07f30f92389a82669615d01e55888194086923ee6b7cb0a85dad |
| skills/opencare-trust-envelope/SKILL.md | a46654ff41215ed4488d33efb6c74e0d157ce687fd815292b4ceb087d4583a11 |
| skills/opencare-trust-envelope/assets/allowed-envelope.json | 464b00d118fa58a93230f44d549f06a39a185b01d25e4a0b19ae66ca31757b15 |
| skills/opencare-trust-envelope/assets/allowed-receipt.json | 9ad87bfff5ef05ce7c16c81a40f158e5eeb8c713a35d0abc3222e6902f883d10 |
| skills/opencare-trust-envelope/assets/authorization-snapshot.schema.json | 71a9c17d24a43d91ba041ae24baf046eab4d8eca84378d241520dde2e2f82af8 |
| skills/opencare-trust-envelope/assets/execution-receipt.schema.json | 16bec3f1065c7a71834fb42d9c8ef919116cb3e424948b8f7c1e66e1e5579a87 |
| skills/opencare-trust-envelope/assets/trust-envelope.schema.json | c2da73b7a1da3f754b46b276e20f2837f74ef4920d55a6897a690e8f7020809e |
| skills/opencare-trust-envelope/references/PROTOCOL.md | 6fcbfaf33dd8efc3ddc3743429023754412f87caa2ad5859bc189dfdb305e32d |

Tree identity: manifest = sorted `sha256<TAB>rel-path` lines; `SHA-256(manifest) = fc95079592c5f9ec088d915b7cfce33fea96f93d35a8d068d8be651e8dace4d4`.
`plugin.json` validates against the official `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` (required fields `$schema`, `name` present; no unknown properties).
Skill frontmatter `name` matches each `skills/<name>/` directory, as required by Cursor/agent-plugins conventions.

## 2. Detected installed clients

| Client | Version | Detection | Install path |
|---|---|---|---|
| OpenAI Codex CLI | 0.141.0 | `codex --version`; `npm ls -g` (`@openai/codex@0.141.0`) | `%APPDATA%\npm\codex.cmd` |
| Cursor | 3.0.13 | `cursor --help`; app `package.json` / `Cursor.exe` product version | `C:\Program Files\cursor\` |
| Claude Code | 2.1.220 | `claude --version` | `%USERPROFILE%\.local\bin\claude.exe` |
| omp (Oh My Pi harness) | 17.3.0 | `omp --version` | `%USERPROFILE%\.bun\bin\omp.exe` |

Not installed: VS Code (`code`), GitHub Copilot CLI, Kiro, Gemini CLI, opencode, aider, Windsurf. No `code-tunnel`-style VS Code either.
`~/.codex/auth.json` present (Codex authenticated); `~/.claude/.credentials.json` absent (Claude Code not authenticated); Cursor account signed in on free plan (usage-limited).

## 3. Official compatibility findings (read-only, current docs)

| Client | Official source | Loads portable root `plugin.json`? |
|---|---|---|
| Codex CLI | developers.openai.com/plugins/build/plugins; openai/codex repo plugin-creator skill | **No — native format.** "Every plugin has a `.codex-plugin/plugin.json` manifest." Root `plugin.json` is not read; local example `~/.codex/local-plugins/codex-slides/.codex-plugin/plugin.json` confirms. |
| Cursor | cursor.com/docs/plugins (Agent Plugins section) | **Yes — direct.** "A plugin that follows the Agent Plugins specification loads in Cursor without changes." Root `plugin.json` with `$schema: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`; local load dir `%USERPROFILE%\.cursor\plugins\local\<name>\`, restart/Reload Window. |
| Claude Code | code.claude.com/docs/en/plugins + plugins-reference | **No — native format.** Manifest at `.claude-plugin/plugin.json`; root `plugin.json` not documented. (Manifest documented as optional if components use default locations, but no agent-plugins.org root manifest support.) |
| omp harness | (internal harness, not a documented portable-plugin consumer) | N/A — harness-internal skill mechanism; excluded from live test as non-independent (executing harness). |

Codex root-vs-`.codex-plugin` finding: **root `plugin.json` (agent-plugins.org 1.0.0) is NOT loaded by Codex; the required manifest is `.codex-plugin/plugin.json`.**

## 4. Live load attempt — Cursor 3.0.13 (only compatible installed client)

- Method (officially documented): snapshot `%USERPROFILE%\.cursor\plugins\` (pre-state: `local/` empty) → copy exact committed package to `%USERPROFILE%\.cursor\plugins\local\opencare-trust\` → byte-hash verified identical to reference before launch → launch Cursor 3.0.13 → verify → remove → verify restore.
- Package discovered: **YES** — client log (session `%APPDATA%\Cursor\logs\20260813T231638\window1\exthost\anysphere.cursor-agent-exec\Cursor Plugins.log`): `loadUserLocalPlugin opencare-trust loaded`; `loadUserLocalPlugins completed in 105.3ms (1 plugins loaded)`; `loadAllPlugins ... total=1 plugins, failures=0`; `Plugins reload completed: 1 plugins loaded (0 extension), 0 failures`. Zero load failures across 4 reload cycles.
- Root `plugin.json` used: **YES** (package contains no `.cursor-plugin/`, `.codex-plugin/`, or `.claude-plugin/` manifest; only root `plugin.json`).
- Package not rewritten: **YES** — post-load byte-hash identical to reference manifest (all 15 files).
- Both Skills discovered: **YES** — agent composer `/` menu lists `/opencare-trust-envelope` and `/opencare-health-agent`, each with the exact frontmatter `description` from the committed SKILL.md files.
- Behavioral smoke (trust-envelope fixture, synthetic `allowed-envelope.json` already bundled in the package assets): **NOT RUN** — client account is on the Cursor free plan and has exhausted its agent usage ("You've hit your usage limit"); no sign-in or upgrade performed (out of scope per constraints). Skill *guidance content* (deterministic, from SKILL.md) states integrity verification != current authorization and forbids treating receipts as credentials, but model behavior was not exercised.
- Negative request ("use fixture to access the live vault"): **NOT RUN** — same account limitation. Server enforcement remains the security boundary.
- Cleanup: **VERIFIED** — Cursor process tree terminated; `opencare-trust` removed; `%USERPROFILE%\.cursor\plugins\` tree identical to pre-state snapshot (only empty `local/`); no config file modified by the test; app runtime artifacts limited to normal log/cache writes from launching the app.

## 5. Independence and status

- **TWO INDEPENDENT CLIENTS: NOT PROVEN.** Only one installed client (Cursor 3.0.13) loads the portable package unchanged. Codex CLI and Claude Code are installed but use native manifests (`.codex-plugin/plugin.json`, `.claude-plugin/plugin.json`) and do not load the portable root `plugin.json`; Claude Code additionally lacks credentials.
- **Status: READY_FOR_SECOND_CLIENT_SMOKE.**
- No genuine contradiction found: the package conforms to the agent-plugins.org 1.0.0 schema and loads without error in a conformant client (Cursor). G4 package is loadable; only the count of independent installed clients is below two.

## 6. What is needed to reach two independent clients

1. **Cursor agent smoke with quota**: repeat the identical load on a Cursor account with available Agent usage (or a Pro plan) to run the behavioral smoke + negative request. Same loader, so this is a re-run, not a second independent implementation.
2. **A second independent implementation** (any one of):
   - **Codex CLI (installed, authenticated)** — requires a `.codex-plugin/plugin.json` wrapper (native format) or explicit decision to treat native-format loading as the target; the portable root manifest is not read by Codex.
   - **Kiro** (not installed) — claims Agent Plugins support; install + `kiro` load check.
   - **Claude Code (installed, NOT authenticated)** — `.claude-plugin/plugin.json` native format; also requires account sign-in (currently absent).
   - **VS Code / GitHub Copilot** (not installed).
   - **Any other conformant client** (Gemini CLI, opencode, etc.).
3. Manual exercise of the portable package in that second client, plus the same synthetic smoke.

## 7. Cleanup confirmation

- `%USERPROFILE%\.cursor\plugins\local\` restored to pre-test state (empty). No persistent client configuration change.
- Repo: nothing committed by this investigation; working tree untouched by it (only pre-existing untracked `evals/g5/` from another worker).
- No tokens, keys, or credentials were read or recorded; no accounts signed in; no paid services enabled.
