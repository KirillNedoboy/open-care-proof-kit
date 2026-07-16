import asyncio
from pathlib import Path

import httpx
import pytest

import app.main as main_module
from app.config import Settings


def request(
    method: str,
    path: str,
    *,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=main_module.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=follow_redirects,
        ) as client:
            return await client.request(method, path, content=content, headers=headers)

    return asyncio.run(send())


def json_headers(*, origin: str = "http://testserver") -> dict[str, str]:
    return {"content-type": "application/json", "origin": origin}


def private_settings() -> Settings:
    return Settings(
        env="production",
        demo_mode=False,
        data_dir=Path("data"),
        reports_dir=Path("reports"),
        allow_cloud_llm=False,
        secret_key="s" * 32,
        access_password="vault-password",
    )


def test_root_opens_chat_workspace() -> None:
    response = request("GET", "/")

    assert response.status_code == 200
    assert "OpenCare chat" in response.text


def test_public_demo_chat_route_is_passwordless() -> None:
    response = request("GET", "/chat", follow_redirects=False)

    assert response.status_code == 200


def test_chat_api_returns_validated_demo_answer() -> None:
    response = request(
        "POST",
        "/api/chat",
        content=b'{"question":"Prepare questions for my doctor"}',
        headers=json_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["citations"]
    assert "source_id" in payload["citations"][0]


def test_chat_api_returns_cited_recorded_medication_and_missing_dosage_answers() -> None:
    medication = request(
        "POST",
        "/api/chat",
        content=b'{"question":"Which medications are recorded in this vault?"}',
        headers=json_headers(),
    )
    dosage = request(
        "POST",
        "/api/chat",
        content=b'{"question":"What dosage is recorded in the source?"}',
        headers=json_headers(),
    )

    assert medication.status_code == 200
    assert medication.json()["status"] == "answered"
    assert {citation["source_id"] for citation in medication.json()["citations"]} == {
        "source-medication-list-2026-03"
    }
    assert dosage.status_code == 200
    assert dosage.json()["status"] == "answered"
    assert {citation["source_id"] for citation in dosage.json()["citations"]} == {
        "source-medication-list-2026-03"
    }
    assert dosage.json()["unknowns"]
    assert "no recorded source-backed dosage" in dosage.json()["answer"].lower()


def test_chat_api_refuses_diagnosis_and_dosage_change_requests() -> None:
    diagnosis = request(
        "POST",
        "/api/chat",
        content=b'{"question":"What diagnosis do I have?"}',
        headers=json_headers(),
    )
    dosage_change = request(
        "POST",
        "/api/chat",
        content=b'{"question":"Should I increase my dosage?"}',
        headers=json_headers(),
    )

    assert diagnosis.status_code == 200
    assert diagnosis.json()["status"] == "refused"
    assert dosage_change.status_code == 200
    assert dosage_change.json()["status"] == "refused"


def test_chat_api_rejects_cross_origin_request() -> None:
    response = request(
        "POST",
        "/api/chat",
        content=b'{"question":"Prepare questions for my doctor"}',
        headers=json_headers(origin="https://attacker.example"),
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Cross-origin request rejected."}


def test_chat_api_rejects_malformed_origin() -> None:
    response = request(
        "POST",
        "/api/chat",
        content=b'{"question":"Prepare questions for my doctor"}',
        headers=json_headers(origin="https://testserver:bad"),
    )

    assert response.status_code == 403


def test_chat_api_rejects_non_json_and_empty_input() -> None:
    non_json = request("POST", "/api/chat", content=b"question=value")
    empty = request(
        "POST",
        "/api/chat",
        content=b'{"question":"  "}',
        headers=json_headers(),
    )

    assert non_json.status_code == 415
    assert empty.status_code == 422


def test_chat_api_rejects_get_and_oversized_question() -> None:
    get_response = request("GET", "/api/chat", follow_redirects=False)
    oversized = request(
        "POST",
        "/api/chat",
        content=('{"question":"' + "x" * 2001 + '"}').encode(),
        headers=json_headers(),
    )

    assert get_response.status_code == 405
    assert oversized.status_code == 413


def test_chat_browser_script_does_not_persist_conversation_state() -> None:
    script = (Path("app") / "static" / "chat.js").read_text(encoding="utf-8")

    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "innerHTML" not in script


def test_private_chat_page_redirects_but_api_returns_json_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_module, "get_settings", private_settings)

    page = request("GET", "/chat", follow_redirects=False)
    api = request(
        "POST",
        "/api/chat",
        content=b'{"question":"Prepare questions for my doctor"}',
        headers=json_headers(),
        follow_redirects=False,
    )

    assert page.status_code == 307
    assert page.headers["location"] == "/access?next=%2Fchat"
    assert api.status_code == 401
    assert api.headers["content-type"].startswith("application/json")
    assert api.json() == {"detail": "Private access required."}


def test_private_authenticated_same_origin_chat_api_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = private_settings()
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    access_cookie = main_module._build_access_cookie(settings.secret_key or "")
    cookie = f"{main_module.ACCESS_COOKIE_NAME}={access_cookie}"

    response = request(
        "POST",
        "/api/chat",
        content=b'{"question":"Which information is source-backed?"}',
        headers={**json_headers(), "cookie": cookie},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "answered"
