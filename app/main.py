import hashlib
import hmac
import json
import re
from html import escape
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, quote, urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import RequestResponseEndpoint

from app import __version__
from app.config import ConfigError, Settings, get_settings
from app.demo_pipeline import DemoBriefingResult, build_demo_briefing
from app.health_vault.loader import load_demo_family_vault
from app.health_vault.read_model import VaultReadModel, build_vault_read_model
from app.health_vault.runtime_loader import ActiveVault, load_active_vault
from app.health_vault.trace_graph import build_vault_trace_graph
from app.reports.json_audit import PIPELINE_STEPS
from app.vault.loader import load_health_vault
from app.vault.schema import HealthVault

app = FastAPI(title="OpenCare Proof Kit", version=__version__)
APP_DIR = Path(__file__).resolve().parent
SERVICE_NAME = "opencare-proof-kit"
ACCESS_COOKIE_NAME = "opencare_access"
ACCESS_COOKIE_VALUE = "private-access"
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")


def _is_public_path(path: str) -> bool:
    return (
        path in {"/health", "/healthz", "/readyz", "/access"}
        or path.startswith("/static/")
    )


def _normalize_next_path(next_path: str | None) -> str:
    if next_path is None or not next_path.strip():
        return "/"

    parsed = urlsplit(next_path)
    if parsed.scheme or parsed.netloc:
        return "/"
    if not parsed.path.startswith("/"):
        return "/"
    if parsed.path.startswith("/access"):
        return "/"

    normalized = parsed.path
    if parsed.query:
        normalized = f"{normalized}?{parsed.query}"
    return normalized


def _build_access_cookie(secret_key: str) -> str:
    signature = hmac.new(
        secret_key.encode("utf-8"),
        ACCESS_COOKIE_VALUE.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{ACCESS_COOKIE_VALUE}.{signature}"


def _has_valid_access_cookie(request: Request, settings: Settings) -> bool:
    if settings.secret_key is None:
        return False

    cookie = request.cookies.get(ACCESS_COOKIE_NAME)
    if cookie is None:
        return False
    return hmac.compare_digest(cookie, _build_access_cookie(settings.secret_key))


def _redirect_to_access(request: Request) -> RedirectResponse:
    next_path = request.url.path
    if request.url.query:
        next_path = f"{next_path}?{request.url.query}"
    return RedirectResponse(
        url=f"/access?next={quote(next_path, safe='')}",
        status_code=307,
    )


@app.middleware("http")
async def enforce_private_access(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    if _is_public_path(request.url.path):
        return await call_next(request)

    try:
        settings = get_settings()
    except ConfigError:
        return JSONResponse(
            {
                "status": "not_ready",
                "service": SERVICE_NAME,
                "reason": "invalid_configuration",
            },
            status_code=503,
        )

    if not settings.private_mode_enabled or _has_valid_access_cookie(request, settings):
        return await call_next(request)

    if request.method == "GET":
        return _redirect_to_access(request)

    return JSONResponse({"detail": "Private access required."}, status_code=401)


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


def get_required_asset_paths(settings: Settings) -> list[Path]:
    required_paths = [
        settings.data_dir / "demo_patients" / "demo_patient_a.json",
        settings.data_dir / "demo_patients" / "demo_family_vault.json",
        Path("docs") / "reviewer_quickstart.md",
        Path("docs") / "assets" / "health_vault" / "family-vault-manifest.json",
        APP_DIR / "templates",
        APP_DIR / "static",
    ]
    if settings.vault_source == "local_file" and settings.vault_file is not None:
        required_paths.append(settings.vault_file)
    return required_paths


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/readyz")
def readyz() -> Response:
    try:
        settings = get_settings()
    except ConfigError:
        return JSONResponse(
            {
                "status": "not_ready",
                "service": SERVICE_NAME,
                "reason": "invalid_configuration",
            },
            status_code=503,
        )

    missing_assets = [
        str(path).replace("\\", "/")
        for path in get_required_asset_paths(settings)
        if not path.exists()
    ]
    if missing_assets:
        return JSONResponse(
            {
                "status": "not_ready",
                "service": SERVICE_NAME,
                "missing_assets": missing_assets,
            },
            status_code=503,
        )

    return JSONResponse({"status": "ready", "service": SERVICE_NAME})


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


@app.get("/access", response_class=HTMLResponse)
def access_page(request: Request, next: str = "/") -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="access.html",
        context={
            "next_path": _normalize_next_path(next),
            "error_message": None,
        },
    )


@app.post("/access", response_class=HTMLResponse)
async def access_submit(request: Request) -> Response:
    try:
        settings = get_settings()
    except ConfigError:
        return JSONResponse(
            {
                "status": "not_ready",
                "service": SERVICE_NAME,
                "reason": "invalid_configuration",
            },
            status_code=503,
        )

    form_data = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
    next_path = _normalize_next_path(form_data.get("next", ["/"])[0])
    password = form_data.get("password", [""])[0]

    if settings.access_password is None or not hmac.compare_digest(
        password,
        settings.access_password,
    ):
        return templates.TemplateResponse(
            request=request,
            name="access.html",
            context={
                "next_path": next_path,
                "error_message": "Invalid password.",
            },
            status_code=401,
        )

    response = RedirectResponse(url=next_path, status_code=303)
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=_build_access_cookie(settings.secret_key or ""),
        httponly=True,
        samesite="lax",
    )
    return response


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


def _build_vault_page_context(
    active_vault: ActiveVault,
    *,
    include_trace_graph: bool,
    include_trust_flags: bool,
    page_eyebrow: str,
    page_title: str,
    page_lede: str,
) -> dict[str, Any]:
    read_model = active_vault.read_model
    people_lookup = {person.id: person.display_name for person in read_model.people}
    trace_graph = build_vault_trace_graph(read_model) if include_trace_graph else None
    manifest = _load_health_vault_manifest() if include_trust_flags else None
    source_name = (
        active_vault.source_basename
        if active_vault.source_basename is not None
        else "demo"
    )

    return {
        "page_eyebrow": page_eyebrow,
        "page_title": page_title,
        "page_lede": page_lede,
        "vault_source_label": active_vault.source_label,
        "vault_source_name": source_name,
        "show_trace_graph": trace_graph is not None,
        "show_trust_flags": include_trust_flags,
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
        "trace_graph": trace_graph,
        "trust_flags": (
            _trust_flags(manifest, read_model)
            if manifest is not None
            else [
                {"label": "Vault source", "value": active_vault.source_label},
                {"label": "Mounted file", "value": source_name},
                {
                    "label": "Provenance coverage",
                    "value": (
                        f"{read_model.provenance_coverage.records_with_source}/"
                        f"{read_model.provenance_coverage.total_important_records} "
                        "important records source-backed"
                    ),
                },
            ]
        ),
        "safety_banner_items": [
            "read-only",
            f"source: {active_vault.source_label}",
            *(
                ["synthetic/demo-only"]
                if read_model.family.demo_only and read_model.family.synthetic
                else ["operator-supplied local file"]
            ),
            "deterministic summary of recorded context",
            "not diagnosis",
            "not treatment recommendation",
            "not dosage guidance",
            "not medication selection",
            "no start/stop medication advice",
            "no genetics in this layer",
            "not clinical validation",
        ],
        "person_record_note": (
            "Synthetic person record for reviewer inspection only."
            if active_vault.source_kind == "demo"
            else "Read-only vault person record for viewer inspection only."
        ),
        "what_this_page_does_not_do": [
            "Does not diagnose.",
            "Does not recommend treatment or medication selection.",
            "Does not provide dosage guidance or start/stop medication advice.",
            "Does not add genetics, raw genotype, or genome_profile support.",
            "Does not use LLM generation.",
            "Does not accept uploads or user-entered data on this page.",
            "Does not provide medical interpretation or clinical validation.",
        ],
    }


def _build_health_vault_page_context() -> dict[str, Any]:
    dataset = load_demo_family_vault()
    read_model = build_vault_read_model(dataset)
    return _build_vault_page_context(
        ActiveVault(
            dataset=dataset,
            read_model=read_model,
            source_kind="demo",
            source_label="demo",
            source_basename=None,
        ),
        include_trace_graph=True,
        include_trust_flags=True,
        page_eyebrow="Local reviewer UI",
        page_title="Health/Family Vault Reviewer",
        page_lede=(
            "Read-only reviewer page for the synthetic family vault, deterministic read model, "
            "provenance coverage, and visible safety boundaries."
        ),
    )


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


@app.get("/vault", response_class=HTMLResponse)
def vault_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    active_vault = load_active_vault(settings)
    return templates.TemplateResponse(
        request=request,
        name="health_vault.html",
        context=_build_vault_page_context(
            active_vault,
            include_trace_graph=False,
            include_trust_flags=False,
            page_eyebrow="Local vault UI",
            page_title="Health/Family Vault",
            page_lede=(
                "Read-only vault page for the active configured source, with deterministic "
                "provenance coverage and visible safety boundaries."
            ),
        ),
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
