from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response

from app import __version__
from app.demo_pipeline import DemoBriefingResult, build_demo_briefing

app = FastAPI(title="OpenCare Proof Kit", version=__version__)


@app.get("/")
def index() -> dict[str, str]:
    return {
        "project": "OpenCare Proof Kit",
        "mode": "local-first demo",
        "demo_report": "/demo/report?drug=sertraline",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _build_checked_demo_briefing(drug: str) -> DemoBriefingResult:
    try:
        result = build_demo_briefing(drug)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not result.policy_passed:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Safety policy failed.",
                "violations": result.policy_violations,
            },
        )

    return result


@app.get("/demo/report")
def demo_report(drug: str = "sertraline") -> dict[str, Any]:
    result = _build_checked_demo_briefing(drug)
    return {"report_markdown": result.report_markdown, "audit": result.audit}


@app.get("/demo/report.md")
def demo_report_markdown(drug: str = "sertraline") -> Response:
    result = _build_checked_demo_briefing(drug)
    return Response(content=result.report_markdown, media_type="text/markdown")


@app.get("/demo/audit")
def demo_audit(drug: str = "sertraline") -> dict[str, Any]:
    result = _build_checked_demo_briefing(drug)
    return result.audit


def build_demo_report_to_file(output_dir: Path, drug: str = "sertraline") -> Path:
    result = demo_report(drug=drug)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"demo-{drug}-briefing.md"
    report_path.write_text(str(result["report_markdown"]), encoding="utf-8")
    return report_path
