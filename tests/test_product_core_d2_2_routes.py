from __future__ import annotations

import json

import app.main as main_module
from app.family_access.policy import CAREGIVER_BASE_SCOPES_V3
from app.product_core.models import (
    FollowUpCandidateInput,
    ProcedureCandidateInput,
    RecommendationCandidateInput,
)
from tests.product_core_api_support import json_headers
from tests.test_product_core_access_enforcement import (
    AccessHarness,
)
from tests.test_product_core_access_enforcement import (
    access_harness as _access_harness,
)

access_harness = _access_harness


def _set_alice_scopes(harness: AccessHarness, scopes: frozenset[str]) -> None:
    database = main_module.app.state.product_core_runtime.database
    with database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        uow.connection.execute(
            """
            UPDATE person_access_assignments
            SET scopes_json = ?
            WHERE actor_id = ? AND person_id = ? AND is_active = 1
            """,
            (
                json.dumps(sorted(scopes), separators=(",", ":")),
                harness.actor_ids["bob"],
                "alice-person",
            ),
        )


def _new_family_candidate(harness: AccessHarness, fact_type: str) -> str:
    harness.login("alice")
    source = harness.client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={
            "person_id": "alice-person",
            "medication": {"display_name": "Recorded evidence"},
        },
        headers=json_headers(),
    )
    assert source.status_code in {200, 201}, source.text
    inputs = {
        "procedure": ProcedureCandidateInput(display_name="MRI"),
        "recommendation": RecommendationCandidateInput(
            instruction_text="Bring a blood pressure log"
        ),
        "follow_up": FollowUpCandidateInput(action_text="See cardiology"),
    }
    candidate = main_module.app.state.product_core_runtime.lifecycle.create_fact_candidate(
        person_id="alice-person",
        source_id=source.json()["source"]["source_id"],
        fact_type=fact_type,
        detail_input=inputs[fact_type],
    )
    return candidate.id


def test_v4_owner_lists_all_new_family_routes(access_harness: AccessHarness) -> None:
    access_harness.login("alice")
    paths = (
        "procedure-candidates",
        "procedures",
        "recommendation-candidates",
        "recommendations",
        "follow-up-candidates",
        "follow-ups",
    )

    responses = [
        access_harness.client.get(f"/api/product-core/v1/people/alice-person/{path}")
        for path in paths
    ]

    assert [response.status_code for response in responses] == [200] * len(paths)


def test_owner_correction_routes_create_typed_replacements(
    access_harness: AccessHarness,
) -> None:
    cases = (
        ("procedure", "correct:procedure", {"display_name": "MRI knee"}, "display_name"),
        (
            "recommendation",
            "correct:recommendation",
            {"instruction_text": "Track blood pressure"},
            "instruction_text",
        ),
        (
            "follow_up",
            "correct:follow-up",
            {"action_text": "Call cardiology"},
            "action_text",
        ),
    )
    for fact_type, action, payload, detail_field in cases:
        candidate_id = _new_family_candidate(access_harness, fact_type)
        corrected = access_harness.client.post(
            f"/api/product-core/v1/candidates/{candidate_id}/{action}",
            json=payload,
            headers=json_headers(),
        )

        assert corrected.status_code == 201, corrected.text
        assert corrected.json()["predecessor_candidate_id"] == candidate_id
        assert corrected.json()[detail_field] == next(iter(payload.values()))


def test_caregiver_without_procedure_read_is_forbidden_for_visible_person(
    access_harness: AccessHarness,
) -> None:
    from app.family_access.policy import CAREGIVER_BASE_SCOPES_V1

    _set_alice_scopes(access_harness, CAREGIVER_BASE_SCOPES_V1)
    access_harness.login("bob")

    visible = access_harness.client.get(
        "/api/product-core/v1/people/alice-person/procedure-candidates"
    )
    hidden = access_harness.client.get(
        "/api/product-core/v1/people/carol-person/procedure-candidates"
    )

    assert visible.status_code == 403
    assert hidden.status_code == 404


def test_v3_caregiver_retains_old_family_reads_but_not_v4_reads(
    access_harness: AccessHarness,
) -> None:
    _set_alice_scopes(access_harness, CAREGIVER_BASE_SCOPES_V3)
    access_harness.login("bob")

    old_family = access_harness.client.get(
        "/api/product-core/v1/people/alice-person/condition-candidates"
    )
    new_families = [
        access_harness.client.get(f"/api/product-core/v1/people/alice-person/{path}")
        for path in (
            "procedure-candidates",
            "recommendation-candidates",
            "follow-up-candidates",
        )
    ]

    assert old_family.status_code == 200
    assert [response.status_code for response in new_families] == [403, 403, 403]


def test_v3_caregiver_cannot_correct_recommendation(access_harness: AccessHarness) -> None:
    candidate_id = _new_family_candidate(access_harness, "recommendation")
    _set_alice_scopes(access_harness, CAREGIVER_BASE_SCOPES_V3)
    access_harness.login("bob")

    denied = access_harness.client.post(
        f"/api/product-core/v1/candidates/{candidate_id}/correct:recommendation",
        json={"instruction_text": "Denied correction"},
        headers=json_headers(),
    )

    assert denied.status_code == 403


def test_foreign_candidate_correction_is_not_found(access_harness: AccessHarness) -> None:
    access_harness.login("alice")
    source = access_harness.client.post(
        "/api/product-core/v1/sources/manual-medication",
        json={
            "person_id": "carol-person",
            "medication": {"display_name": "Private evidence"},
        },
        headers=json_headers(),
    )
    assert source.status_code == 201, source.text
    candidate = main_module.app.state.product_core_runtime.lifecycle.create_fact_candidate(
        person_id="carol-person",
        source_id=source.json()["source"]["source_id"],
        fact_type="recommendation",
        detail_input=RecommendationCandidateInput(instruction_text="Private instruction"),
    )
    access_harness.login("bob")

    response = access_harness.client.post(
        f"/api/product-core/v1/candidates/{candidate.id}/correct:recommendation",
        json={"instruction_text": "Guessed correction"},
        headers=json_headers(),
    )

    assert response.status_code == 404
