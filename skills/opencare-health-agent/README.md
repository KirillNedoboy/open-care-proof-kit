# Portable OpenCare Health Agent Skill

This canonical skill package lets another file-based agent work from an exported
OpenCare context packet while preserving source, uncertainty, and medical-boundary
rules. It does not add a model provider, document ingestion, uploads, accounts,
MCP integration, or chat persistence.

## Contents

- `SKILL.md`: standalone agent instruction contract
- `context.schema.json`: safe context-packet shape
- `answer.schema.json`: guarded answer shape
- `install.md`: manual installation patterns
- `examples.md`: synthetic allowed and blocked examples

Export a context packet and validate an answer:

```text
python -m app.agent.cli export-context --vault-source demo --output context.json
python -m app.agent.cli validate-answer --context context.json --answer answer.json
```

OpenCare validates output, but cannot guarantee medical correctness.
