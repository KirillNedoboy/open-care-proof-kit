from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import app.main as main_module
from app.family_access.policy import CAREGIVER_OPTIONAL_SCOPES_V3, CAREGIVER_OPTIONAL_SCOPES_V4
from app.product_core.document_fact_extraction import (
    DocumentFactAnswer,
    DocumentFactAnswerV2,
)
from tests.test_product_core_d2_document_facts import _select_person

# One page exercising all six D2.2 categories with exact verbatim quotes.
DOC_TEXT = (
    "Current medication: Aspirin 81 mg daily. Diagnosis: Asthma. "
    "Lab: Hemoglobin A1c result 6.1%. "
    "Procedure: Colonoscopy completed in March. "
    "Recommendation: Reduce sodium intake during meals. "
    "Follow-up: repeat blood panel in 3 months."
)

SIX_ANSWER: dict[str, Any] = {
    "medications": [
        {
            "page_number": 1,
            "evidence_quote": "Current medication: Aspirin 81 mg daily.",
            "display_name": "Aspirin",
            "schedule_text": "81 mg daily",
        }
    ],
    "conditions": [
        {
            "page_number": 1,
            "evidence_quote": "Diagnosis: Asthma.",
            "display_name": "Asthma",
        }
    ],
    "labs": [
        {
            "page_number": 1,
            "evidence_quote": "Lab: Hemoglobin A1c result 6.1%.",
            "test_name": "Hemoglobin A1c",
            "result_text": "6.1%",
        }
    ],
    "procedures": [
        {
            "page_number": 1,
            "evidence_quote": "Procedure: Colonoscopy completed in March.",
            "display_name": "Colonoscopy",
            "status_text": "completed",
            "date_text": "in March",
        }
    ],
    "recommendations": [
        {
            "page_number": 1,
            "evidence_quote": "Recommendation: Reduce sodium intake during meals.",
            "instruction_text": "Reduce sodium intake",
        }
    ],
    "follow_ups": [
        {
            "page_number": 1,
            "evidence_quote": "Follow-up: repeat blood panel in 3 months.",
            "action_text": "repeat blood panel",
            "timing_text": "in 3 months",
        }
    ],
}


class _V2Provider:
    """Fake local provider replaying a canned v2 six-array answer (D2.1 idiom)."""

    def __init__(self, answer: dict[str, Any]) -> None:
        self.external = False
        self.calls = 0
        self.requests: list[Any] = []
        self.answer = answer

    @property
    def descriptor(self) -> Any:
        from app.agent.providers.contract import ProviderDescriptor

        return ProviderDescriptor(
            "tests.d2-2-extraction",
            "self_hosted_http",
            "local_only",
            "loopback",
            False,
            "test",
        )

    def execute(self, request: Any) -> Any:
        from app.agent.providers.contract import ProviderExecutionResult

        self.calls += 1
        self.requests.append(request)
        return ProviderExecutionResult(
            self.answer,
            self.descriptor.provider_id,
            self.descriptor.model_id,
            (),
            None,
        )


def _upload(client: TestClient, text: str = DOC_TEXT) -> str:
    uploaded = client.post(
        "/api/product-core/v1/people/person-1/documents",
        content=text.encode("utf-8"),
        headers={"content-type": "text/plain", "x-opencare-filename": "plan.txt"},
    )
    assert uploaded.status_code == 201, uploaded.text
    return uploaded.json()["document"]["source_id"]


def _prepare(client: TestClient, source_id: str) -> dict[str, Any]:
    prepared = client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}/fact-extractions/prepare",
        json={},
    )
    assert prepared.status_code == 200, prepared.text
    return prepared.json()


def _execute(client: TestClient, source_id: str, run_id: str) -> dict[str, Any]:
    executed = client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}"
        f"/fact-extractions/{run_id}/execute",
        json={},
    )
    assert executed.status_code == 200, executed.text
    return executed.json()


def _pending_candidates(person_id: str = "person-1") -> list[tuple[str, str]]:
    runtime = main_module.app.state.product_core_runtime
    with runtime.database.connect() as connection:
        return [
            (str(row["fact_type"]), str(row["status"]))
            for row in connection.execute(
                "SELECT fact_type, status FROM candidate_facts "
                "WHERE person_id = ? ORDER BY fact_type, id",
                (person_id,),
            ).fetchall()
        ]


def test_d22_six_categories_in_one_answer_materialize_six_pending_candidates(
    product_core_client: TestClient,
) -> None:
    provider = _V2Provider(SIX_ANSWER)
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    source_id = _upload(product_core_client)
    payload = _prepare(product_core_client, source_id)
    assert payload["allowed_fact_types"] == [
        "condition",
        "follow_up",
        "lab",
        "medication",
        "procedure",
        "recommendation",
    ]

    result = _execute(product_core_client, source_id, payload["run_id"])

    assert result["contract_version"] == "opencare-document-facts/2"
    assert result["status"] == "completed"
    assert result["total_facts"] == 6
    assert result["valid_facts"] == 6
    assert result["invalid_facts"] == 0
    assert result["new_candidates"] == 6
    assert result["reused_candidates"] == 0
    assert sorted(_pending_candidates()) == [
        ("condition", "pending"),
        ("follow_up", "pending"),
        ("lab", "pending"),
        ("medication", "pending"),
        ("procedure", "pending"),
        ("recommendation", "pending"),
    ]


def test_d22_fact_cap_is_global_across_six_arrays(
    product_core_client: TestClient,
) -> None:
    # 30 medications + 3 procedures = 33 suggestions: the 32-fact cap is
    # enforced on the flattened total across all six arrays, not per array,
    # and it fails the run BEFORE any candidate materialization.
    answer: dict[str, Any] = {
        "medications": [
            {
                "page_number": 1,
                "evidence_quote": "Current medication: Aspirin 81 mg daily.",
                "display_name": "Aspirin",
                "note": f"entry {index}",
            }
            for index in range(30)
        ],
        "conditions": [],
        "labs": [],
        "procedures": [
            {
                "page_number": 1,
                "evidence_quote": "Procedure: Colonoscopy completed in March.",
                "display_name": "Colonoscopy",
            }
            for _ in range(3)
        ],
        "recommendations": [],
        "follow_ups": [],
    }
    provider = _V2Provider(answer)
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    source_id = _upload(product_core_client)
    payload = _prepare(product_core_client, source_id)

    result = _execute(product_core_client, source_id, payload["run_id"])

    assert result["status"] == "failed"
    assert result["reason_code"] == "fact_count_limit_exceeded"
    assert provider.calls == 1
    assert _pending_candidates() == []


def test_d22_wrong_and_ambiguous_quotes_rejected_for_new_types(
    product_core_client: TestClient,
) -> None:
    # Two-page document: the recommendation quote occurs twice (ambiguous);
    # the procedure quote is not verbatim present (wrong quote). The valid
    # follow-up still materializes, so the run ends "partial".
    text = (
        "Procedure: Colonoscopy completed in March. "
        "Reduce sodium intake during meals. "
        "Reduce sodium intake during meals. "
        "Follow-up: repeat blood panel in 3 months."
    )
    answer: dict[str, Any] = {
        "medications": [],
        "conditions": [],
        "labs": [],
        "procedures": [
            {
                "page_number": 1,
                # "last March" is not verbatim in the document text.
                "evidence_quote": "Procedure: Colonoscopy completed last March.",
                "display_name": "Colonoscopy",
                "status_text": "completed",
            }
        ],
        "recommendations": [
            {
                "page_number": 1,
                # Occurs twice on the page: no unique span resolution.
                "evidence_quote": "Reduce sodium intake during meals.",
                "instruction_text": "Reduce sodium intake",
            }
        ],
        "follow_ups": [
            {
                "page_number": 1,
                "evidence_quote": "Follow-up: repeat blood panel in 3 months.",
                "action_text": "repeat blood panel",
                "timing_text": "in 3 months",
            }
        ],
    }
    provider = _V2Provider(answer)
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    source_id = _upload(product_core_client, text)
    payload = _prepare(product_core_client, source_id)

    result = _execute(product_core_client, source_id, payload["run_id"])

    assert result["status"] == "partial"
    assert result["valid_facts"] == 1
    assert result["invalid_facts"] == 2
    assert result["new_candidates"] == 1
    assert result["reused_candidates"] == 0
    by_type = {item["fact_type"]: item for item in result["items"]}
    assert by_type["procedure"]["validation_status"] == "invalid"
    assert by_type["procedure"]["invalid_reason"] == "quote_not_unique"
    assert by_type["procedure"]["candidate_id"] is None
    assert by_type["recommendation"]["validation_status"] == "invalid"
    assert by_type["recommendation"]["invalid_reason"] == "quote_not_unique"
    assert by_type["recommendation"]["candidate_id"] is None
    assert by_type["follow_up"]["validation_status"] == "valid"
    assert by_type["follow_up"]["candidate_id"] is not None
    # Zero invalid candidates were created — only the one grounded follow-up.
    assert _pending_candidates() == [("follow_up", "pending")]


def test_d22_cross_person_document_cannot_execute_under_other_person(
    product_core_client: TestClient,
) -> None:
    # Mirrors the D2.1 wrong-active-person pattern: a run bound to Person A's
    # document cannot be executed while Person B is active — no provider call,
    # nothing materializes under the wrong Person.
    provider = _V2Provider(SIX_ANSWER)
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    source_id = _upload(product_core_client)
    payload = _prepare(product_core_client, source_id)
    _select_person(product_core_client, "person-2")

    response = product_core_client.post(
        f"/api/product-core/v1/people/person-1/documents/{source_id}"
        f"/fact-extractions/{payload['run_id']}/execute",
        json={},
    )

    assert response.status_code == 403
    assert provider.calls == 0
    assert _pending_candidates("person-2") == []


def test_d22_strict_v2_schema_and_v1_legacy_parse() -> None:
    assert len(SIX_ANSWER) == 6
    parsed = DocumentFactAnswerV2.model_validate(SIX_ANSWER)
    assert len(parsed.procedures) == 1
    # extra="forbid": an unknown seventh category is rejected.
    with pytest.raises(ValidationError):
        DocumentFactAnswerV2.model_validate({**SIX_ANSWER, "devices": []})
    # Missing arrays are rejected — v2 requires exactly six.
    with pytest.raises(ValidationError):
        DocumentFactAnswerV2.model_validate(
            {key: value for key, value in SIX_ANSWER.items() if key != "procedures"}
        )
    # The historical three-array v1 payload still parses via the v1 model.
    legacy = DocumentFactAnswer.model_validate(
        {
            key: SIX_ANSWER[key]
            for key in ("medications", "conditions", "labs")
        }
    )
    assert len(legacy.medications) == 1


def test_d22_v1_three_type_run_then_v2_six_type_reanalysis_reuses_existing(
    product_core_client: TestClient,
) -> None:
    provider = _V2Provider(SIX_ANSWER)
    main_module.app.state.agent_provider = provider
    family_runtime = main_module.app.state.family_access_runtime
    owner_id = product_core_client.get("/api/family-access/v1/me").json()["actor"][
        "actor_id"
    ]
    caregiver_id, assignment_id = _login_caregiver_v3(product_core_client, family_runtime, owner_id)
    assert caregiver_id is not None
    source_id = _upload(product_core_client)

    first = _prepare(product_core_client, source_id)
    # v3 caregiver: only the three D2.1 categories are writable.
    assert first["allowed_fact_types"] == ["condition", "lab", "medication"]
    # A v1-shaped three-array answer (the D2.1 contract) stays parseable
    # and materializes exactly the three D2.1 categories under a v3
    # caregiver's restricted authorization.
    provider.answer = {key: SIX_ANSWER[key] for key in ("medications", "conditions", "labs")}
    first_result = _execute(product_core_client, source_id, first["run_id"])
    assert first_result["new_candidates"] == 3
    assert first_result["status"] == "completed"
    assert first_result["reused_candidates"] == 0

    provider.answer = SIX_ANSWER
    family_runtime.service.revise_assignment(
        owner_id,
        "person-1",
        assignment_id,
        set(CAREGIVER_OPTIONAL_SCOPES_V4),
        policy_generation="family-access-v4",
    )
    second = _prepare(product_core_client, source_id)
    assert second["allowed_fact_types"] == [
        "condition",
        "follow_up",
        "lab",
        "medication",
        "procedure",
        "recommendation",
    ]
    second_result = _execute(product_core_client, source_id, second["run_id"])
    # Same med/condition/lab quotes+identity -> fingerprint reuse; the three
    # new categories materialize fresh.
    assert second_result["new_candidates"] == 3
    assert second_result["reused_candidates"] == 3
    assert second_result["status"] == "completed"
    assert len(_pending_candidates()) == 6

    # Identical third pass: same scopes/provider/document -> the prepared run
    # is the completed v2 run itself (request fingerprint reuse); executing a
    # completed run returns its stored audit without a provider call, without
    # re-materializing, and with no extra candidates.
    third = _prepare(product_core_client, source_id)
    assert third["run_id"] == second["run_id"]
    calls_before = provider.calls
    third_result = _execute(product_core_client, source_id, third["run_id"])
    assert third_result["status"] == "completed"
    assert third_result["new_candidates"] == 3  # stored value from run 2, not re-counted
    assert provider.calls == calls_before
    assert len(_pending_candidates()) == 6


def _login_caregiver_v3(
    client: TestClient, family_runtime: Any, owner_id: str
) -> tuple[str, str]:
    caregiver = family_runtime.service.create_local_actor(
        owner_id,
        username="d22-caregiver",
        display_name="D2.2 scope test caregiver",
        password="caregiver password value",
    )
    assignment = family_runtime.service.grant_assignment(
        owner_id,
        "person-1",
        caregiver.actor_id,
        role="caregiver",
        optional_scopes=set(CAREGIVER_OPTIONAL_SCOPES_V3),
        confirm_full_owner_access=False,
    )
    login = client.post(
        "/api/family-access/v1/login",
        json={"username": "d22-caregiver", "password": "caregiver password value"},
    )
    assert login.status_code == 200, login.text
    csrf = client.cookies.get("opencare_csrf")
    assert csrf is not None
    client.headers.update({"origin": "http://testserver", "x-opencare-csrf": csrf})
    _select_person(client)
    return caregiver.actor_id, assignment.assignment_id


def test_d22_v2_provider_system_prompt_pins_prohibitions() -> None:
    import inspect

    from app.agent.document_fact_trust import DocumentFactTrustAdapter

    source = inspect.getsource(DocumentFactTrustAdapter.provider_request_builder)
    lowered = " ".join(source.split()).casefold()
    # Spec §16-17: duplication/category confusion is contract-level (prompt),
    # these prohibitions must stay pinned in the real request builder.
    for phrase in (
        "never diagnose",
        "never recommend treatment",
        "never infer procedures",
        "derive dates",
        "convert units",
        "interpret labs",
        "verbatim evidence quote",
    ):
        assert phrase in lowered, phrase
    assert "procedure" in lowered and "follow_up" in lowered


def test_d22_same_span_medication_and_recommendation_get_independent_fingerprints(
    product_core_client: TestClient,
) -> None:
    # The server enforces per-(person, source, extraction, fact_type, locator,
    # identity) fingerprints. A medication and a recommendation citing the
    # IDENTICAL span still materialize as two candidates (fact_type differs);
    # §16-17 "classify once" duplication control lives in the v2 prompt
    # contract, not in server-side cross-type dedup.
    answer: dict[str, Any] = {
        "medications": [
            {
                "page_number": 1,
                "evidence_quote": "Current medication: Aspirin 81 mg daily.",
                "display_name": "Aspirin",
                "schedule_text": "81 mg daily",
            }
        ],
        "conditions": [],
        "labs": [],
        "procedures": [],
        "recommendations": [
            {
                "page_number": 1,
                "evidence_quote": "Current medication: Aspirin 81 mg daily.",
                "instruction_text": "Aspirin 81 mg daily",
            }
        ],
        "follow_ups": [],
    }
    provider = _V2Provider(answer)
    main_module.app.state.agent_provider = provider
    _select_person(product_core_client)
    source_id = _upload(product_core_client, "Current medication: Aspirin 81 mg daily.")
    payload = _prepare(product_core_client, source_id)

    result = _execute(product_core_client, source_id, payload["run_id"])

    assert result["status"] == "completed"
    assert result["new_candidates"] == 2
    assert result["invalid_facts"] == 0
    by_type = {item["fact_type"]: item for item in result["items"]}
    med, rec = by_type["medication"], by_type["recommendation"]
    assert med["candidate_id"] != rec["candidate_id"]
    assert med["candidate_fingerprint"] != rec["candidate_fingerprint"]
    # Same span coordinates on both items; the fact_type in the fingerprint
    # keeps them distinct candidates.
    for field in ("page_number", "start_codepoint", "end_codepoint", "quote"):
        assert med[field] == rec[field]
        assert med[field] is not None
    assert sorted(_pending_candidates()) == [
        ("medication", "pending"),
        ("recommendation", "pending"),
    ]
