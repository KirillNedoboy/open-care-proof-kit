import asyncio

import httpx

from app.main import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(request())


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
    assert "report_markdown" not in payload
