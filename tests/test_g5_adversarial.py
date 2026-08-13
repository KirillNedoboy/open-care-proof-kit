"""Focused adversarial-corpus tests (G5, Phase 6).

These assert the *observable security contract* of the corpus + driver: every
case enforces, foreign-Person evidence never reaches a provider, blocked
mutations leave canonical state unchanged, and the corpus is synthetic-only.
"""

from __future__ import annotations

from pathlib import Path

from evals.g5.corpus import CATEGORIES, load_corpus
from evals.g5.harness import HARNESS_NOW, run_scenario

_SYNTHETIC_PREFIXES = ("actor-", "person-", "credential-", "evidence-", "consent-", "source-")


def _run_all(tmp_path: Path):
    scenarios = load_corpus()
    results = [
        run_scenario(scenario, HARNESS_NOW, tmp_path / scenario.case_id)
        for scenario in scenarios
    ]
    return scenarios, results


def test_corpus_loads_twenty_unique_cases() -> None:
    scenarios = load_corpus()
    assert len(scenarios) == 20
    case_ids = [scenario.case_id for scenario in scenarios]
    assert len(case_ids) == len(set(case_ids))
    for scenario in scenarios:
        assert scenario.category in CATEGORIES


def test_corpus_uses_only_synthetic_identities() -> None:
    for scenario in load_corpus():
        for value in (
            scenario.actor_id,
            scenario.person_id,
            scenario.credential_id,
            *scenario.evidence_ids,
        ):
            assert value.startswith(_SYNTHETIC_PREFIXES), value
        for phase in scenario.phases:
            if phase.actor_id:
                assert phase.actor_id.startswith("actor-")
            if phase.evidence_id:
                assert phase.evidence_id.startswith("evidence-")


def test_every_case_enforces_its_expected_outcome(tmp_path: Path) -> None:
    scenarios, results = _run_all(tmp_path)
    failed = [result for result in results if not result.passed]
    assert failed == [], [(result.case_id, result.failures) for result in failed]
    assert len(results) == 20


def test_foreign_person_evidence_never_reaches_provider(tmp_path: Path) -> None:
    _, results = _run_all(tmp_path)
    for result in results:
        for call_evidence in result.provider_evidence_ids:
            leaked = set(call_evidence) & set(result.forbidden_evidence_ids)
            assert leaked == set(), f"{result.case_id}: {leaked}"


def test_mutation_attempts_leave_canonical_state_unchanged(tmp_path: Path) -> None:
    scenarios, results = _run_all(tmp_path)
    for scenario, result in zip(scenarios, results, strict=True):
        if scenario.kind != "g2_flow":
            continue
        if result.mutation_attempted:
            assert result.canonical_state_unchanged, result.case_id
            assert result.outcome == "refused"
            assert result.reason_codes == ["tool_not_allowed"]


def test_provider_call_count_is_zero_after_revocation_or_context_change(
    tmp_path: Path,
) -> None:
    scenarios, results = _run_all(tmp_path)
    by_id = {scenario.case_id: scenario for scenario in scenarios}
    for result in results:
        scenario = by_id[result.case_id]
        change_ops = {
            "revoke_actor", "revoke_consent", "mutate_evidence", "swap_provider", "swap_model"
        }
        changed = any(phase.op in change_ops for phase in scenario.phases)
        if changed:
            assert result.provider_calls == 0, result.case_id


def test_replay_is_deterministic_and_rejected(tmp_path: Path) -> None:
    scenarios, results = _run_all(tmp_path)
    replay = [r for r in results if r.kind == "replay"]
    assert len(replay) == 1
    assert replay[0].passed
    assert replay[0].outcome == "answered"
