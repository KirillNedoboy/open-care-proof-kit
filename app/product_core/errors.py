class ProductCoreError(Exception):
    """Base error for Product Core operations."""


class InvalidTransitionError(ProductCoreError):
    """Raised when a candidate cannot make the requested review transition."""


class IntegrityStorageError(ProductCoreError):
    """Raised when persisted records contradict lifecycle invariants."""


class SourceCorruptionError(ProductCoreError):
    """Raised when an immutable source is missing or has changed."""


class SourcePublicationError(ProductCoreError):
    """Raised when an immutable source cannot be published safely."""


class UnsafeSourcePathError(ProductCoreError):
    """Raised when persisted source metadata escapes the configured root."""


class SelectionError(ProductCoreError):
    """Raised when Visit Brief record selection is invalid."""


class NotFoundError(ProductCoreError):
    """Raised when a requested Product Core record does not exist."""


class SourceNotFoundError(NotFoundError):
    """Raised when a requested source does not exist."""


class CandidateNotFoundError(NotFoundError):
    """Raised when a requested candidate does not exist."""


class CanonicalRecordNotFoundError(NotFoundError):
    """Raised when a requested canonical record does not exist."""


class PersonNotFoundError(NotFoundError):
    """Raised when a requested person does not exist."""


class VisitNotFoundError(NotFoundError):
    """Raised when a requested visit does not exist."""


class VisitQuestionNotFoundError(NotFoundError):
    """Raised when a requested visit question does not exist."""


class VisitBriefNotFoundError(NotFoundError):
    """Raised when a requested persisted visit brief does not exist."""


class VisitBriefRevisionNotFoundError(NotFoundError):
    """Raised when a requested persisted visit brief revision does not exist."""


class VisitBriefAlreadyExistsError(ProductCoreError):
    """Raised when a Visit already has its one logical brief."""


class VisitBriefConflictError(ProductCoreError):
    """Raised when a request is based on a stale current revision pointer."""


class VisitBriefValidationError(ProductCoreError, ValueError):
    """Raised when persisted brief input violates lifecycle rules."""


class VisitBriefIntegrityError(IntegrityStorageError):
    """Raised when a persisted Visit Brief cannot be verified safely."""


class VisitValidationError(ProductCoreError, ValueError):
    """Raised when a visit-planning value violates a domain constraint."""


class PersonValidationError(ProductCoreError, ValueError):
    """Raised when a person value violates a domain constraint."""


class PersonMismatchError(ProductCoreError):
    """Raised when related Product Core records belong to different people."""


class ProvenanceValidationError(ProductCoreError, ValueError):
    """Raised when a provenance locator is missing, malformed, or does not
    match the immutable source content."""

class DocumentValidationError(ProductCoreError, ValueError):
    """Raised when an uploaded document fails a bounded validation rule."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class DocumentTooLargeError(DocumentValidationError):
    """Raised when the raw request body exceeds the upload byte limit."""


class UnsupportedDocumentMediaTypeError(DocumentValidationError):
    """Raised when the declared or detected document class is unsupported."""


class RuntimeNotReadyError(ProductCoreError):
    """Raised when the application runtime was not initialized at startup."""


class ScopeForbiddenError(ProductCoreError):
    """Raised when an accessible Person assignment lacks an operation scope."""


class AccessAuditUnavailableError(ProductCoreError):
    """Raised when required sensitive-access audit persistence fails."""
