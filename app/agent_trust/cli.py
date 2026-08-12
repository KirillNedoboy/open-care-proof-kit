from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.agent_trust.builders import BuildRefused, EnvelopeRequest, TrustedEnvelopeBuilder
from app.agent_trust.canonical import canonical_bytes, strict_json_loads
from app.agent_trust.models import TrustEnvelope
from app.agent_trust.testing import SyntheticAuthority
from app.agent_trust.validation import validate_envelope_bytes, validate_receipt_bytes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.agent_trust.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export-envelope")
    export.add_argument("--demo", action="store_true", required=True)
    export.add_argument("--actor-id", default="actor-alice")
    export.add_argument("--credential-id", default="credential-alice")
    export.add_argument("--person-id", required=True)
    export.add_argument(
        "--purpose",
        choices=("visit_preparation", "record_explanation", "clinician_briefing"),
        required=True,
    )
    export.add_argument(
        "--action",
        choices=("answer_question", "draft_visit_brief", "summarize_records"),
        required=True,
    )
    export.add_argument("--requested-action", required=True)
    export.add_argument("--evidence-id", action="append", required=True)
    export.add_argument("--tool", action="append", required=True)
    export.add_argument("--output", type=Path, required=True)

    verify = commands.add_parser("verify-envelope")
    verify.add_argument("--envelope", type=Path, required=True)
    verify.add_argument("--at")
    inspect = commands.add_parser("inspect-envelope")
    inspect.add_argument("--envelope", type=Path, required=True)
    receipt = commands.add_parser("verify-receipt")
    receipt.add_argument("--receipt", type=Path, required=True)
    receipt.add_argument("--envelope", type=Path, required=True)
    receipt.add_argument("--at")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export-envelope":
        return _export(args)
    if args.command == "verify-envelope":
        return _verify_envelope(args.envelope, _parse_at(args.at))
    if args.command == "inspect-envelope":
        return _inspect(args.envelope)
    if args.command == "verify-receipt":
        return _verify_receipt(args.receipt, args.envelope, _parse_at(args.at))
    return 2


def _export(args: argparse.Namespace) -> int:
    now = datetime.now(UTC)
    try:
        request = EnvelopeRequest(
            actor_id=args.actor_id,
            credential_id=args.credential_id,
            person_id=args.person_id,
            purpose_id=args.purpose,
            action_id=args.action,
            requested_action=args.requested_action,
            requested_tools=sorted(args.tool),
            evidence_ids=sorted(args.evidence_id),
            disclosure_mode="local_only",
            provider_id=None,
            consent_basis_id="consent-alice",
            ttl_seconds=300,
        )
        envelope = TrustedEnvelopeBuilder(
            SyntheticAuthority.allowed(now=now), clock=lambda: now
        ).build(request)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_bytes(envelope) + b"\n")
    except (BuildRefused, OSError, ValidationError, ValueError) as exc:
        reasons = exc.reason_codes if isinstance(exc, BuildRefused) else ["trust_envelope_failed"]
        return _print_result(False, reasons)
    return _print_result(True, [], envelope_id=envelope.envelope_id)


def _verify_envelope(path: Path, at: datetime) -> int:
    try:
        result = validate_envelope_bytes(path.read_bytes(), at=at)
    except OSError:
        return _print_result(False, ["invalid_contract"])
    return _print_result(result.valid, result.reason_codes, envelope_id=result.envelope_id)


def _inspect(path: Path) -> int:
    try:
        data = path.read_bytes()
        raw = data[:-1] if data.endswith(b"\n") else data
        strict_json_loads(raw)
        envelope = TrustEnvelope.model_validate_json(raw, strict=False)
        result = validate_envelope_bytes(data, at=envelope.issued_at)
    except (OSError, ValueError, ValidationError):
        return _print_result(False, ["invalid_contract"])
    if not result.valid:
        return _print_result(False, result.reason_codes)
    print(
        json.dumps(
            {
                "valid": True,
                "contract_version": envelope.contract_version,
                "envelope_id": envelope.envelope_id,
                "issued_at": envelope.issued_at.isoformat(),
                "expires_at": envelope.expires_at.isoformat(),
                "actor_id": envelope.actor_id,
                "person_id": envelope.person_id,
                "purpose_id": envelope.purpose_id,
                "action_id": envelope.action_id,
                "resource_scopes": envelope.resource_scopes,
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "evidence_type": item.evidence_type,
                        "content_sha256": item.content_sha256,
                    }
                    for item in envelope.evidence
                ],
                "disclosure_mode": envelope.provider_disclosure.mode,
                "allowed_tools": envelope.allowed_tools,
                "prohibited_operations": envelope.prohibited_operations,
                "disclosure_constraints": envelope.disclosure_constraints,
                "limitations": envelope.limitations,
                "safety_notices": envelope.safety_notices,
                "final_decision": envelope.final_decision.decision,
            },
            sort_keys=True,
        )
    )
    return 0


def _verify_receipt(receipt_path: Path, envelope_path: Path, at: datetime) -> int:
    try:
        envelope_data = envelope_path.read_bytes()
        raw = envelope_data[:-1] if envelope_data.endswith(b"\n") else envelope_data
        strict_json_loads(raw)
        envelope = TrustEnvelope.model_validate_json(raw, strict=False)
        envelope_result = validate_envelope_bytes(envelope_data, at=at)
        if not envelope_result.valid:
            return _print_result(False, envelope_result.reason_codes)
        result = validate_receipt_bytes(receipt_path.read_bytes(), envelope=envelope, at=at)
    except (OSError, ValueError, ValidationError):
        return _print_result(False, ["invalid_contract"])
    return _print_result(result.valid, result.reason_codes, receipt_id=result.receipt_id)


def _parse_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise argparse.ArgumentTypeError("--at must be a UTC RFC 3339 instant")
    return parsed


def _print_result(
    valid: bool,
    reason_codes: list[str],
    *,
    envelope_id: str | None = None,
    receipt_id: str | None = None,
) -> int:
    payload: dict[str, object] = {
        "valid": valid,
        "status": "accepted" if valid else "rejected",
        "reason_codes": reason_codes,
    }
    if envelope_id is not None:
        payload["envelope_id"] = envelope_id
    if receipt_id is not None:
        payload["receipt_id"] = receipt_id
    print(json.dumps(payload, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
