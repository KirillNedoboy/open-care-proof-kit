"""Adversarial corpus driver.

Runs one scenario against the real ``app.agent.g2_runtime.G2Runtime`` (with the
trusted builders, an extended synthetic authority, and a scripted provider) and
records a structured ``CaseResult``. The driver never short-circuits the trust
layer: every refusal is produced by the existing G2 contract, not by a
test-local policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from app.agent.g2_runtime import G2Runtime
from app.agent.providers.contract import ProviderExecutionRequest
from app.agent_trust.builders import BuildRefused, EnvelopeRequest, TrustedEnvelopeBuilder
from app.agent_trust.canonical import canonical_bytes
from app.agent_trust.fixtures import FIXTURE_NOW
from app.agent_trust.identifiers import ToolId
from app.agent_trust.models import ExecutionReceipt, TrustEnvelope
from app.agent_trust.validation import validate_envelope_bytes, validate_receipt_bytes
from app.family_access.sessions import SessionStore
from evals.g5.authority import DescriptorBox, G5Authority
from evals.g5.corpus import Phase, Scenario
from evals.g5.providers import SCRIPTS, RecordingProvider, descriptor_contract

#: Fixed synthetic clock for deterministic replay (matches the G4 fixtures).
HARNESS_NOW = FIXTURE_NOW

_TTL_SECONDS = 900


class MemoryG2Repository:
    """In-memory G2 repository recording receipts and consent."""

    def __init__(self) -> None:
        self.receipts: list[tuple[str, ExecutionReceipt, bool]] = []
        self.consents: list[dict[str, object]] = []

    def save_consent(self, **kwargs: Any) -> None:
        self.consents.append(dict(kwargs))

    def save_execution_receipt(
        self,
        receipt: ExecutionReceipt,
        *,
        execution_id: str,
        consent_id: str,
        actor_id: str,
        person_id: str,
        mutation_attempted: bool,
    ) -> None:
        del consent_id, actor_id, person_id
        self.receipts.append((execution_id, receipt, mutation_attempted))

    def get_execution_receipt(self, execution_id: str) -> ExecutionReceipt | None:
        for stored_id, receipt, _ in self.receipts:
            if stored_id == execution_id:
                return receipt
        return None


@dataclass
class CaseResult:
    case_id: str
    category: str
    kind: str
    passed: bool = True
    failures: list[str] = field(default_factory=list)
    outcome: str = "unset"
    reason_codes: list[str] = field(default_factory=list)
    provider_calls: int = 0
    provider_evidence_ids: list[list[str]] = field(default_factory=list)
    consented_at_call: list[bool] = field(default_factory=list)
    external_calls_without_consent: int = 0
    mutation_attempted: bool = False
    canonical_state_unchanged: bool = True
    receipts: list[ExecutionReceipt] = field(default_factory=list)
    receipt_verification_failures: int = 0
    envelope_id: str | None = None
    envelope_bytes: bytes | None = None
    receipt_bytes: bytes | None = None
    eligible_evidence_ids: list[str] = field(default_factory=list)
    disclosed_evidence_ids: list[str] = field(default_factory=list)
    expected_evidence_ids: list[str] = field(default_factory=list)
    forbidden_evidence_ids: list[str] = field(default_factory=list)
    selected_evidence_ids: list[str] = field(default_factory=list)
    provider_answers: list[dict[str, Any] | None] = field(default_factory=list)
    envelope_source_ids: list[str] = field(default_factory=list)


def _allowed_fields(authority: G5Authority, evidence_ids: list[str]) -> list[str]:
    fields: set[str] = set()
    for evidence_id in evidence_ids:
        record = authority.evidence.get(evidence_id)
        if record is not None:
            fields.update(record.selected_fields)
    return sorted(fields)


def _eligible_evidence_ids(authority: G5Authority, person_id: str) -> list[str]:
    return sorted(
        evidence_id
        for evidence_id, record in authority.evidence.items()
        if record.person_id == person_id and record.source_ids
    )



def _apply_phase(authority: G5Authority, box: DescriptorBox, phase: Phase) -> None:
    if phase.op == "revoke_actor":
        assert phase.actor_id is not None
        authority.revoke_actor(phase.actor_id)
    elif phase.op == "revoke_consent":
        assert phase.actor_id is not None and phase.person_id is not None
        authority.revoke_consent(phase.actor_id, phase.person_id)
    elif phase.op == "mutate_evidence":
        assert phase.evidence_id is not None and phase.content is not None
        authority.mutate_evidence_content(phase.evidence_id, phase.content.encode("utf-8"))
    elif phase.op == "swap_provider":
        assert phase.provider_id is not None
        box.swap_provider(phase.provider_id)
    elif phase.op == "swap_model":
        assert phase.model_id is not None
        box.swap_model(phase.model_id)
    else:
        raise ValueError(f"unknown phase op {phase.op!r}")


class _Harness:
    def __init__(self, scenario: Scenario, now: datetime, tmp_dir: Path) -> None:
        self.scenario = scenario
        self.now = now
        self.authority = G5Authority.seeded(now=now)
        self.box = DescriptorBox(
            provider_id=scenario.provider.provider_id, model_id=scenario.provider.model_id
        )
        self.consent_granted = False
        self.provider = RecordingProvider(
            self.box,
            SCRIPTS[scenario.provider.script],
            consent_ok=lambda: self.consent_granted,
        )
        self.repository = MemoryG2Repository()
        self.built_envelopes: list[TrustEnvelope] = []
        self.evidence_snapshot: dict[str, bytes] = {}
        self._execution_id = ""
        builder = TrustedEnvelopeBuilder(self.authority, clock=lambda: now)

        def _prepare_envelope(
            *,
            actor_id: str,
            person_id: str,
            purpose_id: Any,
            action_id: Any,
            question: str,
        ) -> TrustEnvelope:
            del question
            request = EnvelopeRequest(
                actor_id=actor_id,
                credential_id=scenario.credential_id,
                person_id=person_id,
                purpose_id=purpose_id,
                action_id=action_id,
                requested_action=scenario.requested_action,
                requested_tools=cast(list[ToolId], sorted(scenario.requested_tools)),
                evidence_ids=sorted(scenario.evidence_ids),
                disclosure_mode="local_only",
                provider_id=None,
                provider_descriptor=descriptor_contract(self.box),
                consent_basis_id=f"consent-{person_id.removeprefix('person-')}",
                ttl_seconds=_TTL_SECONDS,
            )
            envelope = builder.build(request)
            self.built_envelopes.append(envelope)
            return envelope

        store = SessionStore(tmp_dir / "sessions.sqlite", clock=lambda: now)
        created = store.create(scenario.actor_id, scenario.credential_id)
        store.set_active_person(created.session_token, scenario.person_id)

        def _revalidate(pending: Any, session: Any) -> bool:
            del session
            return self.authority.consent_is_active(pending.actor_id, pending.person_id)

        self.runtime = G2Runtime(
            store,
            prepare_envelope=_prepare_envelope,
            revalidate=_revalidate,
            provider=self.provider,
            repository=self.repository,
            clock=lambda: now,
        )
        self.token = created.session_token
        self.snapshot_evidence()

    def snapshot_evidence(self) -> None:
        self.evidence_snapshot = {
            evidence_id: record.content for evidence_id, record in self.authority.evidence.items()
        }


def _evidence_ids_in_payload(payload: ProviderExecutionRequest) -> list[str]:
    return sorted(item["evidence_id"] for item in payload.evidence)


def run_scenario(scenario: Scenario, now: datetime, tmp_dir: Path) -> CaseResult:
    result = CaseResult(
        case_id=scenario.case_id,
        category=scenario.category,
        kind=scenario.kind,
        expected_evidence_ids=list(scenario.expected_evidence_ids),
        forbidden_evidence_ids=list(scenario.forbidden_evidence_ids),
    )
    harness = _Harness(scenario, now, tmp_dir)
    result.eligible_evidence_ids = _eligible_evidence_ids(harness.authority, scenario.person_id)
    result.selected_evidence_ids = sorted(scenario.evidence_ids)

    if scenario.kind == "g2_flow":
        outcome, reasons = _drive_flow(scenario, harness)
        result.outcome = outcome
        result.reason_codes = reasons
        _collect(harness, result)
        _assert_flow(scenario, result)
    elif scenario.kind == "tamper_envelope":
        _run_tamper_envelope(harness, result)
    elif scenario.kind == "tamper_receipt":
        _run_tamper_receipt(scenario, harness, result)
    elif scenario.kind == "fixture_misuse":
        _run_fixture_misuse(harness, result)
    elif scenario.kind == "replay":
        _run_replay(scenario, harness, result, tmp_dir)
    else:
        result.passed = False
        result.failures.append(f"unknown scenario kind {scenario.kind!r}")
    return result


def _drive_flow(scenario: Scenario, harness: _Harness) -> tuple[str, list[str]]:
    try:
        prepare_result = harness.runtime.prepare(
            harness.token,
            scenario.question,
            purpose_id=scenario.purpose_id,
            action_id=scenario.action_id,
        )
        harness._execution_id = prepare_result.execution_id
    except BuildRefused as exc:
        return "refused_prepare", exc.reason_codes
    except PermissionError as exc:
        return "refused_prepare", [str(exc)]

    for phase in scenario.phases:
        if phase.after == "prepare":
            _apply_phase(harness.authority, harness.box, phase)

    try:
        fields = _allowed_fields(harness.authority, scenario.evidence_ids)
        harness.runtime.grant_disclosure_consent(
            harness.token, harness._execution_id, fields=fields
        )
        harness.consent_granted = True
    except BuildRefused as exc:
        return "refused_consent", exc.reason_codes
    except PermissionError as exc:
        return "refused_consent", [str(exc)]

    for phase in scenario.phases:
        if phase.after == "grant":
            _apply_phase(harness.authority, harness.box, phase)

    harness.snapshot_evidence()
    try:
        exec_result = harness.runtime.execute(
            harness.token, harness._execution_id, scenario.question
        )
    except BuildRefused as exc:
        return "refused", exc.reason_codes
    except PermissionError as exc:
        return "refused", [str(exc)]

    if exec_result.status == "answered":
        return "answered", []
    return "refused", [exec_result.reason_code or "refused"]


def _collect(harness: _Harness, result: CaseResult) -> None:
    result.provider_calls = harness.provider.calls
    result.consented_at_call = list(harness.provider.consented_at_call)
    result.provider_evidence_ids = [
        _evidence_ids_in_payload(payload) for payload in harness.provider.payloads
    ]
    result.external_calls_without_consent = sum(
        1 for consented in result.consented_at_call if not consented
    )
    result.receipts = [receipt for _, receipt, _ in harness.repository.receipts]
    result.mutation_attempted = any(mutated for _, _, mutated in harness.repository.receipts)
    result.canonical_state_unchanged = all(
        record.content == harness.evidence_snapshot.get(evidence_id)
        for evidence_id, record in harness.authority.evidence.items()
    )
    if harness.built_envelopes:
        envelope = harness.built_envelopes[-1]
        result.envelope_id = envelope.envelope_id
        result.envelope_bytes = canonical_bytes(envelope)
        result.disclosed_evidence_ids = envelope.provider_disclosure.allowed_evidence_ids
        result.envelope_source_ids = sorted(
            {source_id for item in envelope.evidence for source_id in item.source_ids}
        )
    result.provider_answers = list(harness.provider.answers)
    if result.receipts:
        result.receipt_bytes = canonical_bytes(result.receipts[-1])
    _validate_receipts(harness, result)


def _validate_receipts(harness: _Harness, result: CaseResult) -> None:
    if not harness.built_envelopes or not result.receipts:
        return
    envelope = harness.built_envelopes[-1]
    for receipt in result.receipts:
        check = validate_receipt_bytes(
            canonical_bytes(receipt), envelope=envelope, at=harness.now
        )
        if not check.valid:
            result.receipt_verification_failures += 1


def _assert_flow(scenario: Scenario, result: CaseResult) -> None:
    failures: list[str] = []

    if result.outcome != scenario.expected_outcome:
        failures.append(
            f"outcome mismatch: expected {scenario.expected_outcome!r}, got {result.outcome!r}"
        )

    if scenario.expected_reason_codes and set(result.reason_codes) != set(
        scenario.expected_reason_codes
    ):
        failures.append(
            f"reason mismatch: expected {sorted(scenario.expected_reason_codes)}, "
            f"got {sorted(result.reason_codes)}"
        )

    if scenario.provider_must_be_called:
        if result.provider_calls != 1:
            failures.append(f"provider must be called exactly once, got {result.provider_calls}")
    elif result.provider_calls != 0:
        failures.append(f"provider must not be called, got {result.provider_calls}")

    for call_evidence in result.provider_evidence_ids:
        leaked = sorted(set(call_evidence) & set(scenario.forbidden_evidence_ids))
        if leaked:
            failures.append(f"forbidden evidence leaked to provider: {leaked}")

    if result.external_calls_without_consent != 0:
        failures.append(
            f"external calls without consent: {result.external_calls_without_consent}"
        )

    if not result.canonical_state_unchanged:
        failures.append("canonical evidence state changed via the agent path")

    result.passed = not failures
    result.failures = failures


def _run_tamper_envelope(harness: _Harness, result: CaseResult) -> None:
    envelope = _build_valid_envelope(harness)
    valid = canonical_bytes(envelope)
    if not validate_envelope_bytes(valid, at=harness.now).valid:
        result.failures.append("fresh valid envelope did not validate")
    tampered = valid.replace(b'"person-alice"', b'"person-mallory"', 1)
    check = validate_envelope_bytes(tampered, at=harness.now)
    if check.valid:
        result.failures.append("tampered envelope still validates")
    result.envelope_id = envelope.envelope_id
    result.envelope_bytes = valid
    result.outcome = "refused"
    result.reason_codes = sorted(check.reason_codes)
    result.passed = not result.failures


def _run_tamper_receipt(scenario: Scenario, harness: _Harness, result: CaseResult) -> None:
    outcome, reasons = _drive_flow(scenario, harness)
    result.outcome = outcome
    result.reason_codes = reasons
    _collect(harness, result)
    if outcome != "answered" or not result.receipts or not harness.built_envelopes:
        result.failures.append(f"tamper-receipt preflow did not complete: {outcome}")
        result.passed = False
        return

    envelope = harness.built_envelopes[-1]
    receipt = result.receipts[-1]
    good = canonical_bytes(receipt)
    if not validate_receipt_bytes(good, envelope=envelope, at=harness.now).valid:
        result.failures.append("fresh valid receipt did not validate")
    tampered = good.replace(b'"evidence-medication-alice"', b'"evidence-medication-carol"', 1)
    if tampered == good:
        result.failures.append("receipt tamper did not change any byte")
    else:
        check = validate_receipt_bytes(tampered, envelope=envelope, at=harness.now)
        if check.valid:
            result.failures.append("tampered receipt still validates")

    # The runtime must refuse to return a corrupted stored receipt.
    exec_id = harness.repository.receipts[-1][0]
    tampered_receipt = receipt.model_copy(
        update={"used_evidence_ids": ["evidence-medication-carol"]}
    )
    harness.repository.receipts[-1] = (exec_id, tampered_receipt, False)
    if harness.runtime.get_receipt(harness.token, exec_id) is not None:
        result.failures.append("runtime returned a tampered stored receipt")

    result.passed = not result.failures


def _run_fixture_misuse(harness: _Harness, result: CaseResult) -> None:
    from app.agent_trust.fixtures import allowed_envelope

    # The committed fixture is generated from this deterministic builder; we
    # build the synthetic envelope directly to stay independent of the
    # checkout's line-ending conversion (autocrlf), then prove it grants no
    # live access.
    envelope = allowed_envelope()
    fixture_bytes = canonical_bytes(envelope)
    check = validate_envelope_bytes(fixture_bytes, at=harness.now)
    if not check.valid:
        result.failures.append(
            f"committed fixture envelope does not validate: {check.reason_codes}"
        )

    # 2. ... but it grants no live authorization through the G2 runtime.
    try:
        harness.runtime.prepare(
            "no-such-token",
            harness.scenario.question,
            purpose_id=harness.scenario.purpose_id,
            action_id=harness.scenario.action_id,
        )
        result.failures.append("prepare succeeded without a live session")
    except PermissionError:
        pass

    exec_result = harness.runtime.execute(
        "no-such-token", "no-such-execution", harness.scenario.question
    )
    if exec_result.status != "refused":
        result.failures.append("execute succeeded without consent")

    if harness.provider.calls != 0:
        result.failures.append(f"provider called during fixture misuse: {harness.provider.calls}")

    result.outcome = "refused"
    result.provider_calls = harness.provider.calls
    result.reason_codes = [exec_result.reason_code or "context_changed"]
    result.passed = not result.failures


def _run_replay(scenario: Scenario, harness: _Harness, result: CaseResult, tmp_dir: Path) -> None:
    outcome, reasons = _drive_flow(scenario, harness)
    result.outcome = outcome
    result.reason_codes = reasons
    _collect(harness, result)
    if outcome != "answered":
        result.failures.append(f"replay first run did not answer: {outcome}")

    # A second execute on the same execution must be replay-refused.
    replay = harness.runtime.execute(
        harness.token, harness._execution_id, scenario.question
    )
    if replay.status != "refused" or replay.reason_code not in ("replay", "context_changed"):
        result.failures.append(
            f"second execute was not replay-refused: {replay.status}/{replay.reason_code}"
        )

    # Determinism: a fresh identical run must produce identical bytes.
    harness2 = _Harness(scenario, harness.now, tmp_dir / "run2")
    outcome2, _ = _drive_flow(scenario, harness2)
    if outcome2 != "answered":
        result.failures.append(f"replay determinism run did not answer: {outcome2}")
    res2 = CaseResult(case_id=scenario.case_id, category=scenario.category, kind="replay")
    _collect(harness2, res2)
    if res2.envelope_bytes != result.envelope_bytes:
        result.failures.append("envelope bytes differ across identical runs")
    if res2.receipt_bytes != result.receipt_bytes:
        result.failures.append("receipt bytes differ across identical runs")
    if res2.envelope_id != result.envelope_id:
        result.failures.append("envelope identity differs across identical runs")
    if res2.reason_codes != result.reason_codes:
        result.failures.append("reason codes differ across identical runs")

    # Changed semantic input (different evidence selection) -> different identity.
    changed = scenario.model_copy(
        update={"evidence_ids": ["evidence-medication-alice", "evidence-lab-alice"]}
    )
    harness3 = _Harness(changed, harness.now, tmp_dir / "run3")
    outcome3, _ = _drive_flow(changed, harness3)
    if outcome3 != "answered":
        result.failures.append(f"changed-input run did not answer: {outcome3}")
    res3 = CaseResult(case_id=scenario.case_id, category=scenario.category, kind="replay")
    _collect(harness3, res3)
    if res3.envelope_id == result.envelope_id:
        result.failures.append("changed semantic input produced identical envelope identity")

    result.passed = not result.failures


def _build_valid_envelope(harness: _Harness) -> TrustEnvelope:
    request = EnvelopeRequest(
        actor_id=harness.scenario.actor_id,
        credential_id=harness.scenario.credential_id,
        person_id=harness.scenario.person_id,
        purpose_id=harness.scenario.purpose_id,
        action_id=harness.scenario.action_id,
        requested_action=harness.scenario.requested_action,
        requested_tools=cast(list[ToolId], sorted(harness.scenario.requested_tools)),
        evidence_ids=sorted(harness.scenario.evidence_ids),
        disclosure_mode="local_only",
        provider_id=None,
        provider_descriptor=descriptor_contract(harness.box),
        consent_basis_id=f"consent-{harness.scenario.person_id.removeprefix('person-')}",
        ttl_seconds=_TTL_SECONDS,
    )
    return TrustedEnvelopeBuilder(harness.authority, clock=lambda: harness.now).build(request)


__all__ = [
    "CaseResult",
    "HARNESS_NOW",
    "MemoryG2Repository",
    "run_scenario",
]
