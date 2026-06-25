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


def test_index_page_renders_html_landing_page() -> None:
    response = get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "OpenCare Proof Kit" in response.text
    assert "/reviewer-quickstart" in response.text


def test_demo_page_renders_synthetic_demo_patient() -> None:
    response = get("/demo")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Synthetic Demo Patient" in response.text


def test_demo_report_view_renders_briefing() -> None:
    response = get("/demo/report-view?drug=sertraline")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Medication-to-Doctor Briefing" in response.text


def test_reviewer_quickstart_endpoint_returns_markdown() -> None:
    response = get("/reviewer-quickstart")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Reviewer Quickstart" in response.text
