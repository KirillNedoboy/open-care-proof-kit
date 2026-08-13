# G5 Client Interoperability — Safe Evidence (client loading)

Dates: 2026-08-13 (discovery + load proof) and 2026-08-14 (behavioral-smoke attempt, re-verified load).
Machine: Windows 10 Pro x64. Repo: sentient (branch `codex/sentient-g5-ecosystem-validation`, HEAD `b2f6593`).
Scope: can the **exact committed package** `agent-plugins/opencare-trust/` be loaded unchanged by agent clients actually installed on this machine?
All load/cleanup steps were reversible; no client configuration change persists; nothing committed (operator decides).

## 1. Package identity (reference)

Committed tree on `HEAD` — 15 files. **Every SHA-256 below was cross-verified against the committed git blob** (`git cat-file blob HEAD:<path>`) — all 15 match. Git blob (tree) identity is stable; see `git ls-tree -r HEAD agent-plugins/opencare-trust/` (blobs e.g. `988cb95c` plugin.json, `25368502` trust SKILL.md, `027d5a94` allowed-envelope.json).

| File | SHA-256 (verified vs committed blob) |
|---|---|
| README.md | 9a977d619c56ff8a8de4d4a54a84ae9434397e6d1fd8fd7212997f0621ff8907 |
| plugin.json | 15a92c9d4b31d3d4421ba6f3e84c31d04e205d35fa93712f4feb6ce5d1a90a4b |
| skills/opencare-health-agent/SKILL.md | fd7a40773a3b2d273d3b3bc52a0e0e1c85385b02271987b757eca17e534a98f0 |
| skills/opencare-health-agent/answer.schema.json | 8f719f31cf30276617b8bcfa75abb795778434c184577479a9f2c1d19b46ce6c |
| skills/opencare-health-agent/context.schema.json | 42dc044dc73f2e1aae58755658ac47caeeb1cb27258609c51e074ef22ce171b3 |
| skills/opencare-health-agent/references/README.md | 8b4ca20614fe2206acafbbe97521490260e1ede9bc10184a427cb3f9e1be349c |
| skills/opencare-health-agent/references/examples.md | e11b204013af5e519586119bd837d6a232880e1acfa0a0f413dbf05a935f1678 |
| skills/opencare-health-agent/references/install.md | 397431fb22979e2cd75c2f9fdb8afe9eb912af560cf75bebeff86d47bbe1c8ca |
| skills/opencare-trust-envelope/SKILL.md | 4fc633cd5a1ce25687c2ad16859a34c7b5816491a041b451ffb58bfa6bd71852 |
| skills/opencare-trust-envelope/assets/allowed-envelope.json | af77ad18b24b14c54b571167068aa62d620988bc2428fd0a5b905077c7fe827a |
| skills/opencare-trust-envelope/assets/allowed-receipt.json | 4577758ffbe003dc53cfc47fa0b9004446b7b57d13f4b0738e063018ebe30413 |
| skills/opencare-trust-envelope/assets/authorization-snapshot.schema.json | 0de3919d9c9b5996a24a20071b07640891940734b17d9f3343418a45a72dbfca |
| skills/opencare-trust-envelope/assets/execution-receipt.schema.json | f7a4078ac5554b2556962611793badf0a3c793caf2f03dc5275e2f43268277fc |
| skills/opencare-trust-envelope/assets/trust-envelope.schema.json | 07e0e590a11c54046c707d2d2a55c39fa0ab08c4c51f39c7ac5728290fcf9358 |
| skills/opencare-trust-envelope/references/PROTOCOL.md | cd7270d5bfd5a6be4398652f424bada66b99db56efdf5e8384658e4b188f13be |

Tree identity: manifest = sorted `sha256<TAB>rel-path` lines; `SHA-256(manifest) = f49e97f8fb10d490309e47c0fb9e6e7d32c2ade5f3fece0cedf1e6c8502f3efe`.
`fixtures/agent-trust/allowed-envelope.json` is byte-identical to the package's bundled asset (`af77ad18…`); the Skill's synthetic fixture is already in the package (`skills/opencare-trust-envelope/assets/`), so no fixture copy is needed.
`plugin.json` validates against the official `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` (required `$schema`, `name`; no unknown properties). Skill frontmatter `name` matches each `skills/<name>/` directory.

## 2. Detected installed clients (fresh re-detection 2026-08-14)

| Client | Version | Detection method | Install path |
|---|---|---|---|
| OpenAI Codex CLI | 0.141.0 | `codex --version`; `where codex`; `npm ls -g` (`@openai/codex@0.141.0`) | `%APPDATA%\npm\codex` |
| Cursor | 3.0.13 | `cursor --help`; app `package.json` / `Cursor.exe` ProductVersion | `C:\Program Files\cursor\` |
| Claude Code | 2.1.220 | `claude --version`; `where claude` | `%USERPROFILE%\.local\bin\claude.exe` |
| omp (Oh My Pi harness) | 17.3.0 | `omp --version` | `%USERPROFILE%\.bun\bin\omp.exe` |
| GitHub CLI | 2.87.3 | `gh --version`; `gh extension list` | `C:\Program Files\GitHub CLI\gh.exe` |

Not installed (checked `where`/`Get-Command` + install dirs): VS Code (`code`, `code-insiders`), Kiro, GitHub Copilot CLI (`github-copilot`, `copilot`, no `gh copilot` extension), Gemini CLI (`gemini`), Windsurf, aider, opencode, cursor-agent binary (absent from Cursor install).
Auth state (existence checks only): `~/.codex/auth.json` present (Codex authenticated); `~/.claude/.credentials.json` absent (Claude Code not authenticated); Cursor account signed in on free plan — **agent usage exhausted** (see §4).

## 3. Official compatibility findings (read-only, current docs)

| Client | Official source | Loads portable root `plugin.json`? |
|---|---|---|
| Codex CLI | developers.openai.com/plugins/build/plugins; openai/codex plugin-creator skill | **No — native format.** "Every plugin has a `.codex-plugin/plugin.json` manifest." Root `plugin.json` not read; confirmed by installed `~/.codex/local-plugins/codex-slides/.codex-plugin/plugin.json`. |
| Cursor | cursor.com/docs/plugins (Agent Plugins section) | **Yes — direct.** "A plugin that follows the Agent Plugins specification loads in Cursor without changes." Root `plugin.json` (`$schema: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`); local dir `%USERPROFILE%\.cursor\plugins\local\<name>\`. |
| Claude Code | code.claude.com/docs/en/plugins + plugins-reference | **No — native format.** Manifest `.claude-plugin/plugin.json`; root `plugin.json` not documented. Ineligible also because not authenticated. |
| omp harness | (internal harness; not a documented portable-plugin consumer) | N/A — harness-internal skill mechanism; excluded as non-independent (executing harness). |
| GitHub CLI | (no agent-plugin loading; no copilot extension installed) | N/A. |

Codex root-vs-`.codex-plugin` finding: **root `plugin.json` (agent-plugins.org 1.0.0) is NOT loaded by Codex; the required manifest is `.codex-plugin/plugin.json`.**

## 4. Live load + behavioral smoke — Cursor 3.0.13 (only compatible installed client)

Two independent runs, same method, same result on load/discovery; smoke blocked identically both times.

- Method (officially documented): snapshot `%USERPROFILE%\.cursor\plugins\` (pre-state: `local/` empty) → copy exact committed package to `%USERPROFILE%\.cursor\plugins\local\opencare-trust\` → byte-hash verified identical to §1 manifest before launch → launch Cursor → verify → remove → verify restore.
- Package discovered: **YES** — client log (`%APPDATA%\Cursor\logs\20260813T231638\…\Cursor Plugins.log` and `20260814T000929\…\Cursor Plugins.log`): `loadUserLocalPlugin opencare-trust loaded`; `loadUserLocalPlugins completed in …ms (1 plugins loaded)`; `loadAllPlugins … total=1 plugins, failures=0`; `Plugins reload completed: 1 plugins loaded (0 extension), 0 failures`. Zero failures across reload cycles.
- Root `plugin.json` used: **YES** — package contains only the root `plugin.json` (no `.cursor-plugin/`, `.codex-plugin/`, `.claude-plugin/` manifest).
- Package not rewritten: **YES** — post-load byte-hash identical to §1 manifest (all 15 files) on both runs.
- Both Skills discovered: **YES** — agent composer `/` menu lists `/opencare-trust-envelope` and `/opencare-health-agent` with the exact frontmatter descriptions from the committed SKILL.md files (verified 2026-08-13 and 2026-08-14).
- POSITIVE behavioral smoke (synthetic `allowed-envelope.json`): **NOT RUN — exact blocker:** submitting the prompt in the agent composer returns **"You've hit your usage limit"** with "Get Cursor Pro for more Agent usage, unlimited Tab, and more." The installed Cursor account is on the free plan and its Agent usage is exhausted; using the agent requires the paid plan. Per constraints, no upgrade and no sign-in to a new account was performed. Skill *guidance content* (deterministic, from SKILL.md) states integrity verification != current authorization and never treats receipts as credentials, but model behavior was not exercised.
- NEGATIVE smoke (valid fixture → live vault access): **NOT RUN — same exact blocker** ("You've hit your usage limit"). Server enforcement remains the security boundary.
- Cleanup: **VERIFIED** — Cursor process tree terminated; `opencare-trust` removed; `%USERPROFILE%\.cursor\plugins\` identical to pre-state (empty `local/`); no config file modified; only normal app log/cache runtime artifacts.

## 5. Second independent client

- **Not available on this machine.** Fresh re-detection (§2) found no second conformant root-`plugin.json` client: VS Code/Kiro/Copilot/Gemini/Windsurf/aider/opencode not installed; Codex CLI and Claude Code are installed but use native manifests (§3) and are therefore ineligible by the operator's rule; omp is the executing harness (not independent); GitHub CLI has no agent-plugin loading.
- Per constraints, installing a full IDE (VS Code, Kiro) was NOT performed.

## 6. Independence and status

- **TWO INDEPENDENT CLIENTS WITH FULL BEHAVIORAL EVIDENCE: NOT PROVEN → READY_FOR_SECOND_CLIENT_SMOKE.**
- One conformant client (Cursor 3.0.13) is proven for load + discovery (root `plugin.json`, package byte-identical, both Skills discovered), but its behavioral smoke is blocked by the account's exhausted free-plan Agent usage — no paid upgrade permitted.
- No genuine contradiction found: the package conforms to the agent-plugins.org 1.0.0 schema and loads with zero failures in a conformant client.

## 7. Exact remaining manual steps for PASS

1. **Cursor behavioral smoke** (same loader; not a second independent implementation): re-run the identical load on a Cursor account with available Agent usage (paid/Pro or quota-reset free account), then run (a) the positive synthetic-envelope smoke and (b) the negative live-vault-request smoke. Requires an account with usage; a free-plan quota reset is sufficient.
2. **Second independent conformant client** — install one of:
   - **Kiro** (supports Agent Plugins; needs install + sign-in) — preferred documented root-`plugin.json` consumer;
   - **VS Code + GitHub Copilot / VS Code agent skills** (not installed);
   - **Gemini CLI / opencode / Windsurf** (not installed; verify docs for root `plugin.json` support before counting);
   - **Codex CLI or Claude Code** — would require an explicit decision to treat their native manifests (`.codex-plugin/plugin.json` / `.claude-plugin/plugin.json`) as acceptable, which contradicts the "portable package unchanged" gate.
3. For the chosen client: load the exact committed package (root `plugin.json`, byte-verified), confirm both Skills discoverable, run positive + negative smokes, snapshot → restore config.

## 8. Cleanup confirmation

- `%USERPROFILE%\.cursor\plugins\local\` restored to pre-test state (empty); no persistent client configuration change (Codex/Claude configs untouched).
- Package `agent-plugins/opencare-trust/` verified byte-identical to the committed tree (§1 cross-check: all 15 files match their blobs).
- Nothing committed by this investigation; this evidence file's updates are uncommitted working-tree changes (operator decides on commit). No tokens/keys/credentials read or recorded; no accounts signed into; no paid services enabled.
