from __future__ import annotations

import asyncio

import httpx

from app.main import app


def get(path: str, *, follow_redirects: bool = True) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=follow_redirects,
        ) as client:
            return await client.get(path)

    return asyncio.run(send())


def test_root_redirects_to_workspace() -> None:
    response = get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/workspace"


def test_workspace_renders_a_static_product_shell() -> None:
    response = get("/workspace")

    assert response.status_code == 200
    assert "Visit Preparation Workspace" in response.text
    assert 'id="person-selector"' in response.text
    assert 'id="create-profile-form"' in response.text
    assert 'id="edit-profile"' in response.text
    assert 'id="person-id"' not in response.text
    assert 'id="medication-form"' in response.text
    assert 'id="review-inbox"' in response.text
    assert 'id="candidate-history"' in response.text
    assert 'id="canonical-medications"' in response.text
    assert 'id="timeline"' in response.text
    assert 'id="visit-form"' in response.text
    assert 'id="visits"' in response.text
    assert 'id="visit-question-form"' in response.text
    assert 'id="visit-questions"' in response.text
    assert 'id="initialize-brief"' in response.text
    assert 'id="brief-evidence-selection"' in response.text
    assert 'id="brief-preparation-notes"' in response.text
    assert 'id="brief-revisions"' in response.text
    assert 'id="brief-markdown"' in response.text
    assert 'id="workspace-status"' in response.text
    assert "/static/product_core_workspace.css" in response.text
    assert "/static/product_core_workspace.js" in response.text
    assert "person-demo" not in response.text


def test_chat_remains_available() -> None:
    response = get("/chat")

    assert response.status_code == 200
    assert "OpenCare chat" in response.text
