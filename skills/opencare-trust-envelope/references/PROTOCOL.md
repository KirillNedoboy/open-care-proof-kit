# OpenCare Trust Protocol Reference

Generic, read-only reference for the OpenCare portable trust contract.
Verification and explanation only: this material never mints, signs, or
fabricates authorization.

Contract version literals:

- Trust Envelope: `opencare-trust-envelope/1`
- Execution Receipt: `opencare-execution-receipt/1`

The machine-readable contract is the JSON Schema in `assets/`
(`trust-envelope.schema.json`, `execution-receipt.schema.json`,
`authorization-snapshot.schema.json`). This document explains the fields and
the semantics; the schema is authoritative.

## 1. Trust Envelope

A Trust Envelope is a portable, Person-scoped artifact that records what a
specific Actor was authorized to do with a specific Person's context, under
which consent and policy, and under which constraints. It is a provenance and
integrity artifact, not a live capability.

Top-level fields:

- `envelope_id` — `sha256:<64 hex>` digest over the identity payload;
  deterministic identity and integrity, never signer authenticity.
- `contract_version` — MUST be the literal `opencare-trust-envelope/1`.
- `issued_at`, `expires_at` — trusted-clock timestamps; verification checks
  that `expires_at` is later than issuance and not before the verification
  time.
- `actor_id`, `person_id` — the acting identity and the Person whose context
  is in scope.
- `purpose_id` — one of `visit_preparation`, `record_explanation`,
  `clinician_briefing`.
- `action_id` — one of `answer_question`, `draft_visit_brief`,
  `summarize_records`.
- `requested_action` — the human-readable action statement.
- `resource_scopes` — the resource scopes the Envelope covers.
- `allowed_tools` — a non-empty subset of `context.read`, `source.read`,
  `brief.draft`.
- `prohibited_operations` — operations that are never allowed under this
  Envelope.
- `disclosure_constraints` — constraints on what may be disclosed (for
  example `disclose_only_selected_fields`,
  `do_not_retain_beyond_declared_retention`).
- `limitations` — non-empty list of boundary statements.
- `safety_notices` — non-empty list of notices that must accompany any output.
- `evidence` — non-empty list of `EvidenceItem` entries: `evidence_id`,
  `evidence_type`, `person_id`, `resource_scope`, `content_sha256`,
  `source_ids`, `provenance_status` (`source_backed` | `user_asserted`),
  `selected_fields`, `observed_at`.
- `authorization` — `AuthorizationDecision`: `decision`
  (`allow` | `deny`), `reason_codes`, and an optional `snapshot`
  (see §3).
- `safety` — `SafetyDecision`: `decision` (`allow` | `refuse`),
  `reason_codes`, `policy_version`, `evaluated_at`, `limitations`,
  `required_notices`.
- `final_decision` — `FinalDecision`: `decision` (`allow` | `refuse`) and
  `reason_codes`.
- `provider_disclosure` — `ProviderDisclosure`: `mode`
  (`local_only` | `external_provider`), `consent_basis_id`,
  `allowed_evidence_ids`, `allowed_fields`, `prohibited_data_classes`,
  `retention` (`request_only` | `provider_policy`), and an optional
  `provider_descriptor` (`provider_id`, `provider_kind`, `endpoint_class`,
  `external`, `model_id`, `descriptor_hash`).

Verifying an Envelope checks schema conformance, integrity identity, and
temporal/invariant rules offline. It does not contact any live system and it
does not re-check consent or policy.

## 2. Execution Receipt

An Execution Receipt is an observed-facts record of one execution attempt
against an Envelope identity.

Fields:

- `receipt_id` — `sha256:<64 hex>`; deterministic identity of the Receipt.
- `envelope_id` — the Envelope identity the execution was attempted under.
- `contract_version` — MUST be the literal `opencare-execution-receipt/1`.
- `started_at`, `completed_at` — execution timestamps.
- `status` — terminal status (`completed` | `refused` | ...); only
  `completed` executions carry an `output_sha256`.
- `used_evidence_ids`, `used_tools` — what the execution consumed; must be a
  subset of what the Envelope allows.
- `output_sha256` — digest of the produced output; present only for
  `completed`.
- `reason_codes` — refusal/unsupported reasons; a `refused` Receipt claims
  nothing was executed.
- `receipt_sha256` — digest of the Receipt itself.
- `model_id`, `provider_id`, `provider_kind`, `external` — optional provider
  identity observed during execution.

A Receipt alone does not prove a completed Envelope: `refused` Receipts link
to the same Envelope identity but record non-execution. Completion requires
`status: completed` plus an `output_sha256`, verified against a valid,
unexpired Envelope.

## 3. Authorization Snapshot

The `snapshot` inside an Envelope's `authorization` decision records the
authorization state at issuance time. It is a point-in-time record, not a
live decision.

Fields:

- `actor_id`, `credential_id`, `person_id`, `assignment_id` — identities.
- `role` — `owner` or `caregiver`.
- `granted_scopes` — non-empty scopes granted by the assignment.
- `required_scopes` — non-empty scopes the action required.
- `consent_event_id` — the consent event the assignment derives from.
- `authorized_at` — when the assignment was authorized.
- `access_expires_at` — optional; when access lapses.
- `policy_version` — the policy version applied.

The snapshot is evidence about a past decision. Current authorization is a
live decision made by an authority adapter at request time; the snapshot
neither grants nor proves access now.

## 4. What verification proves and what it does not

- Envelope verification != current authorization. A valid, unexpired
  Envelope proves integrity and provenance, not that the actor may act today.
- Receipt verification != current access. A verified Receipt proves an
  execution record, not a right to access anything.
- Hash integrity != signer authenticity. Hashes prove byte identity only;
  they do not prove who created an artifact or that it was authorized.
- Nothing in this package turns JSON into authorization. There is no live
  minting path; the synthetic `export-envelope` command builds Envelopes only
  from the repository's fixed synthetic authority.

## 5. CLI

The trust CLI is exposed as `opencare-trust` or
`python -m app.agent_trust.cli`. Exit codes: `0` accepted, `1` rejection,
`2` usage error. Machine output is JSON.

Commands:

- `verify-envelope --envelope PATH [--at UTC]` — offline integrity/schema/
  invariant verification; never live authority.
- `inspect-envelope --envelope PATH` — verified, redacted summary; never
  prints payloads or credentials.
- `verify-receipt --receipt PATH --envelope PATH [--at UTC]` — Receipt
  integrity and Envelope-subset constraints.
- `export-envelope` — synthetic Envelope from the fixed demo authority only.
- `export-schemas` — deterministic schema export to `schemas/agent-trust/`.
- `regenerate-fixtures` — deterministic fixture regeneration.

Use `--at` with the bundled fixtures: their clock is fixed at
`2027-08-02T10:00:00Z`.

## 6. Integration guidance

When integrating the OpenCare trust contract into a downstream agent:

1. Verify before you rely: run the artifact through the schema and the CLI
   checks before interpreting any field.
2. Treat `allowed_tools`, `resource_scopes`, and `evidence` as the exact
   surface an agent may touch; never broaden it.
3. Keep disclosure inside `disclosure_constraints` and `allowed_fields`;
   never leak fields outside them.
4. Re-check authorization at request time through the live authority adapter;
   never treat a stored Envelope or Receipt as a current grant.
5. If anything is missing or ambiguous, report the gap. Never fabricate an
   authorization decision, a consent event, or a receipt.

Synthetic fixtures in `assets/` use the fixed identities `actor-alice`,
`credential-alice`, `person-alice`, `evidence-medication-alice`,
`consent-alice`. These are not real identities or consent events and are not
reusable as live authorization.
