"""Portable fixture invariants for ``fixtures/agent-trust/``.

Every fixture is synthetic/offline: it carries no authorization power and no
real health data. These tests pin the semantics (allowed Envelope verifies;
allowed Receipt links to it; refusals never claim completion; unsupported
actions stay fail-closed; tampering is detected; regeneration is
byte-identical).
"""

from __future__ import annotations

from pathlib import Path

from app.agent_trust.cli import main
from app.agent_trust.fixtures import FIXTURE_NOW
from app.agent_trust.models import ExecutionReceipt, TrustEnvelope
from app.agent_trust.validation import validate_envelope_bytes, validate_receipt_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "fixtures" / "agent-trust"

ZERO_ENVELOPE_ID = f"sha256:{'0' * 64}"

FIXTURE_FILENAMES = (
    "allowed-envelope.json",
    "allowed-receipt.json",
    "refused-before-envelope-receipt.json",
    "unsupported-action-receipt.json",
)


def _read(filename: str) -> bytes:
    return (FIXTURES_DIR / filename).read_bytes()


def _envelope() -> TrustEnvelope:
    return TrustEnvelope.model_validate_json(_read("allowed-envelope.json"), strict=False)


def _receipt(filename: str) -> ExecutionReceipt:
    return ExecutionReceipt.model_validate_json(_read(filename), strict=False)


def test_allowed_envelope_validates() -> None:
    result = validate_envelope_bytes(_read("allowed-envelope.json"), at=FIXTURE_NOW)
    assert result.valid
    assert result.envelope_id == _envelope().envelope_id


def test_allowed_receipt_validates_and_links_to_envelope() -> None:
    envelope = _envelope()
    receipt = _receipt("allowed-receipt.json")
    assert receipt.status == "completed"
    assert receipt.output_sha256 is not None
    assert not receipt.reason_codes
    assert receipt.envelope_id == envelope.envelope_id
    result = validate_receipt_bytes(
        _read("allowed-receipt.json"), envelope=envelope, at=FIXTURE_NOW
    )
    assert result.valid
    assert result.receipt_id == receipt.receipt_id


def test_refused_receipt_does_not_claim_a_completed_envelope() -> None:
    receipt = _receipt("refused-before-envelope-receipt.json")
    assert receipt.status == "refused"
    assert receipt.output_sha256 is None
    assert receipt.reason_codes == ["safety_refused"]
    # It references the same Envelope identity as the allowed Receipt...
    assert receipt.envelope_id == _envelope().envelope_id
    # ...but integrity validation passes only for the refused shape, never
    # implying completion: a Receipt alone does not prove a completed Envelope.
    standalone = validate_receipt_bytes(
        _read("refused-before-envelope-receipt.json"), envelope=None, at=FIXTURE_NOW
    )
    assert standalone.valid
    assert receipt.status != "completed"


def test_unsupported_action_receipt_stays_fail_closed() -> None:
    receipt = _receipt("unsupported-action-receipt.json")
    assert receipt.status == "refused"
    assert receipt.output_sha256 is None
    assert receipt.reason_codes == ["unsupported_action"]
    assert receipt.envelope_id == ZERO_ENVELOPE_ID
    # Standalone integrity holds, but the Receipt cannot be linked to the real
    # Envelope: an unsupported action never received one.
    standalone = validate_receipt_bytes(
        _read("unsupported-action-receipt.json"), envelope=None, at=FIXTURE_NOW
    )
    assert standalone.valid
    linked = validate_receipt_bytes(
        _read("unsupported-action-receipt.json"), envelope=_envelope(), at=FIXTURE_NOW
    )
    assert not linked.valid
    assert "receipt_exceeds_envelope" in linked.reason_codes


def test_tampering_changes_verification_result() -> None:
    envelope_data = _read("allowed-envelope.json")
    tampered_envelope = envelope_data.replace(b'"person-alice"', b'"person-mallory"', 1)
    assert tampered_envelope != envelope_data
    assert not validate_envelope_bytes(tampered_envelope, at=FIXTURE_NOW).valid

    receipt_data = _read("allowed-receipt.json")
    tampered_receipt = receipt_data.replace(b'"context.read"', b'"brief.draft"', 1)
    assert tampered_receipt != receipt_data
    assert not validate_receipt_bytes(
        tampered_receipt, envelope=_envelope(), at=FIXTURE_NOW
    ).valid


def test_regeneration_is_byte_identical(tmp_path: Path) -> None:
    assert main(["regenerate-fixtures", "--output", str(tmp_path)]) == 0
    for filename in FIXTURE_FILENAMES:
        assert (tmp_path / filename).read_bytes() == _read(filename)


def test_no_fixture_is_reusable_as_live_authorization() -> None:
    readme = (FIXTURES_DIR / "README.md").read_text(encoding="utf-8").lower()
    for marker in (
        "synthetic / offline",
        "not authorization",
        "not real health data",
        "nothing in this directory",
        "grants access to a live opencare installation",
    ):
        assert marker in readme

    envelope = _envelope()
    assert envelope.actor_id == "actor-alice"
    assert envelope.person_id == "person-alice"
    snapshot = envelope.authorization.snapshot
    assert snapshot is not None
    assert snapshot.credential_id == "credential-alice"
    assert snapshot.consent_event_id == "consent-alice"
    # Only the fixed synthetic identity set appears anywhere in the fixtures.
    synthetic_ids = {
        "actor-alice",
        "credential-alice",
        "person-alice",
        "person-carol",
        "evidence-medication-alice",
        "evidence-medication-carol",
        "consent-alice",
        "consent-revoked",
        "assignment-alice",
        "source-alice",
        "source-carol",
    }
    for filename in FIXTURE_FILENAMES:
        for match in _opaque_id_tokens(_read(filename).decode("utf-8")):
            assert match in synthetic_ids, f"{filename}: unexpected identity {match!r}"


def _opaque_id_tokens(text: str) -> list[str]:
    import re

    return re.findall(
        r'"((?:actor|credential|person|consent|assignment|source|evidence)-[a-z-]+)"',
        text,
    )
