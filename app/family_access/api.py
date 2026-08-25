from __future__ import annotations

import hmac
import logging
from dataclasses import asdict, dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.responses import Response as StarletteResponse

from app.family_access.api_models import (
    ActivePersonRequest,
    AssignmentCreateRequest,
    AssignmentReviseRequest,
    AssignmentUpgradeRequest,
    BootstrapRequest,
    EmptyRequest,
    FamilyCreateRequest,
    InvitationAcceptRequest,
    InvitationCreateRequest,
    InvitationRegisterRequest,
    InvitationSecretRequest,
    LoginRequest,
    MembershipCreateRequest,
    PasswordChangeRequest,
    PersonCreateRequest,
    RelationshipCreateRequest,
)
from app.family_access.errors import (
    AuthenticationError,
    AuthorizationError,
    BootstrapUnavailableError,
    ConfirmationRequiredError,
    ConflictError,
    FamilyAccessError,
    InvitationUnavailableError,
    LastAdministratorError,
    LastOwnerError,
    NotFoundError,
    PersonAccessDeniedError,
    ValidationError,
)
from app.family_access.models import ActorRecord
from app.family_access.policy import OWNER_SCOPES
from app.family_access.runtime import FamilyAccessRuntime
from app.family_access.sessions import CreatedSession, SessionRecord
from app.http_security import is_same_origin

SESSION_COOKIE_NAME = "opencare_session"
CSRF_COOKIE_NAME = "opencare_csrf"
CSRF_HEADER_NAME = "x-opencare-csrf"
logger = logging.getLogger(__name__)


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


async def family_access_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, FamilyAccessError):
        return _error(500, "family_access_failure", "Family access storage failed.")
    if isinstance(exc, InvitationUnavailableError):
        return _error(404, "invitation_unavailable", "Invitation is unavailable.")
    if isinstance(exc, PersonAccessDeniedError):
        return _error(404, "person_not_found", "Person was not found.")
    if isinstance(exc, NotFoundError):
        return _error(404, "resource_not_found", "Resource was not found.")
    if isinstance(exc, AuthenticationError):
        return _error(401, "authentication_required", "Authentication is required.")
    if isinstance(exc, ConfirmationRequiredError):
        return _error(403, "owner_confirmation_required", "Explicit confirmation is required.")
    if isinstance(exc, AuthorizationError):
        return _error(403, "forbidden", "The operation is not permitted.")
    if isinstance(exc, BootstrapUnavailableError):
        return _error(409, "bootstrap_unavailable", "Bootstrap is unavailable.")
    if isinstance(exc, LastAdministratorError):
        return _error(409, "last_administrator", "The final administrator cannot be removed.")
    if isinstance(exc, LastOwnerError):
        return _error(409, "last_owner", "The final Person owner cannot be removed.")
    if isinstance(exc, ConflictError):
        return _error(409, "conflict", "The requested state conflicts with current state.")
    if isinstance(exc, ValidationError):
        return _error(422, "request_validation_failed", "The request is invalid.")
    return _error(500, "family_access_failure", "Family access storage failed.")


def get_family_access_runtime(request: Request) -> FamilyAccessRuntime:
    runtime = getattr(request.app.state, "family_access_runtime", None)
    if not isinstance(runtime, FamilyAccessRuntime):
        raise HTTPException(status_code=503, detail="Family access runtime is unavailable.")
    return runtime


RuntimeDependency = Annotated[FamilyAccessRuntime, Depends(get_family_access_runtime)]


def require_same_origin(request: Request) -> None:
    if request.headers.get("origin") is None or not is_same_origin(request):
        raise HTTPException(status_code=403, detail="Same-origin request required.")


@dataclass(frozen=True)
class AuthenticatedSession:
    actor: ActorRecord
    record: SessionRecord
    session_token: str


def get_authenticated_session(request: Request, runtime: RuntimeDependency) -> AuthenticatedSession:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    record = runtime.sessions.resolve(token)
    if record is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    actor = runtime.service.get_actor_for_session(record.actor_id, record.credential_id)
    if actor is None:
        try:
            runtime.sessions.revoke(token)
        except Exception:
            logger.error(
                "family_access_session_revoke_failed",
                extra={"reason_code": "stale_session_cleanup_failure"},
                exc_info=False,
            )
        raise HTTPException(status_code=401, detail="Authentication required.")
    return AuthenticatedSession(actor=actor, record=record, session_token=token)


AuthenticatedDependency = Annotated[AuthenticatedSession, Depends(get_authenticated_session)]


def require_authenticated_csrf(
    request: Request,
    runtime: RuntimeDependency,
    authenticated: AuthenticatedDependency,
) -> AuthenticatedSession:
    require_same_origin(request)
    csrf_token = request.headers.get(CSRF_HEADER_NAME)
    if csrf_token is None or not runtime.sessions.verify_csrf(
        authenticated.session_token, csrf_token
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")
    return authenticated


UnsafeAuthenticatedDependency = Annotated[AuthenticatedSession, Depends(require_authenticated_csrf)]


def _actor_payload(actor: ActorRecord) -> dict[str, object]:
    return {
        "actor_id": actor.actor_id,
        "username": actor.username_normalized,
        "display_name": actor.display_name,
        "status": actor.status,
        "created_at": actor.created_at,
    }


def _set_session_cookies(
    response: Response,
    created: CreatedSession,
    *,
    secure: bool,
) -> None:
    max_age = 8 * 60 * 60
    response.set_cookie(
        SESSION_COOKIE_NAME,
        created.session_token,
        max_age=max_age,
        expires=created.expires_at,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        created.csrf_token,
        max_age=max_age,
        expires=created.expires_at,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", httponly=False, samesite="lax")


def _session_json_response(
    request: Request,
    runtime: FamilyAccessRuntime,
    actor: ActorRecord,
    credential_id: str,
    *,
    status_code: int,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    created = runtime.sessions.create(actor.actor_id, credential_id)
    content: dict[str, object] = {"actor": _actor_payload(actor)}
    if extra:
        content.update(extra)
    response = JSONResponse(jsonable_encoder(content), status_code=status_code)
    _set_session_cookies(
        response,
        created,
        secure=runtime.settings.is_production or request.url.scheme == "https",
    )
    return response


class SanitizedValidationRoute(APIRoute):
    def get_route_handler(self) -> Any:
        original_handler = super().get_route_handler()

        async def sanitized_handler(request: Request) -> StarletteResponse:
            try:
                return await original_handler(request)
            except RequestValidationError as error:
                fields = [
                    {
                        "loc": [str(part) for part in item.get("loc", ())],
                        "type": str(item.get("type", "validation_error")),
                    }
                    for item in error.errors()
                ]
                return JSONResponse(
                    {
                        "error": {
                            "code": "request_validation_failed",
                            "message": "The request is invalid.",
                            "fields": fields,
                        }
                    },
                    status_code=422,
                )

        return sanitized_handler


router = APIRouter(
    prefix="/api/family-access/v1",
    tags=["Family Access"],
    route_class=SanitizedValidationRoute,
)


@router.get("/bootstrap-status")
def bootstrap_status(runtime: RuntimeDependency) -> dict[str, bool]:
    return {
        "bootstrap_available": runtime.service.bootstrap_available(),
        "bootstrap_secret_required": runtime.settings.is_production,
    }


@router.post("/bootstrap", status_code=201)
def bootstrap(
    payload: BootstrapRequest,
    request: Request,
    runtime: RuntimeDependency,
    _same_origin: Annotated[None, Depends(require_same_origin)],
) -> JSONResponse:
    if "bootstrap_secret" in request.query_params:
        raise AuthorizationError("bootstrap_operator_authorization_failed")
    if runtime.settings.is_production:
        supplied = payload.bootstrap_secret or ""
        expected = runtime.settings.bootstrap_secret or ""
        if not expected or not hmac.compare_digest(supplied, expected):
            raise AuthorizationError("bootstrap_operator_authorization_failed")
    if payload.person_ids and not payload.confirm_full_owner_access:
        raise ConfirmationRequiredError("owner_confirmation_required")
    actor = runtime.service.bootstrap(
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
        person_ids=payload.person_ids,
        own_person_id=payload.own_person_id,
        confirm_full_owner_access=payload.confirm_full_owner_access,
    )
    credential_id = runtime.service.get_active_credential_id(actor.actor_id)
    if credential_id is None:
        raise AuthenticationError("active credential is unavailable")
    return _session_json_response(
        request,
        runtime,
        actor,
        credential_id,
        status_code=201,
        extra={
            "installation_admin": True,
            "owner_assignment_count": len(payload.person_ids),
            "owner_assignments": [
                {
                    "person_id": person_id,
                    "role": "owner",
                    "scopes": sorted(OWNER_SCOPES),
                }
                for person_id in payload.person_ids
            ],
        },
    )


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    runtime: RuntimeDependency,
    _same_origin: Annotated[None, Depends(require_same_origin)],
) -> JSONResponse:
    authenticated = runtime.service.authenticate_for_session(payload.username, payload.password)
    if authenticated is None:
        raise AuthenticationError("invalid credential")
    return _session_json_response(
        request,
        runtime,
        authenticated.actor,
        authenticated.credential_id,
        status_code=200,
    )


@router.post("/logout", status_code=204)
def logout(
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
    _payload: EmptyRequest | None = None,
) -> Response:
    runtime.sessions.revoke(authenticated.session_token)
    response = Response(status_code=204)
    _clear_session_cookies(response)
    return response


@router.get("/me")
def me(authenticated: AuthenticatedDependency) -> dict[str, object]:
    return {
        "actor": _actor_payload(authenticated.actor),
        "active_person_id": authenticated.record.active_person_id,
    }


@router.post("/password:change", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> Response:
    runtime.service.change_password(
        authenticated.actor.actor_id,
        payload.current_password,
        payload.new_password,
    )
    response = Response(status_code=204)
    _clear_session_cookies(response)
    return response


@router.put("/active-person", status_code=204)
def set_active_person(
    payload: ActivePersonRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> Response:
    if payload.person_id is not None:
        runtime.service.require_person_access(
            authenticated.actor.actor_id, payload.person_id, "person.read"
        )
    runtime.sessions.set_active_person(authenticated.session_token, payload.person_id)
    return Response(status_code=204)


@router.get("/actors")
def list_actors(
    runtime: RuntimeDependency, authenticated: AuthenticatedDependency
) -> dict[str, object]:
    return {
        "actors": [
            _actor_payload(actor)
            for actor in runtime.service.list_actors(authenticated.actor.actor_id)
        ]
    }


@router.post("/actors/{actor_id}:deactivate", status_code=204)
def deactivate_actor(
    actor_id: str,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
    _payload: EmptyRequest | None = None,
) -> Response:
    runtime.service.deactivate_actor(authenticated.actor.actor_id, actor_id)
    response = Response(status_code=204)
    if actor_id == authenticated.actor.actor_id:
        _clear_session_cookies(response)
    return response


@router.post("/people", status_code=201)
def create_person(
    payload: PersonCreateRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, object]:
    person_id = runtime.service.create_person(
        authenticated.actor.actor_id,
        display_name=payload.display_name,
        date_of_birth=payload.date_of_birth,
        confirm_owner_assignment=payload.confirm_owner_assignment,
        link_as_own=payload.link_as_own,
    )
    return {"person_id": person_id, "role": "owner", "scopes": sorted(OWNER_SCOPES)}


@router.post("/families", status_code=201)
def create_family(
    payload: FamilyCreateRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, object]:
    return asdict(runtime.service.create_family(authenticated.actor.actor_id, payload.display_name))


@router.get("/families")
def list_families(
    runtime: RuntimeDependency, authenticated: AuthenticatedDependency
) -> dict[str, object]:
    return {
        "families": [
            asdict(item) for item in runtime.service.list_families(authenticated.actor.actor_id)
        ]
    }


@router.get("/families/{family_id}")
def get_family(
    family_id: str,
    runtime: RuntimeDependency,
    authenticated: AuthenticatedDependency,
) -> dict[str, object]:
    return runtime.service.get_family(authenticated.actor.actor_id, family_id)


@router.post("/families/{family_id}:archive", status_code=204)
def archive_family(
    family_id: str,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
    _payload: EmptyRequest | None = None,
) -> Response:
    runtime.service.archive_family(authenticated.actor.actor_id, family_id)
    return Response(status_code=204)


@router.post("/families/{family_id}/memberships", status_code=201)
def add_membership(
    family_id: str,
    payload: MembershipCreateRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, object]:
    return asdict(
        runtime.service.add_membership(authenticated.actor.actor_id, family_id, payload.person_id)
    )


@router.post("/families/{family_id}/memberships/{membership_id}:end", status_code=204)
def end_membership(
    family_id: str,
    membership_id: str,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
    _payload: EmptyRequest | None = None,
) -> Response:
    runtime.service.end_membership(authenticated.actor.actor_id, family_id, membership_id)
    return Response(status_code=204)


@router.post("/families/{family_id}/relationships", status_code=201)
def create_relationship(
    family_id: str,
    payload: RelationshipCreateRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, object]:
    return asdict(
        runtime.service.create_relationship(
            authenticated.actor.actor_id,
            family_id,
            person_id=payload.person_id,
            related_person_id=payload.related_person_id,
            relationship_type=payload.relationship_type,
        )
    )


@router.post("/families/{family_id}/relationships/{relationship_id}:end", status_code=204)
def end_relationship(
    family_id: str,
    relationship_id: str,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
    _payload: EmptyRequest | None = None,
) -> Response:
    runtime.service.end_relationship(authenticated.actor.actor_id, family_id, relationship_id)
    return Response(status_code=204)


@router.get("/people/{person_id}/access-assignments")
def list_assignments(
    person_id: str,
    runtime: RuntimeDependency,
    authenticated: AuthenticatedDependency,
) -> dict[str, object]:
    return {
        "assignments": runtime.service.list_assignments(authenticated.actor.actor_id, person_id)
    }


@router.post("/people/{person_id}/access-assignments", status_code=201)
def grant_assignment(
    person_id: str,
    payload: AssignmentCreateRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, Any]:
    return asdict(
        runtime.service.grant_assignment(
            authenticated.actor.actor_id,
            person_id,
            payload.recipient_actor_id,
            role=payload.role,
            optional_scopes=payload.optional_scopes,
            confirm_full_owner_access=payload.confirm_full_owner_access,
        )
    )


@router.post("/people/{person_id}/access-assignments/{assignment_id}:revise", status_code=201)
def revise_assignment(
    person_id: str,
    assignment_id: str,
    payload: AssignmentReviseRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, Any]:
    return asdict(
        runtime.service.revise_assignment(
            authenticated.actor.actor_id,
            person_id,
            assignment_id,
            payload.optional_scopes,
            policy_generation=payload.policy_generation,
        )
    )


@router.post(
    "/people/{person_id}/access-assignments/{assignment_id}:upgrade-generation",
    status_code=200,
)
def upgrade_assignment_generation(
    person_id: str,
    assignment_id: str,
    payload: AssignmentUpgradeRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, Any]:
    return asdict(
        runtime.service.upgrade_owner_generation(
            authenticated.actor.actor_id,
            person_id,
            assignment_id,
            confirm_full_owner_access=payload.confirm_full_owner_access,
        )
    )


@router.post("/people/{person_id}/access-assignments/{assignment_id}:revoke", status_code=204)
def revoke_assignment(
    person_id: str,
    assignment_id: str,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
    _payload: EmptyRequest | None = None,
) -> Response:
    runtime.service.revoke_assignment(authenticated.actor.actor_id, person_id, assignment_id)
    return Response(status_code=204)


@router.get("/people/{person_id}/consents")
def list_consents(
    person_id: str,
    runtime: RuntimeDependency,
    authenticated: AuthenticatedDependency,
) -> dict[str, object]:
    return {"consents": runtime.service.list_consents(authenticated.actor.actor_id, person_id)}


@router.get("/people/{person_id}/access-audit")
def list_access_audit(
    person_id: str,
    runtime: RuntimeDependency,
    authenticated: AuthenticatedDependency,
) -> dict[str, object]:
    return {"audit_events": runtime.service.list_audits(authenticated.actor.actor_id, person_id)}


@router.post("/people/{person_id}/invitations", status_code=201)
def create_invitation(
    person_id: str,
    payload: InvitationCreateRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, Any]:
    return asdict(
        runtime.service.create_invitation(
            authenticated.actor.actor_id,
            person_id,
            role=payload.role,
            optional_scopes=payload.optional_scopes,
            expires_at=payload.expires_at,
            confirm_full_owner_access=payload.confirm_full_owner_access,
        )
    )


@router.post("/people/{person_id}/invitations/{invitation_id}:revoke", status_code=204)
def revoke_invitation(
    person_id: str,
    invitation_id: str,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
    _payload: EmptyRequest | None = None,
) -> Response:
    runtime.service.revoke_invitation(authenticated.actor.actor_id, person_id, invitation_id)
    return Response(status_code=204)


@router.post("/invite/preview")
def preview_invitation(
    payload: InvitationSecretRequest,
    runtime: RuntimeDependency,
    _same_origin: Annotated[None, Depends(require_same_origin)],
) -> dict[str, Any]:
    preview = runtime.service.preview_invitation(payload.secret)
    return {
        "role": preview.role,
        "scopes": sorted(preview.scopes),
        "expires_at": preview.expires_at,
    }


@router.post("/invite/register", status_code=201)
def register_invitation(
    payload: InvitationRegisterRequest,
    request: Request,
    runtime: RuntimeDependency,
    _same_origin: Annotated[None, Depends(require_same_origin)],
) -> JSONResponse:
    actor = runtime.service.register_invitation(
        payload.secret,
        username=payload.username,
        display_name=payload.display_name,
        password=payload.password,
        confirm_full_owner_access=payload.confirm_full_owner_access,
    )
    credential_id = runtime.service.get_active_credential_id(actor.actor_id)
    if credential_id is None:
        raise AuthenticationError("active credential is unavailable")
    return _session_json_response(request, runtime, actor, credential_id, status_code=201)


@router.post("/invite/accept", status_code=201)
def accept_invitation(
    payload: InvitationAcceptRequest,
    runtime: RuntimeDependency,
    authenticated: UnsafeAuthenticatedDependency,
) -> dict[str, Any]:
    return asdict(
        runtime.service.accept_invitation(
            authenticated.actor.actor_id,
            payload.secret,
            confirm_full_owner_access=payload.confirm_full_owner_access,
        )
    )
