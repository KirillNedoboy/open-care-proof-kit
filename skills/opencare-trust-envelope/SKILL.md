---
name: opencare-trust-envelope
description: Inspects OpenCare Trust Envelopes and Execution Receipts, explains provenance, policy, disclosure, and authorization-snapshot fields, and integrates the OpenCare trust contract. Activate when a developer asks to verify an envelope or receipt, understand its fields, or distinguish verification from current authorization. Never fabricates or mints authorization.
---

# OpenCare Trust Envelope

## Purpose

Use this skill when a developer asks you to work with the OpenCare portable
trust contract: inspect a Trust Envelope, verify an Execution Receipt,
understand provenance / policy / disclosure fields, integrate the OpenCare
trust contract, or distinguish verification from current authorization. This
skill is generic and is not specific to health or to any one product.

This skill is read-only. It never mints, signs, or fabricates authorization.

## Core invariants

- **Envelope verification != current authorization.** A valid, unexpired
  Envelope is an integrity and provenance artifact. It does not grant access
  today; authorization is a live decision supplied by an authority adapter.
- **Receipt verification != current access.** A verified Execution Receipt
  records that an execution happened. It is not a credential and does not open
  access.
- **Hash integrity != signer authenticity.** Matching hashes prove the bytes
  are the ones that were hashed. They do not prove who produced an artifact or
  that it was authorized.

Never claim that an Envelope or Receipt authorizes anything. If the material
does not contain the evidence you need, say so instead of guessing.

## What to do

1. Read the artifact JSON. If the `opencare-trust` CLI is available, prefer it
   for offline verification:
   `opencare-trust verify-envelope --envelope <path> [--at <UTC>]` and
   `opencare-trust verify-receipt --receipt <path> --envelope <path>
   [--at <UTC>]`. Exit code `0` means the artifact passed offline
   verification, `1` means rejection, `2` means a usage error.
2. Explain the fields the developer asked about, using
   `references/PROTOCOL.md` for the field-by-field contract reference.
3. For a worked example, verify the bundled synthetic fixtures in `assets/`
   against their JSON Schemas with `--at 2027-08-02T10:00:00Z`.
4. State what verification proves and what it does not prove, using the core
   invariants above.

## Bundled material

- `references/PROTOCOL.md` — contract reference: envelope, receipt, and
  authorization-snapshot fields plus verification semantics.
- `assets/trust-envelope.schema.json`, `assets/execution-receipt.schema.json`,
  `assets/authorization-snapshot.schema.json` — the three JSON Schemas.
- `assets/allowed-envelope.json`, `assets/allowed-receipt.json` — synthetic
  fixtures that verify offline (fixed clock `2027-08-02T10:00:00Z`).

Contract version literals are `opencare-trust-envelope/1` and
`opencare-execution-receipt/1`. The schemas and fixtures are synthetic and
offline; none of them grant access to any system.
