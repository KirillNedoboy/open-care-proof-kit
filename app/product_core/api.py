from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BeforeValidator

from app.http_security import is_same_origin
from app.product_core.api_models import (
    CandidateListResponse,
    CandidateResponse,
    CandidateStatus,
    CanonicalMedicationListResponse,
    CanonicalMedicationResponse,
    CorrectCandidateRequest,
    EmptyActionRequest,
    ErrorResponse,
    ManualSourceRequest,
    MedicationCandidateRequest,
    PeopleListResponse,
    PersonCreateRequest,
    PersonResponse,
    PersonUpdateRequest,
    PlainTextSourceRequest,
    SourceRegistrationResponse,
    SourceResponse,
    TimelineEventResponse,
    TimelineResponse,
    VisitBriefGenerateRequest,
    VisitBriefResponse,
    _validate_identifier,
)
from app.product_core.errors import (
    CandidateNotFoundError,
    CanonicalRecordNotFoundError,
    IntegrityStorageError,
    InvalidTransitionError,
    NotFoundError,
    PersonMismatchError,
    PersonNotFoundError,
    PersonValidationError,
    ProductCoreError,
    RuntimeNotReadyError,
    SelectionError,
    SourceCorruptionError,
    SourceNotFoundError,
    SourcePublicationError,
    UnsafeSourcePathError,
)
from app.product_core.models import VisitBriefRequest
from app.product_core.runtime import ProductCoreRuntime

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
    if isinstance(exc, PersonValidationError):
        return _error_response(422, "request_validation_failed", "The request is invalid.")
    if isinstance(exc, PersonNotFoundError):
        return _error_response(404, "person_not_found", "Person was not found.")
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


async def _check_request_safety(request: Request) -> JSONResponse | None:
    if not is_same_origin(request):
        return _error_response(403, "origin_rejected", "The request origin is not allowed.")
    if request.method in {"POST", "PUT", "PATCH"}:
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            return _error_response(
                415,
                "json_content_type_required",
                "JSON content type is required.",
            )
    return None


class ProductCoreRoute(APIRoute):
    def get_route_handler(self) -> Callable[..., Any]:
        original_route_handler = super().get_route_handler()

        async def product_core_route_handler(request: Request) -> Any:
            safety_response = await _check_request_safety(request)
            if safety_response is not None:
                return safety_response
            try:
                return await original_route_handler(request)
            except RequestValidationError as exc:
                return _error_response(
                    422,
                    "request_validation_failed",
                    "The request is invalid.",
                    _validation_details(exc),
                )
            except ProductCoreError as exc:
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
    )


def _canonical_response(record: Any) -> CanonicalMedicationResponse:
    return CanonicalMedicationResponse(
        id=record.id,
        person_id=record.person_id,
        candidate_id=record.candidate_id,
        source_id=record.source_id,
        display_name=record.display_name,
        schedule_text=record.schedule_text,
        note=record.note,
        confirmed_at=record.confirmed_at,
        is_active=record.is_active,
    )


def _timeline_response(event: Any) -> TimelineEventResponse:
    return TimelineEventResponse(
        id=event.id,
        person_id=event.person_id,
        canonical_record_id=event.canonical_record_id,
        source_id=event.source_id,
        event_type=event.event_type,
        event_at=event.event_at,
        title=event.title,
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
) -> PersonResponse:
    return _person_response(
        runtime.people.create(payload.display_name, date_of_birth=payload.date_of_birth)
    )


@router.get(
    "/people",
    response_model=PeopleListResponse,
    operation_id="product_core_list_people",
)
def list_people(runtime: RuntimeDependency) -> PeopleListResponse:
    return PeopleListResponse(
        people=[_person_response(person) for person in runtime.people.list_active()]
    )


@router.get(
    "/people/{person_id}",
    response_model=PersonResponse,
    responses={404: {"model": ErrorResponse}},
    operation_id="product_core_get_person",
)
def get_person(person_id: ProductCoreIdentifier, runtime: RuntimeDependency) -> PersonResponse:
    return _person_response(runtime.people.get(person_id))


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
) -> PersonResponse:
    return _person_response(
        runtime.people.update(
            person_id,
            display_name=payload.display_name,
            date_of_birth=payload.date_of_birth,
            update_date_of_birth="date_of_birth" in payload.model_fields_set,
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
) -> SourceRegistrationResponse:
    result = runtime.sources.register_manual_entry_result(
        payload.person_id,
        payload.medication.display_name,
        schedule_text=payload.medication.schedule_text,
        note=payload.medication.note,
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
) -> SourceRegistrationResponse:
    result = runtime.sources.register_plain_text_result(payload.person_id, payload.content)
    response.status_code = 201 if result.created else 200
    return SourceRegistrationResponse(
        created=result.created,
        source=_source_response(result.source),
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
) -> CandidateResponse:
    candidate = runtime.lifecycle.create_candidate(
        person_id=payload.person_id,
        source_id=payload.source_id,
        display_name=payload.display_name,
        schedule_text=payload.schedule_text,
        note=payload.note,
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
) -> CandidateResponse:
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
    status: Annotated[CandidateStatus | None, Query()] = None,
) -> CandidateListResponse:
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
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> CanonicalMedicationResponse:
    return _canonical_response(runtime.lifecycle.confirm(candidate_id))


@router.post(
    "/candidates/{candidate_id}/reject",
    response_model=CandidateResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    operation_id="product_core_reject_candidate",
)
def reject_candidate(
    candidate_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    _payload: Annotated[EmptyActionRequest | None, Body()] = None,
) -> CandidateResponse:
    return _candidate_response(runtime.lifecycle.reject(candidate_id))


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
) -> CandidateResponse:
    replacement = runtime.lifecycle.correct(
        candidate_id,
        display_name=payload.display_name,
        schedule_text=payload.schedule_text,
        note=payload.note,
    )
    return _candidate_response(replacement)


@router.get(
    "/people/{person_id}/medications",
    response_model=CanonicalMedicationListResponse,
    responses={422: {"model": ErrorResponse}},
    operation_id="product_core_list_medications",
)
def list_medications(
    person_id: ProductCoreIdentifier,
    runtime: RuntimeDependency,
    include_inactive: Annotated[bool, Query()] = False,
) -> CanonicalMedicationListResponse:
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
) -> TimelineResponse:
    events = runtime.lifecycle.list_timeline(person_id)
    return TimelineResponse(events=[_timeline_response(event) for event in events])


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
) -> VisitBriefResponse:
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
