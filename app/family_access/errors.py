class FamilyAccessError(Exception):
    """Base class for privacy-safe family-access failures."""


class AuditWriteError(FamilyAccessError):
    pass


class BootstrapUnavailableError(FamilyAccessError):
    pass


class AuthenticationError(FamilyAccessError):
    pass


class AuthorizationError(FamilyAccessError):
    pass


class PersonAccessDeniedError(AuthorizationError):
    def __init__(self, person_id: str, required_scope: str) -> None:
        super().__init__("Person was not found.")
        self.person_id = person_id
        self.required_scope = required_scope


class ConfirmationRequiredError(AuthorizationError):
    pass


class InvitationUnavailableError(FamilyAccessError):
    def __init__(self) -> None:
        super().__init__("Invitation is unavailable.")


class LastAdministratorError(FamilyAccessError):
    pass


class LastOwnerError(FamilyAccessError):
    pass


class ConflictError(FamilyAccessError):
    pass


class NotFoundError(FamilyAccessError):
    pass


class ValidationError(FamilyAccessError):
    pass
