from fastapi.testclient import TestClient

from tests.product_core_api_support import json_headers


def test_visit_and_question_api_lifecycle(product_core_client: TestClient) -> None:
    created = product_core_client.post(
        "/api/product-core/v1/visits",
        json={
            "person_id": "person-1",
            "title": "  Neurology review  ",
            "specialist": "Neurologist",
            "scheduled_date": "2020-01-02",
        },
        headers=json_headers(),
    )

    assert created.status_code == 201
    visit = created.json()
    assert set(visit) == {
        "visit_id", "person_id", "title", "specialist", "scheduled_date", "created_at", "updated_at"
    }
    assert visit["title"] == "Neurology review"
    assert visit["scheduled_date"] == "2020-01-02"

    listed = product_core_client.get("/api/product-core/v1/people/person-1/visits")
    assert listed.status_code == 200
    assert listed.json()["visits"] == [visit]

    updated = product_core_client.patch(
        f"/api/product-core/v1/visits/{visit['visit_id']}",
        json={"specialist": None, "scheduled_date": None},
        headers=json_headers(),
    )
    assert updated.status_code == 200
    assert updated.json()["specialist"] is None
    assert updated.json()["scheduled_date"] is None

    first = product_core_client.post(
        f"/api/product-core/v1/visits/{visit['visit_id']}/questions",
        json={"question_text": "What should I monitor?"},
        headers=json_headers(),
    )
    second = product_core_client.post(
        f"/api/product-core/v1/visits/{visit['visit_id']}/questions",
        json={"question_text": "Which records matter?"},
        headers=json_headers(),
    )
    assert first.status_code == 201
    assert second.status_code == 201

    moved = product_core_client.patch(
        f"/api/product-core/v1/visit-questions/{second.json()['question_id']}",
        json={"position": 0},
        headers=json_headers(),
    )
    assert moved.status_code == 200
    questions = product_core_client.get(
        f"/api/product-core/v1/visits/{visit['visit_id']}/questions"
    )
    question_positions = [
        (item["question_text"], item["position"])
        for item in questions.json()["questions"]
    ]
    assert question_positions == [
        ("Which records matter?", 0),
        ("What should I monitor?", 1),
    ]

    deleted = product_core_client.delete(
        f"/api/product-core/v1/visit-questions/{first.json()['question_id']}",
        headers=json_headers(),
    )
    assert deleted.status_code == 204
    assert product_core_client.get(
        f"/api/product-core/v1/visits/{visit['visit_id']}/questions"
    ).json()["questions"][0]["position"] == 0


def test_visit_api_rejects_invalid_patch_and_unknown_records(
    product_core_client: TestClient,
) -> None:
    empty_patch = product_core_client.patch(
        "/api/product-core/v1/visits/missing", json={}, headers=json_headers()
    )
    invalid_title = product_core_client.post(
        "/api/product-core/v1/visits",
        json={"person_id": "person-1", "title": "  "},
        headers=json_headers(),
    )
    unknown_person = product_core_client.get("/api/product-core/v1/people/missing/visits")
    unknown_visit = product_core_client.get("/api/product-core/v1/visits/missing/questions")

    assert empty_patch.status_code == 404
    assert empty_patch.content == unknown_visit.content
    assert invalid_title.status_code == 422
    assert unknown_person.status_code == 404
    assert unknown_person.json()["error"]["code"] == "person_not_found"
    assert unknown_visit.status_code == 404
    assert unknown_visit.json()["error"]["code"] == "visit_not_found"


def test_visit_patch_distinguishes_omitted_fields_from_explicit_null(
    product_core_client: TestClient,
) -> None:
    visit = product_core_client.post(
        "/api/product-core/v1/visits",
        json={
            "person_id": "person-1",
            "title": "Visit",
            "specialist": "Cardiology",
            "scheduled_date": "2020-01-02",
        },
        headers=json_headers(),
    ).json()

    title_null = product_core_client.patch(
        f"/api/product-core/v1/visits/{visit['visit_id']}",
        json={"title": None},
        headers=json_headers(),
    )
    unchanged = product_core_client.patch(
        f"/api/product-core/v1/visits/{visit['visit_id']}",
        json={"title": "Renamed"},
        headers=json_headers(),
    )
    question = product_core_client.post(
        f"/api/product-core/v1/visits/{visit['visit_id']}/questions",
        json={"question_text": "Question"},
        headers=json_headers(),
    ).json()
    question_null = product_core_client.patch(
        f"/api/product-core/v1/visit-questions/{question['question_id']}",
        json={"question_text": None},
        headers=json_headers(),
    )

    assert title_null.status_code == 422
    assert unchanged.status_code == 200
    assert unchanged.json()["specialist"] == "Cardiology"
    assert unchanged.json()["scheduled_date"] == "2020-01-02"
    assert question_null.status_code == 422
