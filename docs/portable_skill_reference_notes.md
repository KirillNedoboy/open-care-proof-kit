# Portable Skill Reference Notes

## https://github.com/realactivity/tula

- Detected license: Apache-2.0.
- Useful conceptual pattern: a health-agent repository can organize reusable
  skill instructions and keep explicit safety boundaries near skill guidance.
- Not copied: source code, prompts, schemas, assets, branding, evaluation
  material, deployment design, or health-data examples.
- Original OpenCare implementation: one canonical portable folder, explicit
  JSON contracts, and reuse of OpenCare policy, context, validation, and
  deterministic service code.

## https://github.com/Rai220/my-health-public

- Detected license: MIT.
- Useful conceptual pattern: structured health records benefit from clear date,
  source, status, and visit-preparation conventions.
- Not copied: source code, instructions, documentation, schemas, branding, or
  examples containing personal or genetic data.
- Original OpenCare implementation: a redacted context packet with source IDs,
  evidence status, explicit unknowns, and medical-decision refusals.

Both repositories were inspected only under ignored `.tmp/upstream/`.
