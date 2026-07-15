import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.config import Settings
from app.main import app


def request(
    method: str,
    path: str,
    *,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=follow_redirects,
        ) as client:
            return await client.request(method, path, data=data, headers=headers)

    return asyncio.run(send())


def get(
    path: str,
    *,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    return request(
        "GET",
        path,
        headers=headers,
        follow_redirects=follow_redirects,
    )


def post(
    path: str,
    *,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    follow_redirects: bool = True,
) -> httpx.Response:
    return request(
        "POST",
        path,
        data=data,
        headers=headers,
        follow_redirects=follow_redirects,
    )


def test_demo_report_markdown_endpoint_returns_markdown() -> None:
    response = get("/demo/report.md?drug=sertraline")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Medication-to-Doctor Briefing" in response.text
    assert "not medical advice" in response.text.lower()


def test_demo_audit_endpoint_returns_audit_only() -> None:
    response = get("/demo/audit?drug=sertraline")

    assert response.status_code == 200
    payload = response.json()
    assert payload["drug"] == "sertraline"
    assert payload["policy_passed"] is True
    assert payload["raw_health_or_genetic_data_exported"] is False
    assert payload["coverage"]["coverage_status"] == "matched_demo_rule"
    assert "report_markdown" not in payload


def test_index_page_opens_chat_workspace() -> None:
    response = get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "OpenCare chat" in response.text
    assert "Ask about your recorded vault" in response.text


def test_demo_page_renders_synthetic_demo_patient() -> None:
    response = get("/demo")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Synthetic Demo Patient" in response.text


def test_health_vault_reviewer_page_renders_synthetic_read_only_context() -> None:
    response = get("/demo/health-vault")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "synthetic/demo-only" in response.text
    assert "not diagnosis" in response.text
    assert "not treatment recommendation" in response.text
    assert "not dosage guidance" in response.text
    assert "not medication selection" in response.text
    assert "no start/stop medication advice" in response.text
    assert "no genetics in this layer" in response.text
    assert "Provenance Coverage" in response.text
    assert "Context / Provenance Trace Graph" in response.text
    assert "not medical interpretation" in response.text
    assert "Source-linked records" in response.text
    assert "Artifact / Trust Flags" in response.text
    assert "Demo Adult Alex" in response.text
    assert "Demo Adult Jordan" in response.text
    assert "Demo Teen Sam" in response.text
    assert "clinical decision support" not in response.text.lower()


def local_file_payload() -> dict[str, object]:
    return {
        "dataset_id": "local-family-vault-v1",
        "version": "0.1.0",
        "demo_only": False,
        "synthetic": False,
        "family": {
            "id": "family-local-01",
            "display_name": "Local Family Vault",
            "synthetic": False,
        },
        "people": [
            {
                "id": "person-owner",
                "display_name": "Local Adult One",
                "role": "self",
                "synthetic": False,
                "notes": "Locally mounted read-only vault record.",
            }
        ],
        "relationships": [],
        "document_sources": [
            {
                "id": "source-local-note",
                "title": "Local mounted note",
                "source_type": "visit_note",
                "synthetic": False,
                "demo_only": False,
                "description": "Local operator-mounted vault source.",
            }
        ],
        "conditions": [
            {
                "id": "condition-local",
                "person_id": "person-owner",
                "name": "Recorded local concern",
                "status": "active",
                "description": "Recorded context only; clinician review required.",
                "evidence": [
                    {
                        "source_id": "source-local-note",
                        "strength": "source_backed",
                        "note": "Recorded in the mounted local note.",
                    }
                ],
            }
        ],
        "medications": [],
        "lab_results": [],
        "visits": [],
        "timeline_events": [],
        "question_threads": [],
    }


def test_vault_page_renders_demo_source_by_default() -> None:
    response = get("/vault")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Source: demo" in response.text
    assert "read-only" in response.text.lower()
    assert "Demo Adult Alex" in response.text


def test_vault_page_renders_local_file_source_without_leaking_full_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault_path = tmp_path / "local-family-vault.json"
    vault_path.write_text(json.dumps(local_file_payload()), encoding="utf-8")
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            env="development",
            demo_mode=True,
            data_dir=Path("data"),
            reports_dir=Path("reports"),
            allow_cloud_llm=False,
            secret_key=None,
            access_password=None,
            vault_source="local_file",
            vault_file=vault_path,
        ),
    )

    response = get("/vault")

    assert response.status_code == 200
    assert "Source: local file" in response.text
    assert "local-family-vault.json" in response.text
    assert str(vault_path) not in response.text
    assert "Local Family Vault" in response.text
    assert "Local Adult One" in response.text


def test_demo_report_view_renders_briefing() -> None:
    response = get("/demo/report-view?drug=sertraline")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Medication-to-Doctor Briefing" in response.text
    assert "Demo evidence-pack coverage" in response.text


def test_demo_report_view_uses_neutral_demo_subtitle_for_any_drug() -> None:
    response = get("/demo/report-view?drug=aspirin")

    assert response.status_code == 200
    assert "Medication-to-Doctor Briefing demo" in response.text
    assert "sertraline demo" not in response.text


def test_demo_report_endpoint_returns_safe_no_claim_for_unsupported_drug() -> None:
    response = get("/demo/report?drug=aspirin")

    assert response.status_code == 200
    payload = response.json()
    assert payload["audit"]["policy_passed"] is True
    assert payload["audit"]["coverage"]["coverage_status"] == "drug_not_in_demo_pack"
    assert "no demo evidence-pack rules exist for this drug" in payload["report_markdown"].lower()


def test_reviewer_quickstart_endpoint_returns_markdown() -> None:
    response = get("/reviewer-quickstart")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Reviewer Quickstart" in response.text


def test_health_endpoint_remains_backwards_compatible() -> None:
    response = get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_endpoint_returns_liveness_status() -> None:
    response = get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "opencare-proof-kit"}


def test_readyz_endpoint_returns_ready_when_required_assets_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.main.get_required_asset_paths",
        lambda settings: [Path("README.md")],
    )
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            env="development",
            demo_mode=True,
            data_dir=Path("data"),
            reports_dir=Path("reports"),
            allow_cloud_llm=False,
            secret_key=None,
            access_password=None,
        ),
    )

    response = get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "opencare-proof-kit"}


def test_readyz_endpoint_fails_closed_when_required_asset_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.main.get_required_asset_paths",
        lambda settings: [Path("missing.file")],
    )
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            env="development",
            demo_mode=True,
            data_dir=Path("data"),
            reports_dir=Path("reports"),
            allow_cloud_llm=False,
            secret_key=None,
            access_password=None,
        ),
    )

    response = get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "service": "opencare-proof-kit",
        "missing_assets": ["missing.file"],
    }


def private_production_settings() -> Settings:
    return Settings(
        env="production",
        demo_mode=False,
        data_dir=Path("data"),
        reports_dir=Path("reports"),
        allow_cloud_llm=False,
        secret_key="s" * 32,
        access_password="vault-password",
    )


def test_private_production_keeps_health_endpoints_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.get_settings", private_production_settings)

    health_response = get("/health")
    healthz_response = get("/healthz")
    readyz_response = get("/readyz")

    assert health_response.status_code == 200
    assert healthz_response.status_code == 200
    assert readyz_response.status_code == 200


def test_private_production_redirects_protected_html_route_without_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.get_settings", private_production_settings)

    response = get("/demo/health-vault", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/access?next=%2Fdemo%2Fhealth-vault"


def test_private_production_redirects_vault_route_without_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.get_settings", private_production_settings)

    response = get("/vault", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/access?next=%2Fvault"


def test_access_page_renders_in_private_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.get_settings", private_production_settings)

    response = get("/access")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Private Access" in response.text


def test_private_production_rejects_invalid_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.main.get_settings", private_production_settings)

    response = post(
        "/access",
        data={"password": "wrong-password", "next": "/demo/health-vault"},
        follow_redirects=False,
    )

    assert response.status_code == 401
    assert "Invalid password" in response.text
    assert "set-cookie" not in response.headers


def test_private_production_allows_access_after_valid_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.main.get_settings", private_production_settings)

    login_response = post(
        "/access",
        data={"password": "vault-password", "next": "/demo/health-vault"},
        follow_redirects=False,
    )

    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/demo/health-vault"
    cookie_header = login_response.headers["set-cookie"]
    assert "opencare_access=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header

    cookie = cookie_header.split(";", 1)[0]
    protected_response = get(
        "/demo/health-vault",
        headers={"cookie": cookie},
    )

    assert protected_response.status_code == 200
    assert "Health/Family Vault Reviewer" in protected_response.text


def test_demo_mode_keeps_protected_route_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            env="production",
            demo_mode=True,
            data_dir=Path("data"),
            reports_dir=Path("reports"),
            allow_cloud_llm=False,
            secret_key="s" * 32,
            access_password=None,
        ),
    )

    response = get("/demo/health-vault")

    assert response.status_code == 200
    assert "Health/Family Vault Reviewer" in response.text


def test_demo_mode_keeps_vault_route_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: Settings(
            env="production",
            demo_mode=True,
            data_dir=Path("data"),
            reports_dir=Path("reports"),
            allow_cloud_llm=False,
            secret_key="s" * 32,
            access_password=None,
        ),
    )

    response = get("/vault")

    assert response.status_code == 200
    assert "Source: demo" in response.text
