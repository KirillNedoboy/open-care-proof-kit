import hashlib
import hmac
import json
import logging
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, quote, urlsplit

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import RequestResponseEndpoint

from app import __version__
from app.agent.g2_product_repository import ProductCoreG2Repository
from app.agent.g2_runtime import G2Runtime
from app.agent.live_chat import (
    LIVE_CHAT_ACTION,
    LiveChatAuthority,
    resolve_live_chat_evidence,
)
from app.agent.models import AgentQuestion
from app.agent.policy import classify_question
from app.agent.providers.contract import AgentProvider
from app.agent.providers.deterministic import DeterministicProvider
from app.agent.providers.ollama import OllamaProvider, OllamaProviderConfig
from app.agent.providers.openai_responses import OpenAIResponsesProvider
from app.agent.service import GuardedChatService
from app.agent.trust_adapter import OpenCareAuthorizationAdapter
from app.agent_trust.builders import BuildRefused
from app.agent_trust.identifiers import ACTION_REQUIREMENTS
from app.config import ConfigError, Settings, get_settings
from app.demo_pipeline import DemoBriefingResult, build_demo_briefing
from app.family_access.api import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    family_access_exception_handler,
)
from app.family_access.api import router as family_access_router
from app.family_access.errors import FamilyAccessError
from app.family_access.runtime import create_family_access_runtime
from app.health_vault.loader import load_demo_family_vault
from app.health_vault.read_model import VaultReadModel, build_vault_read_model
from app.health_vault.runtime_loader import ActiveVault, load_active_vault
from app.health_vault.trace_graph import build_vault_trace_graph
from app.http_security import is_same_origin
from app.product_core.api import resolve_product_core_access
from app.product_core.api import router as product_core_router
from app.product_core.errors import (
    AccessAuditUnavailableError,
    ScopeForbiddenError,
)
from app.product_core.errors import NotFoundError as ProductCoreNotFoundError
from app.product_core.runtime import create_product_core_runtime
from app.reports.json_audit import PIPELINE_STEPS
from app.vault.loader import load_health_vault
from app.vault.schema import HealthVault


def _build_agent_provider(settings: Settings) -> AgentProvider:
    """Operator-configured provider; deterministic remains the default."""
    if settings.agent_mode == "ollama":
        return OllamaProvider(
            OllamaProviderConfig(
                endpoint_url=settings.ollama_endpoint or "http://127.0.0.1:11434",
                model=settings.ollama_model or "",
                timeout_seconds=settings.ollama_timeout_seconds,
                max_response_bytes=settings.ollama_max_response_bytes,
            )
        )
    if settings.agent_mode == "openai_responses":
        return OpenAIResponsesProvider.from_settings(settings)
    return DeterministicProvider()


def _provider_status_label(settings: Settings) -> str:
    if settings.agent_mode == "ollama":
        return "Self-hosted model configured by operator"
    if settings.agent_mode == "openai_responses":
        return "External model configured by operator"
    return "Local deterministic demo"


logger = logging.getLogger(__name__)


@asynccontextmanager
async def product_core_lifespan(application: FastAPI) -> AsyncIterator[None]:
    runtime_factory = getattr(application.state, "product_core_runtime_factory", None)
    try:
        if runtime_factory is None:
            runtime = create_product_core_runtime(get_settings())
        else:
            runtime = runtime_factory(get_settings())
        runtime.database.migrate()
        family_runtime_factory = getattr(application.state, "family_access_runtime_factory", None)
        if family_runtime_factory is None:
            family_runtime = create_family_access_runtime(
                get_settings(),
                runtime.database,
                clock=runtime.clock,
                id_factory=runtime.id_factory,
            )
        else:
            family_runtime = family_runtime_factory(get_settings(), runtime)
        settings = get_settings()
        provider = _build_agent_provider(settings)
        adapter = OpenCareAuthorizationAdapter(family_runtime.service)

        def build_envelope(**kwargs: Any) -> Any:
            authority = LiveChatAuthority(
                runtime,
                family_runtime.service,
                provider,
                question=str(kwargs["question"]),
                clock=runtime.clock,
            )
            return authority.build_envelope(
                actor_id=str(kwargs["actor_id"]),
                credential_id=str(kwargs["credential_id"]),
                person_id=str(kwargs["person_id"]),
            )

        def revalidate(pending: Any, session: Any) -> bool:
            if session.active_person_id != pending.person_id:
                return False
            required_scopes = ACTION_REQUIREMENTS.get(
                pending.action_id, (frozenset(), frozenset())
            )[0]
            decision = adapter.authorize(
                actor_id=session.actor_id,
                credential_id=session.credential_id,
                person_id=pending.person_id,
                required_scopes=required_scopes,
                authorized_at=runtime.clock(),
            )
            return (
                decision.decision == "allow"
                and decision.snapshot is not None
                and pending.provider_hash == provider.descriptor.descriptor_hash
            )

        def authorize_receipt(actor_id: str, credential_id: str, person_id: str) -> bool:
            decision = adapter.authorize(
                actor_id=actor_id,
                credential_id=credential_id,
                person_id=person_id,
                required_scopes=ACTION_REQUIREMENTS[LIVE_CHAT_ACTION][0],
                authorized_at=runtime.clock(),
            )
            return decision.decision == "allow"

        g2_runtime = G2Runtime(
            family_runtime.sessions,
            prepare_envelope=build_envelope,
            revalidate=revalidate,
            provider=provider,
            repository=ProductCoreG2Repository(runtime.database),
            project=lambda projection, _question: {
                "provider_id": provider.descriptor.provider_id,
                "model_id": provider.descriptor.model_id,
                "provider_kind": provider.descriptor.provider_kind,
                "external": provider.descriptor.external,
                "retention": "provider policy; OpenCare does not retain provider payloads",
                "evidence_count": len(projection.evidence),
                "fields": list(projection.allowed_fields),
                "disclosure_constraints": list(projection.disclosure_constraints),
            },
            resolve_evidence=lambda envelope: resolve_live_chat_evidence(
                runtime, envelope, runtime.clock()
            ),
            authorize_receipt=authorize_receipt,
            clock=runtime.clock,
        )
    except Exception:
        logger.error("Product Core startup failed", exc_info=False)
        raise
    application.state.product_core_runtime = runtime
    application.state.family_access_runtime = family_runtime
    application.state.g2_runtime = g2_runtime
    try:
        yield
    finally:
        if hasattr(application.state, "product_core_runtime"):
            del application.state.product_core_runtime
        if hasattr(application.state, "family_access_runtime"):
            del application.state.family_access_runtime
        if hasattr(application.state, "g2_runtime"):
            del application.state.g2_runtime


app = FastAPI(title="OpenCare Proof Kit", version=__version__, lifespan=product_core_lifespan)
APP_DIR = Path(__file__).resolve().parent
RUNTIME_ASSETS_DIR = APP_DIR / "assets"
REVIEWER_QUICKSTART_PATH = RUNTIME_ASSETS_DIR / "docs" / "reviewer_quickstart.md"
HEALTH_VAULT_MANIFEST_PATH = (
    RUNTIME_ASSETS_DIR / "docs" / "health_vault" / "family-vault-manifest.json"
)
SERVICE_NAME = "opencare-proof-kit"
ACCESS_COOKIE_NAME = "opencare_access"
ACCESS_COOKIE_VALUE = "private-access"
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.include_router(product_core_router)
app.include_router(family_access_router)
app.add_exception_handler(FamilyAccessError, family_access_exception_handler)


def _is_public_path(path: str) -> bool:
    return path in {"/health", "/healthz", "/readyz", "/access", "/favicon.ico"} or path.startswith(
        "/static/"
    )


def _uses_actor_session_boundary(path: str) -> bool:
    return (
        path
        in {
            "/",
            "/workspace",
            "/genetics",
            "/vault",
            "/chat",
            "/api/chat",
            "/login",
            "/register",
            "/bootstrap",
            "/invite",
            "/family-access",
        }
        or path.startswith("/api/chat/")
        or path.startswith("/api/product-core/")
        or path.startswith("/api/family-access/")
    )


def _normalize_next_path(next_path: str | None, *, default: str = "/") -> str:
    if next_path is None or not next_path.strip():
        return default

    parsed = urlsplit(next_path)
    if parsed.scheme or parsed.netloc:
        return default
    if not parsed.path.startswith("/"):
        return default
    if parsed.path.startswith("/access"):
        return default

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
    if _is_public_path(request.url.path) or _uses_actor_session_boundary(request.url.path):
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
def index() -> RedirectResponse:
    return RedirectResponse(url="/workspace", status_code=307)


def _live_access_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, AccessAuditUnavailableError):
        return JSONResponse({"detail": "Sensitive access could not be audited."}, status_code=503)
    if isinstance(exc, ScopeForbiddenError):
        return JSONResponse({"detail": "Required scope is not granted."}, status_code=403)
    return JSONResponse({"detail": "Person was not found."}, status_code=404)


def _resolve_browser_access(request: Request) -> Any:
    access = resolve_product_core_access(request)
    if isinstance(access, JSONResponse) and access.status_code == 401:
        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        return RedirectResponse(
            url=f"/login?next={quote(next_path, safe='')}",
            status_code=307,
        )
    return access


def _actor_page(
    request: Request,
    template_name: str,
    context: dict[str, object] | None = None,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context or {},
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/login", response_class=HTMLResponse)
def actor_login_page(request: Request, next: str | None = None) -> HTMLResponse:
    return _actor_page(
        request,
        "actor_login.html",
        {"next_path": _normalize_next_path(next, default="/workspace")},
    )


@app.get("/register", response_class=HTMLResponse)
def actor_register_page(request: Request) -> HTMLResponse:
    return _actor_page(request, "actor_register.html")


@app.get("/bootstrap", response_class=HTMLResponse)
def actor_bootstrap_page(request: Request) -> HTMLResponse:
    return _actor_page(
        request,
        "actor_bootstrap.html",
        {"bootstrap_secret_required": get_settings().is_production},
    )


@app.get("/invite", response_class=HTMLResponse)
def invitation_page(request: Request) -> HTMLResponse:
    return _actor_page(request, "invitation.html")


@app.get("/family-access", response_class=HTMLResponse)
def family_access_page(request: Request) -> Response:
    access = _resolve_browser_access(request)
    if isinstance(access, Response):
        return access
    return _actor_page(request, "family_access_workspace.html")


@app.get("/workspace", response_class=HTMLResponse)
def workspace(request: Request) -> Response:
    access = _resolve_browser_access(request)
    if isinstance(access, Response):
        return access
    if access.active_person_id is not None:
        try:
            access.require_active_person("person.read")
        except (ProductCoreNotFoundError, ScopeForbiddenError) as exc:
            return _live_access_error(exc)
    return _actor_page(
        request,
        "product_core_workspace.html",
        {"active_person_id": access.active_person_id},
    )


@app.get("/genetics", response_class=HTMLResponse)
def genetics_page(request: Request) -> Response:
    access = _resolve_browser_access(request)
    if isinstance(access, Response):
        return access
    if access.active_person_id is not None:
        try:
            access.require_active_person("person.read")
        except (ProductCoreNotFoundError, ScopeForbiddenError) as exc:
            return _live_access_error(exc)
    return _actor_page(
        request,
        "genetics.html",
        {"active_person_id": access.active_person_id},
    )


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request) -> Response:
    access = _resolve_browser_access(request)
    if isinstance(access, Response):
        return access
    try:
        person_id = access.require_active_person("chat.use", "person.read")
        person = access.runtime.people.get(person_id)
    except (ProductCoreNotFoundError, ScopeForbiddenError) as exc:
        return _live_access_error(exc)
    settings = get_settings()
    return _actor_page(
        request,
        "chat.html",
        {
            "vault_source_label": "Product Core",
            "vault_source_name": person.display_name,
            "family_label": person.display_name,
            "people": [person],
            "provider_status": _provider_status_label(settings),
            "chat_endpoint": "/api/chat",
            "live_workspace": True,
        },
    )


@app.post("/api/chat")
async def chat_api(request: Request) -> JSONResponse:
    return JSONResponse(
        {"detail": "Consent-gated chat is required.", "code": "consent_required"}, status_code=410
    )


def _g2_runtime_or_unavailable() -> Any:
    runtime = getattr(app.state, "g2_runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="Consent runtime is not ready.")
    return runtime


def _session_token(request: Request) -> str:
    token = request.cookies.get("opencare_session")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token


def _chat_request_guard(request: Request) -> JSONResponse | None:
    """Apply the normal Product Core session and CSRF boundary to G2 routes."""
    if getattr(request.app.state, "family_access_runtime", None) is not None:
        access = resolve_product_core_access(request)
        return access if isinstance(access, JSONResponse) else None
    token = request.cookies.get(SESSION_COOKIE_NAME)
    runtime = getattr(request.app.state, "g2_runtime", None)
    if runtime is None or not token or runtime.sessions.resolve(token) is None:
        return JSONResponse({"detail": "Authentication required."}, status_code=401)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("origin") is None or not is_same_origin(request):
            return JSONResponse({"detail": "The request origin is not allowed."}, status_code=403)
        csrf = request.headers.get(CSRF_HEADER_NAME)
        if csrf is None or not runtime.sessions.verify_csrf(token, csrf):
            return JSONResponse({"detail": "CSRF validation failed."}, status_code=403)
    return None


async def _chat_json(request: Request, *, keys: set[str]) -> dict[str, Any] | JSONResponse:
    content_type = request.headers.get("content-type", "").lower()
    if not content_type.startswith("application/json"):
        return JSONResponse({"detail": "JSON content type is required."}, status_code=415)
    body = await request.body()
    if len(body) > 10_000:
        return JSONResponse({"detail": "Request is too large."}, status_code=413)
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse({"detail": "Malformed JSON request."}, status_code=400)
    if not isinstance(payload, dict) or set(payload) != keys:
        return JSONResponse({"detail": "The request shape is invalid."}, status_code=422)
    return payload


@app.post("/api/chat/prepare")
async def chat_prepare(request: Request) -> JSONResponse:
    guarded = _chat_request_guard(request)
    if guarded is not None:
        return guarded
    runtime = _g2_runtime_or_unavailable()
    payload = await _chat_json(request, keys={"question"})
    if isinstance(payload, JSONResponse):
        return payload
    try:
        question = AgentQuestion.model_validate(payload).question
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="A question is required.") from exc
    policy = classify_question(question)
    if policy.decision != "allowed":
        return JSONResponse(
            {
                "status": "refused",
                "answer": policy.response_text,
                "reason_code": policy.reason_code,
                "boundary_notices": [
                    "OpenCare does not provide diagnosis or treatment recommendations."
                ],
            }
        )
    try:
        result = runtime.prepare(
            _session_token(request),
            question,
            purpose_id="record_explanation",
            action_id="answer_question",
        )
    except (PermissionError, BuildRefused, ValueError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return JSONResponse({"status": "prepared", **jsonable_encoder(result.__dict__)})


@app.post("/api/chat/executions/{execution_id}/consent")
async def chat_consent(execution_id: str, request: Request) -> JSONResponse:
    guarded = _chat_request_guard(request)
    if guarded is not None:
        return guarded
    runtime = _g2_runtime_or_unavailable()
    payload = await _chat_json(request, keys={"fields"})
    if isinstance(payload, JSONResponse):
        return payload
    fields = payload.get("fields")
    if not isinstance(fields, list) or not all(isinstance(item, str) for item in fields):
        raise HTTPException(status_code=422, detail="Disclosure fields are required.")
    try:
        result = runtime.grant_disclosure_consent(
            _session_token(request), execution_id, fields=fields
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return JSONResponse(jsonable_encoder(result.__dict__))


@app.post("/api/chat/executions/{execution_id}/execute")
async def chat_execute(execution_id: str, request: Request) -> JSONResponse:
    guarded = _chat_request_guard(request)
    if guarded is not None:
        return guarded
    runtime = _g2_runtime_or_unavailable()
    payload = await _chat_json(request, keys={"question"})
    if isinstance(payload, JSONResponse):
        return payload
    try:
        question = AgentQuestion.model_validate(payload).question
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="A question is required.") from exc
    result = runtime.execute(_session_token(request), execution_id, question)
    return JSONResponse(jsonable_encoder(result.__dict__))


@app.get("/api/chat/executions/{execution_id}/receipt")
async def chat_receipt(execution_id: str, request: Request) -> JSONResponse:
    guarded = _chat_request_guard(request)
    if guarded is not None:
        return guarded
    runtime = _g2_runtime_or_unavailable()
    getter = getattr(runtime, "get_receipt", None)
    if getter is None:
        raise HTTPException(status_code=404, detail="Receipt unavailable.")
    receipt = getter(_session_token(request), execution_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Receipt unavailable.")
    return JSONResponse(jsonable_encoder(receipt))


@app.get("/demo/chat", response_class=HTMLResponse)
def demo_chat_page(request: Request) -> HTMLResponse:
    settings = get_settings()
    active_vault = load_active_vault(settings)
    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "vault_source_label": active_vault.source_label,
            "vault_source_name": active_vault.source_basename or "Synthetic demo vault",
            "family_label": active_vault.read_model.family.display_name,
            "people": active_vault.read_model.people,
            "provider_status": _provider_status_label(settings),
            "chat_endpoint": "/api/demo/chat",
            "live_workspace": False,
        },
    )


@app.post("/api/demo/chat")
async def demo_chat_api(request: Request) -> JSONResponse:
    if not is_same_origin(request):
        return JSONResponse({"detail": "Cross-origin request rejected."}, status_code=403)
    content_type = request.headers.get("content-type", "").lower()
    if not content_type.startswith("application/json"):
        return JSONResponse({"detail": "JSON content type is required."}, status_code=415)
    body = await request.body()
    if len(body) > 10_000:
        return JSONResponse({"detail": "Question is too long."}, status_code=413)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JSONResponse({"detail": "Malformed JSON request."}, status_code=400)
    if not isinstance(payload, dict) or not isinstance(payload.get("question"), str):
        return JSONResponse({"detail": "A question is required."}, status_code=422)
    question = payload["question"].strip()
    if not question:
        return JSONResponse({"detail": "A question is required."}, status_code=422)
    if len(question) > 2_000:
        return JSONResponse({"detail": "Question is too long."}, status_code=413)
    answer = GuardedChatService.for_settings(get_settings()).answer(
        AgentQuestion(question=question).question
    )
    return JSONResponse(answer.model_dump())


def get_required_asset_paths(settings: Settings) -> list[Path]:
    required_paths = [
        settings.data_dir / "demo_patients" / "demo_patient_a.json",
        settings.data_dir / "demo_patients" / "demo_family_vault.json",
        REVIEWER_QUICKSTART_PATH,
        HEALTH_VAULT_MANIFEST_PATH,
        APP_DIR / "templates",
        APP_DIR / "static",
    ]
    if settings.vault_source == "local_file" and settings.vault_file is not None:
        required_paths.append(settings.vault_file)
    return required_paths


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/favicon.ico", status_code=204)
def favicon() -> Response:
    return Response(status_code=204)


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
    return REVIEWER_QUICKSTART_PATH.read_text(encoding="utf-8")


def _load_health_vault_manifest() -> dict[str, Any]:
    manifest = json.loads(HEALTH_VAULT_MANIFEST_PATH.read_text(encoding="utf-8"))
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
        secure=settings.is_production,
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
        active_vault.source_basename if active_vault.source_basename is not None else "demo"
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
def vault_page(request: Request) -> Response:
    access = _resolve_browser_access(request)
    if isinstance(access, Response):
        return access
    try:
        person_id = access.require_active_person(
            "person.read",
            "source.read",
            "medication.read",
            "timeline.read",
            "visit.read",
        )
        person = access.runtime.people.get(person_id)
    except (ProductCoreNotFoundError, ScopeForbiddenError) as exc:
        return _live_access_error(exc)
    return _actor_page(request, "product_core_vault.html", {"person": person})


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
