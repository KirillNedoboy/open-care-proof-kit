from __future__ import annotations

import base64
import json
import sqlite3
from collections.abc import Callable
from contextlib import suppress
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BeforeValidator

from app.family_access.api import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, AuthenticatedSession
from app.family_access.runtime import FamilyAccessRuntime
from app.http_security import is_same_origin
from app.product_core.access import ProductCoreAccess
from app.product_core.api_models import (
    CandidateListResponse,
    CandidateResponse,
    CandidateStatus,
    CanonicalMedicationListResponse,
    CanonicalMedicationResponse,
    ConditionCandidateListResponse,
    ConditionCandidateRequest,
    ConditionCandidateResponse,
    ConditionCorrectRequest,
    ConditionRecordListResponse,
    ConditionRecordResponse,
    CorrectCandidateRequest,
    DocumentExtractionResponse,
    DocumentListResponse,
    DocumentPageResponse,
    DocumentRegistrationResponse,
    DocumentResponse,
    EmptyActionRequest,
    ErrorResponse,
    GeneticsComparisonRequest,
    GeneticsConsentRequest,
    GeneticsExportRequest,
    GeneticsGrantRequest,
    GeneticsImportRequest,
    GeneticsResearchRequest,
    GeneticsReviewRequest,
    LabCandidateListResponse,
    LabCandidateRequest,
    LabCandidateResponse,
    LabCorrectRequest,
    LabRecordListResponse,
    LabRecordResponse,
    ManualConditionSourceRequest,
    ManualLabSourceRequest,
    ManualSourceRequest,
    MedicationCandidateRequest,
    PeopleListResponse,
    PersonCreateRequest,
    PersonResponse,
    PersonUpdateRequest,
    PlainTextSourceRequest,
    SourceMetadataResponse,
    SourceRegistrationResponse,
    SourceResponse,
    TimelineEventResponse,
    TimelineResponse,
    VisitBriefEligibleEvidenceResponse,
    VisitBriefEvidenceRequest,
    VisitBriefEvidenceValidationResponse,
    VisitBriefGenerateRequest,
    VisitBriefGenerateRevisionRequest,
    VisitBriefInitializeResponse,
    VisitBriefResponse,
    VisitBriefResponseV2,
    VisitBriefRestoreRequest,
    VisitBriefRevisionListResponse,
    VisitBriefRevisionResponse,
    VisitBriefStalenessResponse,
    VisitBriefUserEditRequest,
    VisitCreateRequest,
    VisitListResponse,
    VisitQuestionCreateRequest,
    VisitQuestionListResponse,
    VisitQuestionResponse,
    VisitQuestionUpdateRequest,
    VisitResponse,
    VisitUpdateRequest,
    WorkspaceCapabilities,
    WorkspaceCapabilitiesResponse,
    _validate_identifier,
)
from app.product_core.errors import (
    AccessAuditUnavailableError,
    CandidateNotFoundError,
    CanonicalRecordNotFoundError,
    DocumentValidationError,
    IntegrityStorageError,
    InvalidTransitionError,
    NotFoundError,
    PersonMismatchError,
    PersonNotFoundError,
    PersonValidationError,
    ProductCoreError,
    ProvenanceValidationError,
    RuntimeNotReadyError,
    ScopeForbiddenError,
    SelectionError,
    SourceCorruptionError,
    SourceNotFoundError,
    SourcePublicationError,
    UnsafeSourcePathError,
    VisitBriefAlreadyExistsError,
    VisitBriefConflictError,
    VisitBriefNotFoundError,
    VisitBriefRevisionNotFoundError,
    VisitBriefValidationError,
    VisitNotFoundError,
    VisitQuestionNotFoundError,
    VisitValidationError,
)
from app.product_core.genetics import MAX_GENETICS_UPLOAD_BYTES, GeneticsValidationError
from app.product_core.models import ConditionCandidateInput, LabCandidateInput, VisitBriefRequest
from app.product_core.portable_vault_export import PORTABLE_VAULT_FORMAT_VERSION
from app.product_core.runtime import ProductCoreRuntime
from app.product_core.services import MAX_DOCUMENT_PAGES, MAX_DOCUMENT_UPLOAD_BYTES

ProductCoreIdentifier = Annotated[
    str,
    Path(min_length=1, max_length=128),
    BeforeValidator(_validate_identifier),
]


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(payload, status_code=status_code)


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in exc.errors():
        details.append(
            {
                "loc": [str(item) for item in error.get("loc", ())],
                "code": str(error.get("type", "validation_error")),
            }
        )
    return details


def _map_product_core_error(exc: ProductCoreError) -> JSONResponse:
    if isinstance(exc, GeneticsValidationError):
        return _error_response(
            422,
            "genetics_validation_failed",
            "The genetics request is invalid.",
        )
    if isinstance(exc, ScopeForbiddenError):
        return _error_response(403, "scope_forbidden", "Required scope is not granted.")
    if isinstance(exc, AccessAuditUnavailableError):
        return _error_response(
            503,
            "access_audit_unavailable",
            "Sensitive access could not be audited.",
        )
    if isinstance(exc, DocumentValidationError):
        status_code = {
            "upload_bytes_limit_exceeded": 413,
            "content_length_exceeded": 413,
            "unsupported_media_type": 415,
            "pdf_signature_invalid": 415,
            "content_length_required": 411,
        }.get(exc.reason_code, 422)
        return _error_response(
            status_code,
            exc.reason_code,
            "The document could not be accepted.",
        )
    if isinstance(exc, PersonValidationError):
        return _error_response(422, "request_validation_failed", "The request is invalid.")
    if isinstance(exc, VisitValidationError):
        return _error_response(422, "request_validation_failed", "The request is invalid.")
    if isinstance(exc, VisitBriefValidationError):
        return _error_response(422, "request_validation_failed", "The request is invalid.")
    if isinstance(exc, PersonNotFoundError):
        return _error_response(404, "person_not_found", "Person was not found.")
    if isinstance(exc, VisitNotFoundError):
        return _error_response(404, "visit_not_found", "Visit was not found.")
    if isinstance(exc, VisitQuestionNotFoundError):
        return _error_response(404, "visit_question_not_found", "Visit question was not found.")
    if isinstance(exc, VisitBriefNotFoundError):
        return _error_response(404, "visit_brief_not_found", "Visit Brief was not found.")
    if isinstance(exc, VisitBriefRevisionNotFoundError):
        return _error_response(
            404, "visit_brief_revision_not_found", "Visit Brief revision was not found."
        )
    if isinstance(exc, VisitBriefAlreadyExistsError):
        return _error_response(409, "visit_brief_already_exists", "Visit Brief already exists.")
    if isinstance(exc, VisitBriefConflictError):
        return _error_response(409, "visit_brief_conflict", "Visit Brief changed.")
    if isinstance(exc, SourceNotFoundError):
        return _error_response(404, "source_not_found", "Source was not found.")
    if isinstance(exc, CandidateNotFoundError):
        return _error_response(404, "candidate_not_found", "Candidate was not found.")
    if isinstance(exc, CanonicalRecordNotFoundError):
        return _error_response(
            404,
            "canonical_record_not_found",
            "Canonical medication record was not found.",
        )
    if isinstance(exc, NotFoundError):
        return _error_response(404, "product_core_record_not_found", "Record was not found.")
    if isinstance(exc, InvalidTransitionError):
        return _error_response(
            409,
            "invalid_lifecycle_transition",
            "The candidate cannot make that transition.",
        )
    if isinstance(exc, PersonMismatchError):
        return _error_response(
            409,
            "person_mismatch",
            "Related records belong to different people.",
        )
    if isinstance(exc, ProvenanceValidationError):
        return _error_response(
            422,
            "provenance_validation_failed",
            "The provenance locator is missing, malformed, or does not match the source.",
        )
    if isinstance(exc, SelectionError):
        return _error_response(422, "invalid_visit_brief_selection", "The selection is invalid.")
    if isinstance(exc, (SourceCorruptionError, UnsafeSourcePathError, IntegrityStorageError)):
        return _error_response(
            500,
            "product_core_integrity_failure",
            "Product Core integrity failed.",
        )
    if isinstance(exc, (SourcePublicationError, RuntimeNotReadyError)):
        return _error_response(
            503,
            "product_core_storage_unavailable",
            "Product Core storage is unavailable.",
        )
    return _error_response(
        500,
        "product_core_failure",
        "Product Core could not complete the request.",
    )


async def _check_request_safety(request: Request, operation_id: str) -> JSONResponse | None:
    if request.method in {"POST", "PUT", "PATCH"}:
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if operation_id == "product_core_register_document":
            if media_type not in {"application/pdf", "text/plain"}:
                return _error_response(
                    415,
                    "unsupported_document_media_type",
                    "Only PDF and plain-text documents are supported.",
                )
        elif media_type != "application/json":
            return _error_response(
                415,
                "json_content_type_required",
                "JSON content type is required.",
            )
    return None


_PERSON_PATH_SCOPES: dict[str, tuple[str, ...]] = {
    "product_core_get_person": ("person.read",),
    "product_core_update_person": ("person.update",),
    "product_core_list_visits": ("visit.read",),
    "product_core_list_candidates": ("candidate.read",),
    "product_core_list_medications": ("medication.read",),
    "product_core_list_conditions": ("condition.read",),
    "product_core_list_condition_candidates": ("condition.read",),
    "product_core_list_labs": ("lab.read",),
    "product_core_list_lab_candidates": ("lab.read",),
    "product_core_list_timeline": ("timeline.read",),
    "product_core_generate_visit_brief": ("brief.write",),
    "product_core_list_documents": ("document.read",),
    "product_core_get_document": ("document.read",),
    "product_core_get_document_page": ("document.read",),
    "product_core_register_document": ("source.write", "document.write"),
}
_VISIT_PATH_SCOPES: dict[str, tuple[str, ...]] = {
    "product_core_get_visit": ("visit.read",),
    "product_core_update_visit": ("visit.write",),
    "product_core_create_visit_question": ("visit.write",),
    "product_core_list_visit_questions": ("visit.read",),
    "product_core_initialize_persisted_visit_brief": ("brief.write",),
    "product_core_get_persisted_visit_brief": ("brief.read",),
    "product_core_list_persisted_visit_brief_revisions": ("brief.read",),
    "product_core_get_persisted_visit_brief_revision": ("brief.read",),
    "product_core_list_visit_brief_eligible_evidence": ("brief.read",),
    "product_core_validate_visit_brief_evidence": ("brief.write",),
    "product_core_generate_persisted_visit_brief_revision": ("brief.write",),
    "product_core_save_persisted_visit_brief_user_edit": ("brief.write",),
    "product_core_restore_persisted_visit_brief_revision": ("brief.write",),
}
_QUESTION_PATH_SCOPES: dict[str, tuple[str, ...]] = {
    "product_core_update_visit_question": ("visit.write",),
    "product_core_delete_visit_question": ("visit.write",),
}
_CANDIDATE_PATH_SCOPES: dict[str, tuple[str, ...]] = {
    "product_core_get_candidate": ("candidate.read",),
    "product_core_reject_candidate": ("candidate.review",),
    "product_core_unsupported_candidate": ("candidate.review",),
    "product_core_correct_candidate": ("candidate.review",),
    "product_core_correct_condition_candidate": ("candidate.review",),
    "product_core_correct_lab_candidate": ("candidate.review",),
}
_CONDITION_PATH_SCOPES: dict[str, tuple[str, ...]] = {
    "product_core_get_condition_record": ("condition.read",),
    "product_core_get_condition_candidate": ("condition.read",),
}
_LAB_PATH_SCOPES: dict[str, tuple[str, ...]] = {
    "product_core_get_lab_record": ("lab.read",),
    "product_core_get_lab_candidate": ("lab.read",),
}
_BODY_PERSON_SCOPES: dict[str, tuple[str, ...]] = {
    "product_core_create_visit": ("visit.write",),
    "product_core_register_manual_medication_source": ("source.write",),
    "product_core_register_manual_condition_source": ("source.write",),
    "product_core_register_manual_lab_source": ("source.write",),
    "product_core_register_plain_text_source": ("source.write",),
    "product_core_create_medication_candidate": ("candidate.review",),
    "product_core_create_condition_candidate": ("candidate.review",),
    "product_core_create_lab_candidate": ("candidate.review",),
}

_GENETICS_OPERATIONS = {
    "product_core_get_genetics_workspace": "genetics.read",
    "product_core_consent_genetics": "person.read",
    "product_core_grant_genetics_access": "access.manage",
    "product_core_import_genetics": "genetics.write",
    "product_core_review_genetics_finding": "genetics.read",
    "product_core_run_genetics_research": "genetics.research",
    "product_core_compare_genetics": "genetics.compare",
    "product_core_export_genetics": "genetics.export",
}
_CANDIDATE_CREATE_OPERATIONS = frozenset(
    {
        "product_core_create_medication_candidate",
        "product_core_create_condition_candidate",
        "product_core_create_lab_candidate",
    }
)
_ATOMIC_MUTATION_OPERATIONS = {
    "product_core_update_person",
    "product_core_create_visit",
    "product_core_update_visit",
    "product_core_create_visit_question",
    "product_core_update_visit_question",
    "product_core_delete_visit_question",
    "product_core_register_manual_medication_source",
    "product_core_register_manual_condition_source",
    "product_core_register_manual_lab_source",
    "product_core_register_plain_text_source",
    "product_core_register_document",
    "product_core_create_medication_candidate",
    "product_core_create_condition_candidate",
    "product_core_create_lab_candidate",
    "product_core_confirm_candidate",
    "product_core_reject_candidate",
    "product_core_unsupported_candidate",
    "product_core_correct_candidate",
    "product_core_correct_condition_candidate",
    "product_core_correct_lab_candidate",
    "product_core_initialize_persisted_visit_brief",
    "product_core_generate_persisted_visit_brief_revision",
    "product_core_save_persisted_visit_brief_user_edit",
    "product_core_restore_persisted_visit_brief_revision",
    "product_core_export_current_persisted_visit_brief",
    "product_core_consent_genetics",
    "product_core_grant_genetics_access",
    "product_core_import_genetics",
    "product_core_review_genetics_finding",
    "product_core_run_genetics_research",
    "product_core_export_genetics",
}


async def _authorize_route_request(
    request: Request, operation_id: str, access: ProductCoreAccess
) -> None:
    # Preflight path resources before request-model validation to preserve 404
    # privacy semantics. The authoritative recheck and success audit still run
    # inside the same Product Core write transaction as the mutation.
    if operation_id in _GENETICS_OPERATIONS:
        person_id = request.path_params.get("person_id")
        if isinstance(person_id, str):
            scope = _GENETICS_OPERATIONS[operation_id]
            if scope in {"person.read", "access.manage"}:
                access.require_person(person_id, scope)
            else:
                access.require_genetics(person_id, scope)
        return
    if operation_id in _ATOMIC_MUTATION_OPERATIONS:
        if operation_id in _PERSON_PATH_SCOPES:
            access.preflight_person(
                str(request.path_params["person_id"]),
                *_PERSON_PATH_SCOPES[operation_id],
            )
            return
        if operation_id in _VISIT_PATH_SCOPES:
            access.preflight_visit(
                str(request.path_params["visit_id"]),
                *_VISIT_PATH_SCOPES[operation_id],
            )
            return
        if operation_id == "product_core_export_current_persisted_visit_brief":
            access.preflight_visit(str(request.path_params["visit_id"]), "brief.export")
            return
        if operation_id in _QUESTION_PATH_SCOPES:
            access.preflight_question(
                str(request.path_params["question_id"]),
                *_QUESTION_PATH_SCOPES[operation_id],
            )
            return
        if operation_id in {
            "product_core_confirm_candidate",
            "product_core_correct_candidate",
            "product_core_correct_condition_candidate",
            "product_core_correct_lab_candidate",
        }:
            access.preflight_candidate_review(
                str(request.path_params["candidate_id"]),
            )
            return
        if operation_id in _CANDIDATE_PATH_SCOPES:
            access.preflight_candidate(
                str(request.path_params["candidate_id"]),
                *_CANDIDATE_PATH_SCOPES[operation_id],
            )
            return
        try:
            payload = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("person_id"), str):
            return
        person_id = payload["person_id"]
        try:
            _validate_identifier(person_id)
        except ValueError:
            return
        access.preflight_person(person_id, *_BODY_PERSON_SCOPES[operation_id])
        if operation_id in _CANDIDATE_CREATE_OPERATIONS and isinstance(
            payload.get("source_id"), str
        ):
            try:
                _validate_identifier(payload["source_id"])
            except ValueError:
                return
            access.preflight_source_for_person(payload["source_id"], person_id, "source.read")
        return
    if operation_id in _PERSON_PATH_SCOPES:
        access.require_person(
            str(request.path_params["person_id"]), *_PERSON_PATH_SCOPES[operation_id]
        )
        return
    if operation_id == "product_core_export_person_portable_vault":
        access.require_person(
            str(request.path_params["person_id"]),
            "vault.export",
            audit_action="vault.export",
            required_audit=True,
        )
        return
    if operation_id in _VISIT_PATH_SCOPES:
        access.require_visit(
            str(request.path_params["visit_id"]), *_VISIT_PATH_SCOPES[operation_id]
        )
        return
    if operation_id == "product_core_export_current_persisted_visit_brief":
        access.require_brief_export(str(request.path_params["visit_id"]))
        return
    if operation_id in _QUESTION_PATH_SCOPES:
        access.require_question(
            str(request.path_params["question_id"]), *_QUESTION_PATH_SCOPES[operation_id]
        )
        return
    if operation_id in _CANDIDATE_PATH_SCOPES:
        access.require_candidate(
            str(request.path_params["candidate_id"]), *_CANDIDATE_PATH_SCOPES[operation_id]
        )
        return
    if operation_id in _CONDITION_PATH_SCOPES:
        if operation_id == "product_core_get_condition_candidate":
            access.require_condition_candidate(
                str(request.path_params["candidate_id"]),
                *_CONDITION_PATH_SCOPES[operation_id],
            )
        else:
            access.require_condition_record(
                str(request.path_params["record_id"]),
                *_CONDITION_PATH_SCOPES[operation_id],
            )
        return
    if operation_id in _LAB_PATH_SCOPES:
        if operation_id == "product_core_get_lab_candidate":
            access.require_lab_candidate(
                str(request.path_params["candidate_id"]),
                *_LAB_PATH_SCOPES[operation_id],
            )
        else:
            access.require_lab_record(
                str(request.path_params["record_id"]),
                *_LAB_PATH_SCOPES[operation_id],
            )
        return
    if operation_id not in _BODY_PERSON_SCOPES:
        return
    try:
        payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return
    if not isinstance(payload, dict) or not isinstance(payload.get("person_id"), str):
        return
    person_id = payload["person_id"]
    try:
        _validate_identifier(person_id)
    except ValueError:
        return
    access.require_person(person_id, *_BODY_PERSON_SCOPES[operation_id])
    if operation_id in _CANDIDATE_CREATE_OPERATIONS and isinstance(payload.get("source_id"), str):
        try:
            _validate_identifier(payload["source_id"])
        except ValueError:
            return
        access.require_source_for_person(payload["source_id"], person_id, "source.read")


def resolve_product_core_access(request: Request) -> ProductCoreAccess | JSONResponse:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        return _error_response(401, "authentication_required", "Authentication required.")
    product_runtime = getattr(request.app.state, "product_core_runtime", None)
    family_runtime = getattr(request.app.state, "family_access_runtime", None)
    if not isinstance(product_runtime, ProductCoreRuntime) or not isinstance(
        family_runtime, FamilyAccessRuntime
    ):
        return _error_response(
            503, "product_core_storage_unavailable", "Product Core storage is unavailable."
        )
    record = family_runtime.sessions.resolve(token)
    if record is None:
        return _error_response(401, "authentication_required", "Authentication required.")
    actor = family_runtime.service.get_actor_for_session(record.actor_id, record.credential_id)
    if actor is None:
        with suppress(Exception):
            family_runtime.sessions.revoke(token)
        return _error_response(401, "authentication_required", "Authentication required.")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("origin") is None or not is_same_origin(request):
            return _error_response(403, "origin_rejected", "The request origin is not allowed.")
        csrf_token = request.headers.get(CSRF_HEADER_NAME)
        if csrf_token is None or not family_runtime.sessions.verify_csrf(token, csrf_token):
            return _error_response(403, "csrf_rejected", "CSRF validation failed.")
    return ProductCoreAccess(
        runtime=product_runtime,
        family_runtime=family_runtime,
        authenticated=AuthenticatedSession(actor=actor, record=record, session_token=token),
    )


class ProductCoreRoute(APIRoute):
    def get_route_handler(self) -> Callable[..., Any]:
        original_route_handler = super().get_route_handler()

        async def product_core_route_handler(request: Request) -> Any:
            try:
                access = resolve_product_core_access(request)
                if isinstance(access, JSONResponse):
                    return access
                request.state.product_core_access = access
                safety_response = await _check_request_safety(request, self.operation_id or "")
                if safety_response is not None:
                    return safety_response
                await _authorize_route_request(request, self.operation_id or "", access)
                return await original_route_handler(request)
            except RequestValidationError as exc:
                return _error_response(
                    422,
                    "request_validation_failed",
                    "The request is invalid.",
                    _validation_details(exc),
                )
            except ProductCoreError as exc:
                if self.operation_id in _ATOMIC_MUTATION_OPERATIONS and isinstance(
                    exc, (NotFoundError, ScopeForbiddenError)
                ):
                    resolved_access = getattr(request.state, "product_core_access", None)
                    if isinstance(resolved_access, ProductCoreAccess):
                        resolved_access.audit_denial_best_effort()
                return _map_product_core_error(exc)
            except sqlite3.OperationalError:
                return _error_response(
                    503,
                    "product_core_storage_unavailable",
                    "Product Core storage is unavailable.",
                )
            except sqlite3.IntegrityError:
                return _error_response(
                    500,
                    "product_core_integrity_failure",
                    "Product Core integrity failed.",
                )
            except OSError:
                return _error_response(
                    503,
                    "product_core_storage_unavailable",
                    "Product Core storage is unavailable.",
                )

        return product_core_route_handler


router = APIRouter(
    prefix="/api/product-core/v1",
    route_class=ProductCoreRoute,
    tags=["Product Core"],
)


def get_product_core_runtime(request: Request) -> ProductCoreRuntime:
    runtime = getattr(request.app.state, "product_core_runtime", None)
    if not isinstance(runtime, ProductCoreRuntime):
        raise RuntimeNotReadyError("Product Core runtime is not ready")
    return runtime


RuntimeDependency = Annotated[ProductCoreRuntime, Depends(get_product_core_runtime)]


def get_product_core_access(request: Request) -> ProductCoreAccess:
    access = getattr(request.state, "product_core_access", None)
    if not isinstance(access, ProductCoreAccess):
        raise RuntimeNotReadyError("Product Core access is not ready")
    return access


AccessDependency = Annotated[ProductCoreAccess, Depends(get_product_core_access)]


async def _read_bounded_document_body(request: Request) -> bytes:
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        raise DocumentValidationError("content_length_required")
    if not raw_length.isdecimal():
        raise DocumentValidationError("content_length_invalid")
    declared_length = int(raw_length)
    if declared_length > MAX_DOCUMENT_UPLOAD_BYTES:
        raise DocumentValidationError("upload_bytes_limit_exceeded")
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_DOCUMENT_UPLOAD_BYTES:
            raise DocumentValidationError("upload_bytes_limit_exceeded")
        payload.extend(chunk)
    if len(payload) != declared_length:
        raise DocumentValidationError("content_length_mismatch")
    return bytes(payload)


def _document_response(source: Any, extraction: Any) -> DocumentResponse:
    return DocumentResponse(
        source_id=source.id,
        person_id=source.person_id,
        source_type="document",
        media_type=source.media_type,
        content_hash=source.content_hash,
        size_bytes=source.size_bytes,
        original_filename=source.original_filename,
        document_kind=source.document_kind,
        created_at=source.created_at,
        extraction=DocumentExtractionResponse(
            extraction_id=extraction.extraction_id,
            extractor=extraction.extractor,
            extractor_version=extraction.extractor_version,
            status=extraction.status,
            text_hash=extraction.text_hash,
            total_chars=extraction.total_chars,
            page_count=extraction.page_count,
            extracted_at=extraction.extracted_at,
        ),
    )


def _source_response(source: Any) -> SourceResponse:
    return SourceResponse(
        source_id=source.id,
        person_id=source.person_id,
        source_type=source.source_type,
        content_hash=source.content_hash,
        size_bytes=source.size_bytes,
        media_type=source.media_type,
        created_at=source.created_at,
    )


def _person_response(person: Any) -> PersonResponse:
    return PersonResponse(
        person_id=person.person_id,
        display_name=person.display_name,
        date_of_birth=person.date_of_birth,
        created_at=person.created_at,
        updated_at=person.updated_at,
        is_active=person.is_active,
    )


def _candidate_response(candidate: Any) -> CandidateResponse:
    return CandidateResponse(
        id=candidate.id,
        person_id=candidate.person_id,
        source_id=candidate.source_id,
        fact_type=candidate.fact_type,
        status=candidate.status,
        display_name=candidate.display_name,
        schedule_text=candidate.schedule_text,
        note=candidate.note,
        created_at=candidate.created_at,
        reviewed_at=candidate.reviewed_at,
        predecessor_candidate_id=candidate.predecessor_candidate_id,
        provenance_locator=candidate.provenance_locator,
    )


def _canonical_response(record: Any) -> CanonicalMedicationResponse:
    return CanonicalMedicationResponse(
        id=record.id,
        person_id=record.person_id,
        candidate_id=record.candidate_id,
        source_id=record.source_id,
        fact_type=record.fact_type,
        display_name=record.display_name,
        schedule_text=record.schedule_text,
        note=record.note,
        confirmed_at=record.confirmed_at,
        is_active=record.is_active,
        superseded_by_record_id=record.superseded_by_record_id,
        provenance_locator=record.provenance_locator,
        predecessor_candidate_id=record.predecessor_candidate_id,
    )


def _condition_candidate_response(candidate: Any) -> ConditionCandidateResponse:
    return ConditionCandidateResponse(
        id=candidate.id,
        person_id=candidate.person_id,
        source_id=candidate.source_id,
        status=candidate.status,
        display_name=candidate.display_name,
        status_text=candidate.detail.status_text,
        onset_date=candidate.detail.onset_date,
        note=candidate.note,
        created_at=candidate.created_at,
        reviewed_at=candidate.reviewed_at,
        predecessor_candidate_id=candidate.predecessor_candidate_id,
        provenance_locator=candidate.provenance_locator,
    )


def _condition_record_response(record: Any) -> ConditionRecordResponse:
    return ConditionRecordResponse(
        id=record.id,
        person_id=record.person_id,
        candidate_id=record.candidate_id,
        source_id=record.source_id,
        display_name=record.display_name,
        status_text=record.detail.status_text,
        onset_date=record.detail.onset_date,
        note=record.note,
        confirmed_at=record.confirmed_at,
        is_active=record.is_active,
        superseded_by_record_id=record.superseded_by_record_id,
        provenance_locator=record.provenance_locator,
        predecessor_candidate_id=record.predecessor_candidate_id,
    )


def _lab_candidate_response(candidate: Any) -> LabCandidateResponse:
    return LabCandidateResponse(
        id=candidate.id,
        person_id=candidate.person_id,
        source_id=candidate.source_id,
        status=candidate.status,
        test_name=candidate.detail.test_name,
        result_text=candidate.detail.result_text,
        unit_text=candidate.detail.unit_text,
        reference_range_text=candidate.detail.reference_range_text,
        observed_date=candidate.detail.observed_date,
        source_flag_text=candidate.detail.source_flag_text,
        note=candidate.note,
        created_at=candidate.created_at,
        reviewed_at=candidate.reviewed_at,
        predecessor_candidate_id=candidate.predecessor_candidate_id,
        provenance_locator=candidate.provenance_locator,
    )


def _lab_record_response(record: Any) -> LabRecordResponse:
    return LabRecordResponse(
        id=record.id,
        person_id=record.person_id,
        candidate_id=record.candidate_id,
        source_id=record.source_id,
        test_name=record.detail.test_name,
        result_text=record.detail.result_text,
        unit_text=record.detail.unit_text,
        reference_range_text=record.detail.reference_range_text,
        observed_date=record.detail.observed_date,
        source_flag_text=record.detail.source_flag_text,
        note=record.note,
        confirmed_at=record.confirmed_at,
        is_active=record.is_active,
        superseded_by_record_id=record.superseded_by_record_id,
        provenance_locator=record.provenance_locator,
        predecessor_candidate_id=record.predecessor_candidate_id,
    )


def _timeline_response(event: Any) -> TimelineEventResponse:
    return TimelineEventResponse(
        id=event.id,
        person_id=event.person_id,
        canonical_record_id=event.canonical_record_id,
        source_id=event.source_id,
        fact_type=event.fact_type,
        event_type=event.event_type,
        event_at=event.event_at,
        title=event.title,
    )


def _visit_response(visit: Any) -> VisitResponse:
    return VisitResponse(
        visit_id=visit.visit_id,
        person_id=visit.person_id,
        title=visit.title,
        specialist=visit.specialist,
        scheduled_date=visit.scheduled_date,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
    )


def _visit_question_response(question: Any) -> VisitQuestionResponse:
    return VisitQuestionResponse(
        question_id=question.question_id,
        visit_id=question.visit_id,
        question_text=question.question_text,
        position=question.position,
        created_at=question.created_at,
        updated_at=question.updated_at,
    )


def _persisted_revision_response(
    runtime: ProductCoreRuntime,
    visit_id: str,
    revision: Any,
) -> VisitBriefRevisionResponse:
    parent_revision_number: int | None = None
    if revision.parent_revision_id is not None:
        with runtime.database.uow() as uow:
            parent = uow.visit_brief_revisions.get(revision.parent_revision_id)
        parent_revision_number = None if parent is None else parent.revision_number
    staleness = runtime.persisted_visit_briefs.staleness(visit_id, revision.revision_number)
    return VisitBriefRevisionResponse(
        revision_number=revision.revision_number,
        origin=revision.origin,
        parent_revision_number=parent_revision_number,
        content_schema_version=revision.content_schema_version,
        render_version=revision.render_version,
        created_at=revision.created_at,
        content=revision.content,
        markdown=revision.rendered_markdown,
        staleness=VisitBriefStalenessResponse(
            state=staleness.state,
            reasons=staleness.reasons,
        ),
    )


def _persisted_brief_response(
    runtime: ProductCoreRuntime,
    visit_id: str,
    brief: Any,
) -> VisitBriefResponseV2:
    current_revision = (
        None
        if brief.current_revision_number is None
        else _persisted_revision_response(
            runtime,
            visit_id,
            runtime.persisted_visit_briefs.get_revision(visit_id, brief.current_revision_number),
        )
    )
    return VisitBriefResponseV2(
        visit_id=visit_id,
        current_revision_number=brief.current_revision_number,
        created_at=brief.created_at,
        updated_at=brief.updated_at,
        current_revision=current_revision,
    )


@router.post(
    "/people",
    response_model=PersonResponse,
    responses={422: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_create_person",
)
def create_person(
    payload: PersonCreateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> PersonResponse:
    person_id = access.create_person(
        display_name=payload.display_name,
        date_of_birth=payload.date_of_birth,
        confirm_owner_assignment=payload.confirm_owner_assignment,
    )
    return _person_response(runtime.people.get(person_id))


@router.get(
    "/people",
    response_model=PeopleListResponse,
    operation_id="product_core_list_people",
)
def list_people(access: AccessDependency) -> PeopleListResponse:
    return PeopleListResponse(people=[_person_response(person) for person in access.list_people()])


@router.post(
    "/visits",
    response_model=VisitResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_create_visit",
)
def create_visit(
    payload: VisitCreateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitResponse:
    return _visit_response(
        runtime.visits.create_visit(
            payload.person_id,
            title=payload.title,
            specialist=payload.specialist,
            scheduled_date=payload.scheduled_date,
            authorize=access.authorize_person_mutation(
                payload.person_id, "visit.write", action="visit.create"
            ),
        )
    )


@router.get(
    "/people/{person_id}/visits",
    response_model=VisitListResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_list_visits",
)
def list_visits(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitListResponse:
    access.require_person(person_id, "visit.read")
    return VisitListResponse(
        visits=[_visit_response(visit) for visit in runtime.visits.list_visits(person_id)]
    )


@router.get(
    "/visits/{visit_id}",
    response_model=VisitResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_get_visit",
)
def get_visit(
    visit_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitResponse:
    access.require_visit(visit_id, "visit.read")
    return _visit_response(runtime.visits.get_visit(visit_id))


@router.patch(
    "/visits/{visit_id}",
    response_model=VisitResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_update_visit",
)
def update_visit(
    visit_id: ProductCoreIdentifier,
    payload: VisitUpdateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitResponse:
    return _visit_response(
        runtime.visits.update_visit(
            visit_id,
            title=payload.title,
            specialist=payload.specialist,
            scheduled_date=payload.scheduled_date,
            update_fields=frozenset(payload.model_fields_set),
            authorize=access.authorize_visit_mutation(
                visit_id, "visit.write", action="visit.update"
            ),
        )
    )


@router.post(
    "/visits/{visit_id}/questions",
    response_model=VisitQuestionResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_create_visit_question",
)
def create_visit_question(
    visit_id: ProductCoreIdentifier,
    payload: VisitQuestionCreateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitQuestionResponse:
    return _visit_question_response(
        runtime.visits.create_question(
            visit_id,
            payload.question_text,
            authorize=access.authorize_visit_mutation(
                visit_id, "visit.write", action="visit_question.create"
            ),
        )
    )


@router.get(
    "/visits/{visit_id}/questions",
    response_model=VisitQuestionListResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_list_visit_questions",
)
def list_visit_questions(
    visit_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitQuestionListResponse:
    access.require_visit(visit_id, "visit.read")
    return VisitQuestionListResponse(
        questions=[
            _visit_question_response(question)
            for question in runtime.visits.list_questions(visit_id)
        ]
    )


@router.patch(
    "/visit-questions/{question_id}",
    response_model=VisitQuestionResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_update_visit_question",
)
def update_visit_question(
    question_id: ProductCoreIdentifier,
    payload: VisitQuestionUpdateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitQuestionResponse:
    return _visit_question_response(
        runtime.visits.update_question(
            question_id,
            question_text=payload.question_text,
            position=payload.position,
            update_fields=frozenset(payload.model_fields_set),
            authorize=access.authorize_question_mutation(
                question_id, "visit.write", action="visit_question.update"
            ),
        )
    )


@router.delete(
    "/visit-questions/{question_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_delete_visit_question",
)
def delete_visit_question(
    question_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> Response:
    runtime.visits.delete_question(
        question_id,
        authorize=access.authorize_question_mutation(
            question_id, "visit.write", action="visit_question.delete"
        ),
    )
    return Response(status_code=204)


@router.get(
    "/people/{person_id}",
    response_model=PersonResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_person",
)
def get_person(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> PersonResponse:
    access.require_person(person_id, "person.read")
    return _person_response(runtime.people.get(person_id))


@router.get(
    "/people/{person_id}/workspace-capabilities",
    response_model=WorkspaceCapabilitiesResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_workspace_capabilities",
)
def get_workspace_capabilities(
    person_id: ProductCoreIdentifier,
    access: AccessDependency,
) -> WorkspaceCapabilitiesResponse:
    """Return the current Actor's capability map on a Person (read-only).

    Presentation metadata only — never replaces server-side authorization.
    Only the current Actor's booleans are returned; hidden or missing Person,
    or a missing/revoked assignment, fails closed with 404 person_not_found.
    """
    scopes = access.effective_scopes(person_id)
    return WorkspaceCapabilitiesResponse(
        person_id=person_id,
        capabilities=WorkspaceCapabilities(
            person_update="person.update" in scopes,
            source_write="source.write" in scopes,
            document_read="document.read" in scopes,
            document_write="document.write" in scopes,
            candidate_review="candidate.review" in scopes,
            medication_read="medication.read" in scopes,
            medication_write="medication.write" in scopes,
            condition_read="condition.read" in scopes,
            condition_write="condition.write" in scopes,
            lab_read="lab.read" in scopes,
            lab_write="lab.write" in scopes,
            timeline_read="timeline.read" in scopes,
            visit_read="visit.read" in scopes,
            visit_write="visit.write" in scopes,
            brief_read="brief.read" in scopes,
            brief_write="brief.write" in scopes,
            brief_export="brief.export" in scopes,
            vault_export="vault.export" in scopes,
            chat_use="chat.use" in scopes,
        ),
    )


@router.patch(
    "/people/{person_id}",
    response_model=PersonResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_update_person",
)
def update_person(
    person_id: ProductCoreIdentifier,
    payload: PersonUpdateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> PersonResponse:
    return _person_response(
        runtime.people.update(
            person_id,
            display_name=payload.display_name,
            date_of_birth=payload.date_of_birth,
            update_date_of_birth="date_of_birth" in payload.model_fields_set,
            authorize=access.authorize_person_mutation(
                person_id, "person.update", action="person.update"
            ),
        )
    )


@router.post(
    "/sources/manual-medication",
    response_model=SourceRegistrationResponse,
    responses={
        200: {"model": SourceRegistrationResponse, "description": "Deduplicated source."},
        422: {"model": ErrorResponse},
    },
    status_code=201,
    operation_id="product_core_register_manual_medication_source",
)
def register_manual_source(
    payload: ManualSourceRequest,
    response: Response,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> SourceRegistrationResponse:
    result = runtime.sources.register_manual_entry_result(
        payload.person_id,
        payload.medication.display_name,
        schedule_text=payload.medication.schedule_text,
        note=payload.medication.note,
        authorize=access.authorize_person_mutation(
            payload.person_id, "source.write", action="source.create"
        ),
    )
    response.status_code = 201 if result.created else 200
    return SourceRegistrationResponse(
        created=result.created,
        source=_source_response(result.source),
    )


@router.post(
    "/sources/plain-text",
    response_model=SourceRegistrationResponse,
    responses={
        200: {"model": SourceRegistrationResponse, "description": "Deduplicated source."},
        422: {"model": ErrorResponse},
    },
    status_code=201,
    operation_id="product_core_register_plain_text_source",
)
def register_plain_text_source(
    payload: PlainTextSourceRequest,
    response: Response,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> SourceRegistrationResponse:
    result = runtime.sources.register_plain_text_result(
        payload.person_id,
        payload.content,
        authorize=access.authorize_person_mutation(
            payload.person_id, "source.write", action="source.create"
        ),
    )
    response.status_code = 201 if result.created else 200
    return SourceRegistrationResponse(
        created=result.created,
        source=_source_response(result.source),
    )


@router.get(
    "/sources/{source_id}",
    response_model=SourceMetadataResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    operation_id="product_core_get_source_metadata",
)
def get_source_metadata(
    source_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> SourceMetadataResponse:
    """Return safe, Person-isolated source provenance metadata (read-only).

    Ownership is resolved server-side from the sources table; a hidden or
    foreign source fails closed with 404 source_not_found. integrity_verified
    is true only after the immutable payload hash has been verified; a
    mismatch raises SourceCorruptionError (500 integrity) — never returned.
    """
    access.require_source(source_id, "source.read")
    source = runtime.sources.get(source_id)
    runtime.sources.store.read(source)
    if source.source_type == "document":
        runtime.documents.get(source_id)
    return SourceMetadataResponse(
        source_id=source.id,
        source_type=source.source_type,
        content_hash=source.content_hash,
        size_bytes=source.size_bytes,
        media_type=source.media_type,
        created_at=source.created_at,
        integrity_verified=True,
    )


@router.post(
    "/people/{person_id}/documents",
    response_model=DocumentRegistrationResponse,
    responses={
        409: {"model": DocumentRegistrationResponse, "description": "Existing document."},
        411: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    status_code=201,
    operation_id="product_core_register_document",
)
async def register_document(
    person_id: ProductCoreIdentifier,
    request: Request,
    response: Response,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> DocumentRegistrationResponse:
    payload = await _read_bounded_document_body(request)
    media_type = request.headers["content-type"].split(";", 1)[0].strip().lower()
    result = runtime.documents.register(
        person_id,
        payload,
        media_type,
        original_filename=request.headers.get("x-opencare-filename"),
        authorize=access.authorize_person_mutation(
            person_id,
            "source.write",
            "document.write",
            action="document.create",
        ),
    )
    response.status_code = 201 if result.created else 409
    return DocumentRegistrationResponse(
        created=result.created,
        document=_document_response(result.source, result.extraction),
    )


@router.get(
    "/people/{person_id}/documents",
    response_model=DocumentListResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    operation_id="product_core_list_documents",
)
def list_documents(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> DocumentListResponse:
    access.require_person(person_id, "document.read")
    return DocumentListResponse(
        documents=[
            _document_response(source, extraction)
            for source, extraction in runtime.documents.list_for_person(person_id)
        ]
    )


@router.get(
    "/people/{person_id}/documents/{source_id}",
    response_model=DocumentResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    operation_id="product_core_get_document",
)
def get_document(
    person_id: ProductCoreIdentifier,
    source_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> DocumentResponse:
    access.require_source_for_person(source_id, person_id, "document.read")
    source, extraction = runtime.documents.get(source_id)
    return _document_response(source, extraction)


@router.get(
    ("/people/{person_id}/documents/{source_id}/extractions/{extraction_id}/pages/{page_number}"),
    response_model=DocumentPageResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    operation_id="product_core_get_document_page",
)
def get_document_page(
    person_id: ProductCoreIdentifier,
    source_id: ProductCoreIdentifier,
    extraction_id: ProductCoreIdentifier,
    page_number: Annotated[int, Path(ge=1, le=MAX_DOCUMENT_PAGES)],
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> DocumentPageResponse:
    access.require_source_for_person(source_id, person_id, "document.read")
    snapshot, page = runtime.documents.get_page(source_id, extraction_id, page_number)
    return DocumentPageResponse(
        source_id=source_id,
        extraction_id=snapshot.extraction_id,
        page_number=page.page_number,
        normalized_text=page.normalized_text,
        decoded_content_bytes=page.decoded_content_bytes,
        extracted_chars=page.extracted_chars,
        page_hash=page.page_hash,
    )


@router.post(
    "/candidates/medications",
    response_model=CandidateResponse,
    responses={422: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_create_medication_candidate",
)
def create_medication_candidate(
    payload: MedicationCandidateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> CandidateResponse:
    candidate = runtime.lifecycle.create_candidate(
        person_id=payload.person_id,
        source_id=payload.source_id,
        display_name=payload.display_name,
        schedule_text=payload.schedule_text,
        note=payload.note,
        provenance_locator=payload.provenance_locator,
        authorize=access.combine_mutation_authorizers(
            access.authorize_person_mutation(
                payload.person_id, "candidate.review", action="candidate.create"
            ),
            access.authorize_source_mutation(
                payload.source_id,
                payload.person_id,
                "source.read",
                action="source.read",
            ),
        ),
    )
    return _candidate_response(candidate)


@router.get(
    "/candidates/{candidate_id}",
    response_model=CandidateResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_candidate",
)
def get_candidate(
    candidate_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> CandidateResponse:
    access.require_candidate(candidate_id, "candidate.read")
    return _candidate_response(runtime.lifecycle.get_candidate(candidate_id))


@router.get(
    "/people/{person_id}/candidates",
    response_model=CandidateListResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_candidates",
)
def list_candidates(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    status: Annotated[CandidateStatus | None, Query()] = None,
) -> CandidateListResponse:
    access.require_person(person_id, "candidate.read")
    candidates = runtime.lifecycle.list_candidates(person_id, status)
    return CandidateListResponse(candidates=[_candidate_response(item) for item in candidates])


@router.post(
    "/candidates/{candidate_id}/confirm",
    response_model=CanonicalMedicationResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    operation_id="product_core_confirm_candidate",
)
def confirm_candidate(
    candidate_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> CanonicalMedicationResponse:
    return _canonical_response(
        runtime.lifecycle.confirm(
            candidate_id,
            authorize=access.authorize_candidate_review_mutation(
                candidate_id,
                action="candidate.confirm",
            ),
        )
    )


@router.post(
    "/candidates/{candidate_id}/reject",
    response_model=CandidateResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    operation_id="product_core_reject_candidate",
)
def reject_candidate(
    candidate_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> CandidateResponse:
    return _candidate_response(
        runtime.lifecycle.reject(
            candidate_id,
            authorize=access.authorize_candidate_mutation(
                candidate_id, "candidate.review", action="candidate.reject"
            ),
        )
    )


@router.post(
    "/candidates/{candidate_id}/unsupported",
    response_model=CandidateResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    operation_id="product_core_unsupported_candidate",
)
def unsupported_candidate(
    candidate_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> CandidateResponse:
    return _candidate_response(
        runtime.lifecycle.unsupported(
            candidate_id,
            authorize=access.authorize_candidate_mutation(
                candidate_id, "candidate.review", action="candidate.unsupported"
            ),
        )
    )


@router.post(
    "/candidates/{candidate_id}/correct",
    response_model=CandidateResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_correct_candidate",
)
def correct_candidate(
    candidate_id: ProductCoreIdentifier,
    payload: CorrectCandidateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> CandidateResponse:
    replacement = runtime.lifecycle.correct(
        candidate_id,
        display_name=payload.display_name,
        schedule_text=payload.schedule_text,
        note=payload.note,
        source_id=payload.source_id,
        provenance_locator=payload.provenance_locator,
        authorize=access.authorize_candidate_review_mutation(
            candidate_id,
            action="candidate.correct",
            replacement_source_id=payload.source_id,
        ),
    )
    return _candidate_response(replacement)


@router.post(
    "/sources/manual-condition",
    response_model=SourceRegistrationResponse,
    responses={
        200: {"model": SourceRegistrationResponse, "description": "Deduplicated source."},
        422: {"model": ErrorResponse},
    },
    status_code=201,
    operation_id="product_core_register_manual_condition_source",
)
def register_manual_condition_source(
    payload: ManualConditionSourceRequest,
    response: Response,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> SourceRegistrationResponse:
    result = runtime.sources.register_structured_manual_entry_result(
        payload.person_id,
        "condition",
        {
            "display_name": payload.condition.display_name,
            "status_text": payload.condition.status_text,
            "onset_date": (
                None
                if payload.condition.onset_date is None
                else payload.condition.onset_date.isoformat()
            ),
            "note": payload.condition.note,
        },
        authorize=access.authorize_person_mutation(
            payload.person_id, "source.write", action="source.create"
        ),
    )
    response.status_code = 201 if result.created else 200
    return SourceRegistrationResponse(
        created=result.created,
        source=_source_response(result.source),
    )


@router.post(
    "/candidates/conditions",
    response_model=ConditionCandidateResponse,
    responses={422: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_create_condition_candidate",
)
def create_condition_candidate(
    payload: ConditionCandidateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> ConditionCandidateResponse:
    candidate = runtime.lifecycle.create_fact_candidate(
        person_id=payload.person_id,
        source_id=payload.source_id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(
            display_name=payload.display_name,
            status_text=payload.status_text,
            onset_date=payload.onset_date,
            note=payload.note,
        ),
        provenance_locator=payload.provenance_locator,
        authorize=access.combine_mutation_authorizers(
            access.authorize_person_mutation(
                payload.person_id, "candidate.review", action="candidate.create"
            ),
            access.authorize_source_mutation(
                payload.source_id,
                payload.person_id,
                "source.read",
                action="source.read",
            ),
        ),
    )
    return _condition_candidate_response(candidate)


@router.get(
    "/people/{person_id}/conditions",
    response_model=ConditionRecordListResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_conditions",
)
def list_conditions(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    include_inactive: Annotated[bool, Query()] = False,
) -> ConditionRecordListResponse:
    access.require_person(person_id, "condition.read")
    records = runtime.lifecycle.list_fact_canonical(
        person_id, include_inactive=include_inactive, fact_type="condition"
    )
    return ConditionRecordListResponse(
        conditions=[_condition_record_response(record) for record in records]
    )


@router.get(
    "/conditions/{record_id}",
    response_model=ConditionRecordResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_condition_record",
)
def get_condition_record(
    record_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> ConditionRecordResponse:
    access.require_condition_record(record_id, "condition.read")
    record = runtime.lifecycle.get_canonical(record_id)
    return _condition_record_response(record)


@router.post(
    "/candidates/{candidate_id}/correct:condition",
    response_model=ConditionCandidateResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_correct_condition_candidate",
)
def correct_condition_candidate(
    candidate_id: ProductCoreIdentifier,
    payload: ConditionCorrectRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> ConditionCandidateResponse:
    replacement = runtime.lifecycle.correct_fact_candidate(
        candidate_id,
        detail_input=ConditionCandidateInput(
            display_name=payload.display_name,
            status_text=payload.status_text,
            onset_date=payload.onset_date,
            note=payload.note,
        ),
        source_id=payload.source_id,
        provenance_locator=payload.provenance_locator,
        authorize=access.authorize_candidate_review_mutation(
            candidate_id,
            action="candidate.correct",
            replacement_source_id=payload.source_id,
        ),
    )
    return _condition_candidate_response(replacement)


@router.get(
    "/people/{person_id}/condition-candidates",
    response_model=ConditionCandidateListResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_condition_candidates",
)
def list_condition_candidates(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    status: Annotated[CandidateStatus | None, Query()] = None,
) -> ConditionCandidateListResponse:
    access.require_person(person_id, "condition.read")
    candidates = runtime.lifecycle.list_fact_candidates(person_id, status, fact_type="condition")
    return ConditionCandidateListResponse(
        candidates=[_condition_candidate_response(item) for item in candidates]
    )


@router.get(
    "/candidates/conditions/{candidate_id}",
    response_model=ConditionCandidateResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_condition_candidate",
)
def get_condition_candidate(
    candidate_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> ConditionCandidateResponse:
    access.require_condition_candidate(candidate_id, "condition.read")
    candidate = runtime.lifecycle.get_candidate(candidate_id)
    return _condition_candidate_response(candidate)


@router.post(
    "/sources/manual-lab",
    response_model=SourceRegistrationResponse,
    responses={
        200: {"model": SourceRegistrationResponse, "description": "Deduplicated source."},
        422: {"model": ErrorResponse},
    },
    status_code=201,
    operation_id="product_core_register_manual_lab_source",
)
def register_manual_lab_source(
    payload: ManualLabSourceRequest,
    response: Response,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> SourceRegistrationResponse:
    result = runtime.sources.register_structured_manual_entry_result(
        payload.person_id,
        "lab",
        {
            "test_name": payload.lab.test_name,
            "result_text": payload.lab.result_text,
            "unit_text": payload.lab.unit_text,
            "reference_range_text": payload.lab.reference_range_text,
            "observed_date": (
                None if payload.lab.observed_date is None else payload.lab.observed_date.isoformat()
            ),
            "source_flag_text": payload.lab.source_flag_text,
            "note": payload.lab.note,
        },
        authorize=access.authorize_person_mutation(
            payload.person_id, "source.write", action="source.create"
        ),
    )
    response.status_code = 201 if result.created else 200
    return SourceRegistrationResponse(
        created=result.created,
        source=_source_response(result.source),
    )


@router.post(
    "/candidates/labs",
    response_model=LabCandidateResponse,
    responses={422: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_create_lab_candidate",
)
def create_lab_candidate(
    payload: LabCandidateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> LabCandidateResponse:
    candidate = runtime.lifecycle.create_fact_candidate(
        person_id=payload.person_id,
        source_id=payload.source_id,
        fact_type="lab",
        detail_input=LabCandidateInput(
            test_name=payload.test_name,
            result_text=payload.result_text,
            unit_text=payload.unit_text,
            reference_range_text=payload.reference_range_text,
            observed_date=payload.observed_date,
            source_flag_text=payload.source_flag_text,
            note=payload.note,
        ),
        provenance_locator=payload.provenance_locator,
        authorize=access.combine_mutation_authorizers(
            access.authorize_person_mutation(
                payload.person_id, "candidate.review", action="candidate.create"
            ),
            access.authorize_source_mutation(
                payload.source_id,
                payload.person_id,
                "source.read",
                action="source.read",
            ),
        ),
    )
    return _lab_candidate_response(candidate)


@router.get(
    "/people/{person_id}/labs",
    response_model=LabRecordListResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_labs",
)
def list_labs(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    include_inactive: Annotated[bool, Query()] = False,
) -> LabRecordListResponse:
    access.require_person(person_id, "lab.read")
    records = runtime.lifecycle.list_fact_canonical(
        person_id, include_inactive=include_inactive, fact_type="lab"
    )
    return LabRecordListResponse(labs=[_lab_record_response(record) for record in records])


@router.get(
    "/labs/{record_id}",
    response_model=LabRecordResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_lab_record",
)
def get_lab_record(
    record_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> LabRecordResponse:
    access.require_lab_record(record_id, "lab.read")
    return _lab_record_response(runtime.lifecycle.get_canonical(record_id))


@router.get(
    "/people/{person_id}/lab-candidates",
    response_model=LabCandidateListResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_lab_candidates",
)
def list_lab_candidates(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    status: Annotated[CandidateStatus | None, Query()] = None,
) -> LabCandidateListResponse:
    access.require_person(person_id, "lab.read")
    candidates = runtime.lifecycle.list_fact_candidates(person_id, status, fact_type="lab")
    return LabCandidateListResponse(
        candidates=[_lab_candidate_response(item) for item in candidates]
    )


@router.get(
    "/candidates/labs/{candidate_id}",
    response_model=LabCandidateResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_lab_candidate",
)
def get_lab_candidate(
    candidate_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> LabCandidateResponse:
    access.require_lab_candidate(candidate_id, "lab.read")
    return _lab_candidate_response(runtime.lifecycle.get_candidate(candidate_id))


@router.post(
    "/candidates/{candidate_id}/correct:lab",
    response_model=LabCandidateResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_correct_lab_candidate",
)
def correct_lab_candidate(
    candidate_id: ProductCoreIdentifier,
    payload: LabCorrectRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> LabCandidateResponse:
    replacement = runtime.lifecycle.correct_fact_candidate(
        candidate_id,
        detail_input=LabCandidateInput(
            test_name=payload.test_name,
            result_text=payload.result_text,
            unit_text=payload.unit_text,
            reference_range_text=payload.reference_range_text,
            observed_date=payload.observed_date,
            source_flag_text=payload.source_flag_text,
            note=payload.note,
        ),
        source_id=payload.source_id,
        provenance_locator=payload.provenance_locator,
        authorize=access.authorize_candidate_review_mutation(
            candidate_id,
            action="candidate.correct",
            replacement_source_id=payload.source_id,
        ),
    )
    return _lab_candidate_response(replacement)


@router.get(
    "/people/{person_id}/medications",
    response_model=CanonicalMedicationListResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_medications",
)
def list_medications(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    include_inactive: Annotated[bool, Query()] = False,
) -> CanonicalMedicationListResponse:
    access.require_person(person_id, "medication.read")
    records = runtime.lifecycle.list_canonical(person_id, include_inactive=include_inactive)
    return CanonicalMedicationListResponse(
        medications=[_canonical_response(record) for record in records]
    )


@router.get(
    "/people/{person_id}/timeline",
    response_model=TimelineResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_timeline",
)
def list_timeline(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> TimelineResponse:
    access.require_person(person_id, "timeline.read")
    events = runtime.lifecycle.list_timeline(person_id)
    return TimelineResponse(events=[_timeline_response(event) for event in events])


@router.post(
    "/people/{person_id}/vault-export",
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    operation_id="product_core_export_person_portable_vault",
)
def export_person_portable_vault(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> Response:
    access.require_person(
        person_id,
        "vault.export",
        audit_action="vault.export",
        required_audit=True,
    )
    exported = runtime.portable_vault_exports.export(person_id)
    return Response(
        content=exported.zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="opencare-person-vault-v{PORTABLE_VAULT_FORMAT_VERSION}.zip"'
            ),
        },
    )


@router.post(
    "/visits/{visit_id}/brief",
    response_model=VisitBriefInitializeResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    status_code=201,
    operation_id="product_core_initialize_persisted_visit_brief",
)
def initialize_persisted_visit_brief(
    visit_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> VisitBriefInitializeResponse:
    brief = runtime.persisted_visit_briefs.initialize(
        visit_id,
        authorize=access.authorize_visit_mutation(
            visit_id, "brief.write", action="brief.initialize"
        ),
    )
    return VisitBriefInitializeResponse(
        visit_id=brief.visit_id,
        current_revision_number=brief.current_revision_number,
        created_at=brief.created_at,
        updated_at=brief.updated_at,
    )


@router.get(
    "/visits/{visit_id}/brief",
    response_model=VisitBriefResponseV2,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_persisted_visit_brief",
)
def get_persisted_visit_brief(
    visit_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefResponseV2:
    access.require_visit(visit_id, "brief.read")
    return _persisted_brief_response(
        runtime, visit_id, runtime.persisted_visit_briefs.get(visit_id)
    )


@router.get(
    "/visits/{visit_id}/brief/revisions",
    response_model=VisitBriefRevisionListResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_list_persisted_visit_brief_revisions",
)
def list_persisted_visit_brief_revisions(
    visit_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefRevisionListResponse:
    access.require_visit(visit_id, "brief.read")
    return VisitBriefRevisionListResponse(
        revisions=[
            _persisted_revision_response(runtime, visit_id, revision)
            for revision in runtime.persisted_visit_briefs.list_revisions(visit_id)
        ]
    )


@router.get(
    "/visits/{visit_id}/brief/revisions/{revision_number}",
    response_model=VisitBriefRevisionResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_persisted_visit_brief_revision",
)
def get_persisted_visit_brief_revision(
    visit_id: ProductCoreIdentifier,
    revision_number: Annotated[int, Path(ge=1)],
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefRevisionResponse:
    access.require_visit(visit_id, "brief.read")
    return _persisted_revision_response(
        runtime,
        visit_id,
        runtime.persisted_visit_briefs.get_revision(visit_id, revision_number),
    )


@router.get(
    "/visits/{visit_id}/brief/evidence",
    response_model=VisitBriefEligibleEvidenceResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_list_visit_brief_eligible_evidence",
)
def list_persisted_visit_brief_evidence(
    visit_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefEligibleEvidenceResponse:
    access.require_visit(visit_id, "brief.read")
    return VisitBriefEligibleEvidenceResponse(
        evidence=runtime.persisted_visit_briefs.list_eligible_evidence(visit_id)
    )


@router.post(
    "/visits/{visit_id}/brief/evidence:validate",
    response_model=VisitBriefEvidenceValidationResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_validate_visit_brief_evidence",
)
def validate_persisted_visit_brief_evidence(
    visit_id: ProductCoreIdentifier,
    payload: VisitBriefEvidenceRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefEvidenceValidationResponse:
    access.require_visit(visit_id, "brief.write")
    return VisitBriefEvidenceValidationResponse.model_validate(
        runtime.persisted_visit_briefs.validate_evidence_selection(
            visit_id, payload.selected_record_ids
        )
    )


@router.post(
    "/visits/{visit_id}/brief/revisions:generate",
    response_model=VisitBriefRevisionResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    status_code=201,
    operation_id="product_core_generate_persisted_visit_brief_revision",
)
def generate_persisted_visit_brief_revision(
    visit_id: ProductCoreIdentifier,
    payload: VisitBriefGenerateRevisionRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefRevisionResponse:
    revision = runtime.persisted_visit_briefs.generate(
        visit_id,
        selected_record_ids=payload.selected_record_ids,
        expected_current_revision_number=payload.expected_current_revision_number,
        authorize=access.authorize_visit_mutation(visit_id, "brief.write", action="brief.generate"),
    )
    return _persisted_revision_response(runtime, visit_id, revision)


@router.post(
    "/visits/{visit_id}/brief/revisions:user-edit",
    response_model=VisitBriefRevisionResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    status_code=201,
    operation_id="product_core_save_persisted_visit_brief_user_edit",
)
def save_persisted_visit_brief_user_edit(
    visit_id: ProductCoreIdentifier,
    payload: VisitBriefUserEditRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefRevisionResponse:
    revision = runtime.persisted_visit_briefs.save_user_edit(
        visit_id,
        preparation_notes=payload.preparation_notes,
        expected_current_revision_number=payload.expected_current_revision_number,
        authorize=access.authorize_visit_mutation(visit_id, "brief.write", action="brief.update"),
    )
    return _persisted_revision_response(runtime, visit_id, revision)


@router.post(
    "/visits/{visit_id}/brief/current",
    response_model=VisitBriefResponseV2,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
    operation_id="product_core_restore_persisted_visit_brief_revision",
)
def restore_persisted_visit_brief_revision(
    visit_id: ProductCoreIdentifier,
    payload: VisitBriefRestoreRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefResponseV2:
    brief = runtime.persisted_visit_briefs.restore(
        visit_id,
        revision_number=payload.revision_number,
        expected_current_revision_number=payload.expected_current_revision_number,
        authorize=access.authorize_visit_mutation(visit_id, "brief.write", action="brief.restore"),
    )
    return _persisted_brief_response(runtime, visit_id, brief)


@router.post(
    "/visits/{visit_id}/brief/current:export",
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    operation_id="product_core_export_current_persisted_visit_brief",
)
def export_current_persisted_visit_brief(
    visit_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> Response:
    markdown, revision_number = runtime.persisted_visit_briefs.export_current(
        visit_id,
        authorize=access.authorize_visit_mutation(visit_id, "brief.export", action="brief.export"),
    )
    return Response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown",
        headers={
            "Content-Disposition": (
                f'attachment; filename="opencare-visit-brief-r{revision_number}.md"'
            )
        },
    )


@router.post(
    "/people/{person_id}/visit-briefs:generate",
    response_model=VisitBriefResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_generate_visit_brief",
)
def generate_visit_brief(
    person_id: ProductCoreIdentifier,
    payload: VisitBriefGenerateRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> VisitBriefResponse:
    access.require_person(person_id, "brief.write")
    brief = runtime.visit_briefs.generate(
        VisitBriefRequest(
            person_id=person_id,
            visit_title=payload.visit_title,
            visit_purpose=payload.visit_purpose or payload.visit_title,
            scheduled_date=payload.scheduled_date,
            generated_at=payload.generated_at,
            selected_record_ids=payload.selected_record_ids,
        )
    )
    return VisitBriefResponse.model_validate(brief.model_dump())


@router.post(
    "/people/{person_id}/genetics/consent",
    response_model=dict[str, Any],
    operation_id="product_core_consent_genetics",
)
def consent_genetics(
    person_id: ProductCoreIdentifier,
    payload: GeneticsConsentRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> dict[str, Any]:
    access.require_person(person_id, "person.read")
    grant_id = runtime.genetics.grant_access(
        actor_id=access.actor_id,
        person_id=person_id,
        scopes=payload.scopes,
        granted_by_actor_id=access.actor_id,
        consent_confirmed=payload.confirmation,
    )
    return {"grant_id": grant_id, "person_id": person_id, "scopes": payload.scopes}


@router.post(
    "/people/{person_id}/genetics/access",
    response_model=dict[str, Any],
    operation_id="product_core_grant_genetics_access",
)
def grant_genetics_access(
    person_id: ProductCoreIdentifier,
    payload: GeneticsGrantRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> dict[str, Any]:
    access.require_person(person_id, "access.manage")
    grant_id = runtime.genetics.grant_access(
        actor_id=payload.actor_id,
        person_id=person_id,
        scopes=payload.scopes,
        granted_by_actor_id=access.actor_id,
        consent_confirmed=payload.confirmation,
    )
    return {"grant_id": grant_id, "person_id": person_id, "actor_id": payload.actor_id}


@router.get(
    "/people/{person_id}/genetics",
    response_model=dict[str, Any],
    operation_id="product_core_get_genetics_workspace",
)
def get_genetics_workspace(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> dict[str, Any]:
    access.require_genetics(person_id, "genetics.read")
    return runtime.genetics.overview(person_id=person_id)


@router.post(
    "/people/{person_id}/genetics/import",
    response_model=dict[str, Any],
    operation_id="product_core_import_genetics",
)
def import_genetics(
    person_id: ProductCoreIdentifier,
    payload: GeneticsImportRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> dict[str, Any]:
    access.require_genetics(person_id, "genetics.write")
    encoded = payload.payload_base64
    if len(encoded) > ((MAX_GENETICS_UPLOAD_BYTES + 2) // 3) * 4:
        raise GeneticsValidationError("genetics_upload_bytes_limit_exceeded")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise GeneticsValidationError("genetics_payload_base64_invalid") from exc
    result = runtime.genetics.import_consumer_genotype(
        person_id=person_id,
        payload=raw,
        original_filename=payload.filename,
        genome_build=payload.genome_build,
        confirmation=payload.confirmation,
        selected_loci=payload.selected_loci,
    )
    return result.__dict__


@router.post(
    "/people/{person_id}/genetics/findings/{finding_id}/review",
    response_model=dict[str, Any],
    operation_id="product_core_review_genetics_finding",
)
def review_genetics_finding(
    person_id: ProductCoreIdentifier,
    finding_id: ProductCoreIdentifier,
    payload: GeneticsReviewRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> dict[str, Any]:
    access.require_genetics(person_id, "genetics.read")
    return runtime.genetics.review_finding(
        finding_id=finding_id,
        person_id=person_id,
        actor_id=access.actor_id,
        status=payload.status,
        reason=payload.reason,
    )


@router.post(
    "/people/{person_id}/genetics/research",
    response_model=dict[str, Any],
    operation_id="product_core_run_genetics_research",
)
def run_genetics_research(
    person_id: ProductCoreIdentifier,
    payload: GeneticsResearchRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> dict[str, Any]:
    access.require_genetics(person_id, "genetics.research")
    if payload.second_person_id is not None:
        access.require_genetics(payload.second_person_id, "genetics.compare")
    packet = runtime.genetics.build_research_packet(
        person_id=person_id,
        finding_ids=payload.finding_ids,
        canonical_records=payload.canonical_records,
        second_person_id=payload.second_person_id,
    )
    return runtime.genetics.run_deterministic_research(
        person_id=person_id,
        actor_id=access.actor_id,
        mode=payload.mode,
        question=payload.question,
        packet=packet,
    )


@router.post(
    "/people/{person_id}/genetics/compare",
    response_model=dict[str, Any],
    operation_id="product_core_compare_genetics",
)
def compare_genetics(
    person_id: ProductCoreIdentifier,
    payload: GeneticsComparisonRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> dict[str, Any]:
    access.require_genetics(person_id, "genetics.compare")
    access.require_genetics(payload.person_b_id, "genetics.compare")
    return runtime.genetics.compare(person_a=person_id, person_b=payload.person_b_id)


@router.post(
    "/people/{person_id}/genetics/export",
    operation_id="product_core_export_genetics",
)
def export_genetics(
    person_id: ProductCoreIdentifier,
    payload: GeneticsExportRequest,
    runtime: RuntimeDependency,
    access: AccessDependency,
) -> Response:
    access.require_genetics(person_id, "genetics.export")
    if not payload.confirmation:
        raise GeneticsValidationError("genetics_export_confirmation_required")
    package = runtime.genetics.export_package(
        person_id=person_id,
        include_research=payload.include_research,
    )
    return Response(
        content=package,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="opencare-genetics-package-v1.zip"'},
    )
