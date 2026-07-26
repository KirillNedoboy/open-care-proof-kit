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


class PersonMismatchError(ProductCoreError):
    """Raised when related Product Core records belong to different people."""


class RuntimeNotReadyError(ProductCoreError):
    """Raised when the application runtime was not initialized at startup."""
