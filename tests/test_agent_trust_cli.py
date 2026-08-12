from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from app.agent_trust.builders import build_execution_receipt
from app.agent_trust.canonical import canonical_bytes
from app.agent_trust.cli import main
from app.agent_trust.models import TrustEnvelope


def test_export_verify_and_redacted_inspect(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    envelope_path = tmp_path / "envelope.json"
    exported = main(
        [
            "export-envelope",
            "--demo",
            "--person-id",
            "person-alice",
            "--purpose",
            "visit_preparation",
            "--action",
            "summarize_records",
            "--requested-action",
            "Summarize selected records.",
            "--evidence-id",
            "evidence-medication-alice",
            "--tool",
            "context.read",
            "--tool",
            "source.read",
            "--output",
            str(envelope_path),
        ]
    )
    assert exported == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True

    assert main(["verify-envelope", "--envelope", str(envelope_path)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True

    assert main(["inspect-envelope", "--envelope", str(envelope_path)]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["person_id"] == "person-alice"
    assert inspected["evidence"] == [
        {
            "content_sha256": inspected["evidence"][0]["content_sha256"],
            "evidence_id": "evidence-medication-alice",
            "evidence_type": "medication_record",
        }
    ]
    rendered = json.dumps(inspected)
    assert "synthetic medication record" not in rendered
    assert "credential-alice" not in rendered

    envelope = TrustEnvelope.model_validate_json(envelope_path.read_bytes(), strict=False)
    receipt = build_execution_receipt(
        envelope=envelope,
        started_at=envelope.issued_at + timedelta(seconds=1),
        completed_at=envelope.issued_at + timedelta(seconds=2),
        status="completed",
        provider_id=None,
        used_evidence_ids=["evidence-medication-alice"],
        used_tools=["context.read"],
        output=b"safe output",
        reason_codes=[],
    )
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_bytes(canonical_bytes(receipt) + b"\n")
    assert (
        main(
            [
                "verify-receipt",
                "--receipt",
                str(receipt_path),
                "--envelope",
                str(envelope_path),
                "--at",
                envelope.issued_at.isoformat(),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["valid"] is True


def test_export_cannot_mint_wrong_person_or_external_disclosure(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    result = main(
        [
            "export-envelope",
            "--demo",
            "--person-id",
            "person-carol",
            "--purpose",
            "visit_preparation",
            "--action",
            "summarize_records",
            "--requested-action",
            "Summarize records.",
            "--evidence-id",
            "evidence-medication-carol",
            "--tool",
            "context.read",
            "--output",
            str(tmp_path / "denied.json"),
        ]
    )
    assert result == 1
    assert json.loads(capsys.readouterr().out)["reason_codes"] == ["person_access_denied"]
    assert not (tmp_path / "denied.json").exists()
