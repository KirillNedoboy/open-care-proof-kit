from __future__ import annotations

from datetime import datetime

from app.agent_trust.models import AuthorizationDecision, AuthorizationSnapshot
from app.family_access.policy import POLICY_VERSION
from app.family_access.service import FamilyAccessService


class OpenCareAuthorizationAdapter:
    """Capture one live Family Access decision without becoming an authority."""

    def __init__(self, service: FamilyAccessService) -> None:
        self.service = service

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision:
        with self.service.database.uow() as uow:
            assert uow.connection is not None
            connection = uow.connection
            credential = connection.execute(
                "SELECT 1 FROM actor_credentials ac JOIN actors a ON a.actor_id = ac.actor_id "
                "WHERE ac.actor_id = ? AND ac.credential_id = ? AND ac.revoked_at IS NULL "
                "AND a.status = 'active'",
                (actor_id, credential_id),
            ).fetchone()
            if credential is None:
                return _deny("authentication_required")
            assignment = None
            for scope in sorted(required_scopes):
                decision, candidate = self.service._authorize_person_in_connection(
                    connection, actor_id, person_id, scope
                )
                if not decision.allowed or candidate is None:
                    reason = (
                        "required_scope_missing"
                        if decision.reason_code == "person_access_denied"
                        else decision.reason_code
                    )
                    return _deny(reason)
                assignment = candidate
            assert assignment is not None
            row = connection.execute(
                "SELECT consent_event_id FROM person_access_assignments "
                "WHERE assignment_id = ? AND is_active = 1",
                (assignment.assignment_id,),
            ).fetchone()
            if row is None:
                return _deny("authorization_revoked")
            if not isinstance(assignment.scopes, frozenset):
                return _deny("person_access_denied")
            return AuthorizationDecision(
                decision="allow",
                reason_codes=[],
                snapshot=AuthorizationSnapshot(
                    actor_id=actor_id,
                    credential_id=credential_id,
                    person_id=person_id,
                    assignment_id=assignment.assignment_id,
                    role=assignment.role,
                    granted_scopes=sorted(assignment.scopes),
                    required_scopes=sorted(required_scopes),
                    consent_event_id=str(row[0]),
                    authorized_at=authorized_at,
                    access_expires_at=None,
                    policy_version=POLICY_VERSION,
                ),
            )


def _deny(reason_code: str) -> AuthorizationDecision:
    return AuthorizationDecision(decision="deny", reason_codes=[reason_code], snapshot=None)
