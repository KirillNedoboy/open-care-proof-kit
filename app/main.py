import json
import re
from html import escape
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import __version__
from app.config import get_settings
from app.demo_pipeline import DemoBriefingResult, build_demo_briefing
from app.health_vault.loader import load_demo_family_vault
from app.health_vault.read_model import VaultReadModel, build_vault_read_model
from app.reports.json_audit import PIPELINE_STEPS
from app.vault.loader import load_health_vault
from app.vault.schema import HealthVault

app = FastAPI(title="OpenCare Proof Kit", version=__version__)
APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "project": "OpenCare Proof Kit",
            "quick_links": [
                ("Open local web demo", "/demo"),
                ("View report HTML", "/demo/report-view?drug=sertraline"),
                ("Read report Markdown", "/demo/report.md?drug=sertraline"),
                ("Inspect audit JSON", "/demo/audit?drug=sertraline"),
                ("Reviewer quickstart", "/reviewer-quickstart"),
            ],
            "pipeline_steps": PIPELINE_STEPS,
        },
    )


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


def _load_demo_vault() -> HealthVault:
    patient_path = get_settings().data_dir / "demo_patients" / "demo_patient_a.json"
    return load_health_vault(patient_path)


def _load_reviewer_quickstart() -> str:
    quickstart_path = Path("docs") / "reviewer_quickstart.md"
    return quickstart_path.read_text(encoding="utf-8")


def _load_health_vault_manifest() -> dict[str, Any]:
    manifest_path = Path("docs") / "assets" / "health_vault" / "family-vault-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], manifest)


def _format_inline_markdown(text: str) -> str:
    escaped = escape(text)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def _render_report_markdown_as_html(report_markdown: str) -> str:
    html_parts: list[str] = []
    list_type: str | None = None
    number_pattern = re.compile(r"^\d+\.\s+(.*)$")

    def close_list() -> None:
        nonlocal list_type
        if list_type is not None:
            html_parts.append(f"</{list_type}>")
            list_type = None

    for raw_line in report_markdown.splitlines():
        line = raw_line.strip()
        if not line:
            close_list()
            continue

        if line.startswith("# "):
            close_list()
            html_parts.append(f"<h1>{_format_inline_markdown(line[2:])}</h1>")
            continue
        if line.startswith("## "):
            close_list()
            html_parts.append(f"<h2>{_format_inline_markdown(line[3:])}</h2>")
            continue
        if line.startswith("### "):
            close_list()
            html_parts.append(f"<h3>{_format_inline_markdown(line[4:])}</h3>")
            continue
        if line.startswith("- "):
            if list_type != "ul":
                close_list()
                list_type = "ul"
                html_parts.append("<ul>")
            html_parts.append(f"<li>{_format_inline_markdown(line[2:])}</li>")
            continue

        number_match = number_pattern.match(line)
        if number_match:
            if list_type != "ol":
                close_list()
                list_type = "ol"
                html_parts.append("<ol>")
            html_parts.append(f"<li>{_format_inline_markdown(number_match.group(1))}</li>")
            continue

        close_list()
        html_parts.append(f"<p>{_format_inline_markdown(line)}</p>")

    close_list()
    return "\n".join(html_parts)


@app.get("/demo", response_class=HTMLResponse)
def demo_page(request: Request) -> HTMLResponse:
    vault = _load_demo_vault()
    return templates.TemplateResponse(
        request=request,
        name="demo.html",
        context={
            "patient": vault,
            "pipeline_steps": PIPELINE_STEPS,
            "question_drug": "sertraline",
        },
    )


def _group_overviews_by_person(
    grouped: dict[str, list[Any]],
    people_lookup: dict[str, str],
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for person_id, items in grouped.items():
        if not items:
            continue
        sections.append(
            {
                "person_id": person_id,
                "person_name": people_lookup.get(person_id, person_id),
                "records": items,
            }
        )
    return sections


def _build_health_vault_page_context() -> dict[str, Any]:
    dataset = load_demo_family_vault()
    read_model = build_vault_read_model(dataset)
    manifest = _load_health_vault_manifest()
    people_lookup = {person.id: person.display_name for person in read_model.people}

    return {
        "family": read_model.family,
        "people": read_model.people,
        "relationships": [
            {
                "person_name": people_lookup.get(item.person_id, item.person_id),
                "related_person_name": people_lookup.get(
                    item.related_person_id,
                    item.related_person_id,
                ),
                "relationship_type": item.relationship_type,
            }
            for item in read_model.relationships
        ],
        "medication_sections": _group_overviews_by_person(
            read_model.medications_by_person,
            people_lookup,
        ),
        "condition_sections": _group_overviews_by_person(
            read_model.conditions_by_person,
            people_lookup,
        ),
        "lab_sections": _group_overviews_by_person(
            read_model.labs_by_person,
            people_lookup,
        ),
        "visit_sections": _group_overviews_by_person(
            read_model.visits_by_person,
            people_lookup,
        ),
        "timeline_events": [
            {
                "date": event.date,
                "person_name": people_lookup.get(event.person_id, event.person_id),
                "title": event.title,
                "event_type": event.event_type,
                "source_links": event.source_links,
            }
            for event in read_model.timeline.events
        ],
        "questions": [
            {
                "id": question.id,
                "scope": question.scope,
                "scope_label": (
                    people_lookup.get(question.person_id, question.person_id)
                    if question.person_id
                    else "Family"
                ),
                "status": question.status,
                "question": question.question,
                "source_links": question.source_links,
            }
            for question in read_model.questions
        ],
        "provenance_coverage": read_model.provenance_coverage,
        "trust_flags": _trust_flags(manifest, read_model),
        "safety_banner_items": [
            "synthetic/demo-only",
            "deterministic summary of recorded context",
            "not diagnosis",
            "not treatment recommendation",
            "not dosage guidance",
            "not medication selection",
            "no start/stop medication advice",
            "no genetics in this layer",
            "not clinical validation",
        ],
        "what_this_page_does_not_do": [
            "Does not diagnose.",
            "Does not recommend treatment or medication selection.",
            "Does not provide dosage guidance or start/stop medication advice.",
            "Does not add genetics, raw genotype, or genome_profile support.",
            "Does not use LLM generation.",
            "Does not accept uploads or user-entered data on this page.",
        ],
    }


def _trust_flags(manifest: dict[str, Any], read_model: VaultReadModel) -> list[dict[str, str]]:
    coverage = read_model.provenance_coverage
    return [
        {"label": "Manifest demo_only", "value": str(manifest.get("demo_only", False)).lower()},
        {"label": "Manifest synthetic", "value": str(manifest.get("synthetic", False)).lower()},
        {
            "label": "Manifest no_llm_generation",
            "value": str(manifest.get("no_llm_generation", False)).lower(),
        },
        {
            "label": "Manifest no_genetics",
            "value": str(manifest.get("no_genetics", False)).lower(),
        },
        {
            "label": "Manifest no_medical_advice",
            "value": str(manifest.get("no_medical_advice", False)).lower(),
        },
        {
            "label": "Provenance coverage",
            "value": (
                f"{coverage.records_with_source}/{coverage.total_important_records} "
                "important records source-backed"
            ),
        },
        {
            "label": "Safety notice count",
            "value": str(manifest.get("safety_boundary_notice_count", 0)),
        },
    ]


@app.get("/demo/health-vault", response_class=HTMLResponse)
def health_vault_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="health_vault.html",
        context=_build_health_vault_page_context(),
    )


@app.get("/reviewer-quickstart")
def reviewer_quickstart() -> Response:
    return Response(content=_load_reviewer_quickstart(), media_type="text/markdown")


@app.get("/demo/report-view", response_class=HTMLResponse)
def demo_report_view(request: Request, drug: str = "sertraline") -> HTMLResponse:
    result = _build_checked_demo_briefing(drug)
    audit = result.audit
    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "drug": drug,
            "policy_passed": result.policy_passed,
            "findings_count": result.findings_count,
            "coverage": result.coverage,
            "policy_violations": result.policy_violations,
            "report_html": _render_report_markdown_as_html(result.report_markdown),
            "audit": audit,
            "audit_summary": [
                ("Report ID", str(audit["report_id"])),
                ("Created at", str(audit["created_at"])),
                ("Evidence pack", str(audit["evidence_pack_id"])),
                ("Evidence pack version", str(audit["evidence_pack_version"])),
                ("Coverage status", str(audit["coverage"]["coverage_status"])),
                ("Policy passed", str(audit["policy_passed"])),
                (
                    "Raw data exported",
                    str(audit["raw_health_or_genetic_data_exported"]),
                ),
            ],
        },
    )


@app.get("/demo/report")
def demo_report(drug: str = "sertraline") -> dict[str, Any]:
    result = _build_checked_demo_briefing(drug)
    return {
        "report_markdown": result.report_markdown,
        "coverage": result.coverage,
        "audit": result.audit,
    }


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
