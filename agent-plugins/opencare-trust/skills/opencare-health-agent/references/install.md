# Manual Installation

OpenCare does not automatically install this skill into global profiles or
overwrite workspace instructions.

## Codex-style repository agents

1. Copy `skills/opencare-health-agent/` into the workspace.
2. Add this reference to the repository agent instructions:

```text
For OpenCare context packets, follow skills/opencare-health-agent/SKILL.md.
Return JSON matching answer.schema.json and validate it with app.agent.cli.
```

## Claude Code-style repository agents

1. Copy the folder into the workspace.
2. Add the same reference manually to the workspace `CLAUDE.md` or equivalent.
3. Do not overwrite an existing instruction file.

## Generic file-based agents

1. Copy the folder into the workspace.
2. Give the agent `SKILL.md`, a context packet, and the user question.
3. Require an answer matching `answer.schema.json`.
4. Validate the answer:

```text
python -m app.agent.cli validate-answer --context context.json --answer answer.json
```

Export packets with `export-context`. A local-file export uses the existing
validated OpenCare configuration and never accepts secrets as CLI arguments.
