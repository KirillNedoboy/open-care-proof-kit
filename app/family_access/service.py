from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import sqlite3
from collections.abc import Callable, Iterable, Iterator, Set
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Literal, cast

from app.family_access.credentials import (
    CredentialHash,
    dummy_verify_password,
    hash_password,
    normalize_username,
    verify_password,
)
from app.family_access.errors import (
    AuthenticationError,
    AuthorizationError,
    BootstrapUnavailableError,
    ConfirmationRequiredError,
    ConflictError,
    InvitationUnavailableError,
    LastAdministratorError,
    LastOwnerError,
    NotFoundError,
    PersonAccessDeniedError,
    ValidationError,
)
from app.family_access.models import (
    AccessRole,
    ActorRecord,
    AssignmentRecord,
    AuthenticatedCredential,
    FamilyRecord,
    InvitationIssued,
    InvitationPreview,
    MembershipRecord,
    RelationshipRecord,
)
from app.family_access.policy import (
    POLICY_VERSION,
    V1_POLICY_VERSION,
    V2_POLICY_VERSION,
    PersonAccessPolicy,
    PolicyDecision,
    build_scopes,
    infer_generation,
    valid_role_scopes,
)
from app.family_access.repository import FamilyAccessRepository, parse_utc
from app.product_core.models import Person, isoformat_utc
from app.product_core.services import Clock, IdFactory, default_clock, default_id_factory
from app.product_core.sqlite import SQLiteDatabase

logger = logging.getLogger(__name__)
AuditEvent = dict[str, str | None]
AuditWriter = Callable[[sqlite3.Connection, AuditEvent], None]
SessionInvalidator = Callable[[str], object]
_DUMMY_INVITATION_HASH = hashlib.sha256(b"opencare-invalid-invitation-v1").digest()


class FamilyAccessService:
    def __init__(
        self,
        database: SQLiteDatabase,
        *,
        clock: Clock = default_clock,
        id_factory: IdFactory = default_id_factory,
        policy: PersonAccessPolicy | None = None,
        audit_writer: AuditWriter | None = None,
        session_invalidator: SessionInvalidator | None = None,
    ) -> None:
        self.database = database
        self.clock = clock
        self.id_factory = id_factory
        self.policy = policy or PersonAccessPolicy()
        self.audit_writer = audit_writer or self._default_audit_writer
        self.session_invalidator = session_invalidator

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    def _timestamp(self) -> str:
        return isoformat_utc(self._now())

    def _id(self) -> str:
        return self.id_factory()

    @staticmethod
    def _scopes_json(scopes: Set[str]) -> str:
        return json.dumps(sorted(scopes), separators=(",", ":"))

    def bootstrap_available(self) -> bool:
        with self.database.connect() as connection:
            actor_count = int(
                connection.execute("SELECT COUNT(*) FROM actors").fetchone()[0]
            )
        return actor_count == 0

    def bootstrap(
        self,
        *,
        username: str,
        display_name: str,
        password: str,
        person_ids: Iterable[str] = (),
        own_person_id: str | None = None,
        confirm_full_owner_access: bool = False,
    ) -> ActorRecord:
        username_normalized = normalize_username(username)
        display_name = self._clean_display_name(display_name)
        selected_people = list(dict.fromkeys(person_ids))
        if selected_people and not confirm_full_owner_access:
            raise ConfirmationRequiredError("owner_confirmation_required")
        if own_person_id is not None and own_person_id not in selected_people:
            raise ValidationError("own Person must be selected for ownership")
        credential = hash_password(password)
        now = self._timestamp()
        actor_id = self._id()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            connection = uow.connection
            if connection.execute("SELECT COUNT(*) FROM actors").fetchone()[0] != 0:
                raise BootstrapUnavailableError("bootstrap is no longer available")
            people = {
                str(row[0])
                for row in connection.execute(
                    "SELECT person_id FROM people WHERE is_active = 1"
                ).fetchall()
            }
            if any(person_id not in people for person_id in selected_people):
                raise NotFoundError("selected Person is unavailable")
            connection.execute(
                """
                INSERT INTO actors (
                    actor_id, username_normalized, display_name, status, created_at
                ) VALUES (?, ?, ?, 'active', ?)
                """,
                (actor_id, username_normalized, display_name, now),
            )
            self._insert_credential(connection, actor_id, credential, now)
            connection.execute(
                """
                INSERT INTO installation_admin_assignments (
                    admin_assignment_id, actor_id, assigned_by_actor_id, is_active, assigned_at
                ) VALUES (?, ?, ?, 1, ?)
                """,
                (self._id(), actor_id, actor_id, now),
            )
            self._audit(connection, actor_id, "bootstrap", "installation", None, "bootstrap")
            self._audit(connection, actor_id, "credential.create", "credential", None, "bootstrap")
            self._audit(connection, actor_id, "admin.assign", "actor", actor_id, "bootstrap")
            for person_id in selected_people:
                self._insert_assignment(
                    connection,
                    acting_actor_id=actor_id,
                    recipient_actor_id=actor_id,
                    person_id=person_id,
                    role="owner",
                    scopes=build_scopes("owner"),
                    event_type="grant",
                    reason_code="bootstrap_owner_grant",
                    now=now,
                )
            if own_person_id is not None:
                self._insert_own_link(connection, actor_id, own_person_id, actor_id, now)
        actor = self.get_actor(actor_id)
        assert actor is not None
        return actor

    def authenticate(self, username: str, password: str) -> ActorRecord | None:
        authenticated = self.authenticate_for_session(username, password)
        return None if authenticated is None else authenticated.actor

    def authenticate_for_session(
        self, username: str, password: str
    ) -> AuthenticatedCredential | None:
        try:
            username_normalized = normalize_username(username)
        except ValueError:
            dummy_verify_password(password)
            return None
        with self.database.connect() as connection:
            repository = FamilyAccessRepository(connection)
            actor = repository.get_actor_by_username(username_normalized)
            if actor is None or actor.status != "active":
                dummy_verify_password(password)
                return None
            row = connection.execute(
                """
                SELECT credential_id, algorithm, algorithm_version, salt, verifier
                FROM actor_credentials
                WHERE actor_id = ? AND revoked_at IS NULL
                """,
                (actor.actor_id,),
            ).fetchone()
            if row is None:
                dummy_verify_password(password)
                return None
            credential = CredentialHash(
                algorithm=str(row["algorithm"]),
                algorithm_version=int(row["algorithm_version"]),
                salt=bytes(row["salt"]),
                verifier=bytes(row["verifier"]),
            )
            if not verify_password(password, credential):
                return None
            return AuthenticatedCredential(actor=actor, credential_id=str(row["credential_id"]))

    def get_active_credential_id(self, actor_id: str) -> str | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT ac.credential_id
                FROM actor_credentials AS ac
                JOIN actors AS a ON a.actor_id = ac.actor_id
                WHERE ac.actor_id = ? AND ac.revoked_at IS NULL AND a.status = 'active'
                """,
                (actor_id,),
            ).fetchone()
        return None if row is None else str(row["credential_id"])

    def get_actor_for_session(
        self, actor_id: str, credential_id: str
    ) -> ActorRecord | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT a.actor_id, a.username_normalized, a.display_name,
                       a.status, a.created_at
                FROM actors AS a
                JOIN actor_credentials AS ac ON ac.actor_id = a.actor_id
                WHERE a.actor_id = ? AND a.status = 'active'
                      AND ac.credential_id = ? AND ac.revoked_at IS NULL
                """,
                (actor_id, credential_id),
            ).fetchone()
        return None if row is None else FamilyAccessRepository._actor(row)

    def get_actor(self, actor_id: str, *, require_active: bool = False) -> ActorRecord | None:
        with self.database.connect() as connection:
            actor = FamilyAccessRepository(connection).get_actor(actor_id)
        if require_active and (actor is None or actor.status != "active"):
            return None
        return actor

    def change_password(self, actor_id: str, current_password: str, new_password: str) -> None:
        credential = hash_password(new_password)
        now = self._timestamp()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            connection = uow.connection
            self._require_active_actor_in_connection(connection, actor_id)
            active = connection.execute(
                "SELECT credential_id, algorithm, algorithm_version, salt, verifier "
                "FROM actor_credentials "
                "WHERE actor_id = ? AND revoked_at IS NULL",
                (actor_id,),
            ).fetchone()
            if active is None:
                dummy_verify_password(current_password)
                raise AuthenticationError("current credential is invalid")
            current_credential = CredentialHash(
                algorithm=str(active["algorithm"]),
                algorithm_version=int(active["algorithm_version"]),
                salt=bytes(active["salt"]),
                verifier=bytes(active["verifier"]),
            )
            if not verify_password(current_password, current_credential):
                raise AuthenticationError("current credential is invalid")
            connection.execute(
                """
                UPDATE actor_credentials
                SET revoked_at = ?
                WHERE credential_id = ?
                """,
                (now, str(active[0])),
            )
            new_id = self._insert_credential(connection, actor_id, credential, now)
            connection.execute(
                """
                UPDATE actor_credentials
                SET replaced_by_credential_id = ?
                WHERE credential_id = ?
                """,
                (new_id, str(active[0])),
            )
            self._audit(
                connection, actor_id, "credential.replace", "credential", new_id, "password_changed"
            )
        self._invalidate_sessions(actor_id)

    def create_local_actor(
        self,
        acting_actor_id: str,
        *,
        username: str,
        display_name: str,
        password: str,
        installation_admin: bool = False,
    ) -> ActorRecord:
        credential = hash_password(password)
        actor_id = self._id()
        now = self._timestamp()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            connection = uow.connection
            self._require_admin_in_connection(connection, acting_actor_id)
            connection.execute(
                """
                INSERT INTO actors (
                    actor_id, username_normalized, display_name, status, created_at
                ) VALUES (?, ?, ?, 'active', ?)
                """,
                (
                    actor_id,
                    normalize_username(username),
                    self._clean_display_name(display_name),
                    now,
                ),
            )
            self._insert_credential(connection, actor_id, credential, now)
            self._audit(
                connection, acting_actor_id, "actor.create", "actor", actor_id, "local_actor"
            )
            self._audit(
                connection, acting_actor_id, "credential.create", "credential", None, "local_actor"
            )
            if installation_admin:
                connection.execute(
                    """
                    INSERT INTO installation_admin_assignments (
                        admin_assignment_id, actor_id, assigned_by_actor_id,
                        is_active, assigned_at
                    ) VALUES (?, ?, ?, 1, ?)
                    """,
                    (self._id(), actor_id, acting_actor_id, now),
                )
                self._audit(
                    connection, acting_actor_id, "admin.assign", "actor", actor_id, "admin_grant"
                )
        actor = self.get_actor(actor_id)
        assert actor is not None
        return actor

    def require_admin(self, actor_id: str) -> None:
        with self.database.connect() as connection:
            self._require_admin_in_connection(connection, actor_id)

    def list_actors(self, actor_id: str) -> list[ActorRecord]:
        self.require_admin(actor_id)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT actor_id, username_normalized, display_name, status, created_at "
                "FROM actors ORDER BY created_at, actor_id"
            ).fetchall()
            return [FamilyAccessRepository._actor(row) for row in rows]

    def authorize_person(
        self, actor_id: str, person_id: str, required_scope: str
    ) -> PolicyDecision:
        with self.database.uow() as uow:
            assert uow.connection is not None
            decision, _ = self._authorize_person_in_connection(
                uow.connection, actor_id, person_id, required_scope
            )
            return decision

    def require_person_access(
        self, actor_id: str, person_id: str, required_scope: str
    ) -> AssignmentRecord:
        with self._access_uow(actor_id) as connection:
            return self._require_person_access_in_connection(
                connection, actor_id, person_id, required_scope
            )

    @contextmanager
    def _access_uow(
        self,
        actor_id: str,
        *,
        begin_mode: Literal["DEFERRED", "IMMEDIATE"] = "DEFERRED",
    ) -> Iterator[sqlite3.Connection]:
        try:
            with self.database.uow(begin_mode=begin_mode) as uow:
                assert uow.connection is not None
                yield uow.connection
        except PersonAccessDeniedError as error:
            self._best_effort_denial_audit(
                actor_id, error.person_id, error.required_scope
            )
            raise

    def _authorize_person_in_connection(
        self,
        connection: sqlite3.Connection,
        actor_id: str,
        person_id: str,
        required_scope: str,
    ) -> tuple[PolicyDecision, AssignmentRecord | None]:
        repository = FamilyAccessRepository(connection)
        actor = repository.get_actor(actor_id)
        assignment = repository.get_active_assignment(actor_id, person_id)
        person_is_active = connection.execute(
            "SELECT 1 FROM people WHERE person_id = ? AND is_active = 1",
            (person_id,),
        ).fetchone()
        mapping = None
        if (
            actor is not None
            and actor.status == "active"
            and assignment is not None
            and person_is_active is not None
        ):
            mapping = {
                "actor_id": assignment.actor_id,
                "person_id": assignment.person_id,
                "role": assignment.role,
                "scopes": assignment.scopes,
                "is_active": assignment.is_active,
            }
        return (
            self.policy.authorize(
                actor_id=actor_id,
                person_id=person_id,
                required_scope=required_scope,
                assignment=mapping,
            ),
            assignment,
        )

    def _require_person_access_in_connection(
        self,
        connection: sqlite3.Connection,
        actor_id: str,
        person_id: str,
        required_scope: str,
    ) -> AssignmentRecord:
        decision, assignment = self._authorize_person_in_connection(
            connection, actor_id, person_id, required_scope
        )
        if not decision.allowed or assignment is None:
            raise PersonAccessDeniedError(person_id, required_scope)
        return assignment

    def _authorize_assignment_management_in_connection(
        self,
        connection: sqlite3.Connection,
        actor_id: str,
        person_id: str,
        *,
        requested_role: AccessRole,
        confirm_full_owner_access: bool,
    ) -> bool:
        decision, assignment = self._authorize_person_in_connection(
            connection, actor_id, person_id, "access.manage"
        )
        if decision.allowed and assignment is not None:
            return False
        person_is_active = connection.execute(
            "SELECT 1 FROM people WHERE person_id = ? AND is_active = 1",
            (person_id,),
        ).fetchone()
        repository = FamilyAccessRepository(connection)
        admin_can_claim = (
            person_is_active is not None
            and repository.is_active_admin(actor_id)
            and self._active_owner_count(connection, person_id) == 0
            and requested_role == "owner"
        )
        if not admin_can_claim:
            raise PersonAccessDeniedError(person_id, "access.manage")
        if not confirm_full_owner_access:
            raise ConfirmationRequiredError("owner_confirmation_required")
        return True

    @staticmethod
    def _require_active_actor_in_connection(
        connection: sqlite3.Connection, actor_id: str
    ) -> ActorRecord:
        actor = FamilyAccessRepository(connection).get_actor(actor_id)
        if actor is None or actor.status != "active":
            raise AuthenticationError("active Actor required")
        return actor

    def _require_admin_in_connection(
        self, connection: sqlite3.Connection, actor_id: str
    ) -> None:
        actor = FamilyAccessRepository(connection).get_actor(actor_id)
        if (
            actor is None
            or actor.status != "active"
            or not FamilyAccessRepository(connection).is_active_admin(actor_id)
        ):
            raise AuthorizationError("installation administrator required")

    def create_person(
        self,
        actor_id: str,
        *,
        display_name: str,
        date_of_birth: date | None,
        confirm_owner_assignment: bool,
        link_as_own: bool = False,
    ) -> str:
        if not confirm_owner_assignment:
            raise ConfirmationRequiredError("owner_confirmation_required")
        now_value = self._now()
        if date_of_birth is not None and date_of_birth > now_value.date():
            raise ValidationError("date of birth is invalid")
        now = isoformat_utc(now_value)
        person_id = self._id()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            self._require_active_actor_in_connection(uow.connection, actor_id)
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=self._clean_display_name(display_name),
                    date_of_birth=date_of_birth,
                    created_at=now_value,
                    updated_at=now_value,
                    is_active=True,
                )
            )
            connection = uow.connection
            self._insert_assignment(
                connection,
                acting_actor_id=actor_id,
                recipient_actor_id=actor_id,
                person_id=person_id,
                role="owner",
                scopes=build_scopes("owner"),
                event_type="grant",
                reason_code="person_creation_owner_grant",
                now=now,
            )
            if link_as_own:
                self._insert_own_link(connection, actor_id, person_id, actor_id, now)
            self._audit(
                connection,
                actor_id,
                "person.create",
                "person",
                person_id,
                "owner_assignment_confirmed",
            )
        return person_id

    def grant_assignment(
        self,
        acting_actor_id: str,
        person_id: str,
        recipient_actor_id: str,
        *,
        role: AccessRole,
        optional_scopes: Set[str],
        confirm_full_owner_access: bool,
    ) -> AssignmentRecord:
        scopes = build_scopes(role, optional_scopes)
        now = self._timestamp()
        with self._access_uow(acting_actor_id, begin_mode="IMMEDIATE") as connection:
            admin_claim = self._authorize_assignment_management_in_connection(
                connection,
                acting_actor_id,
                person_id,
                requested_role=role,
                confirm_full_owner_access=confirm_full_owner_access,
            )
            if role == "owner" and not confirm_full_owner_access:
                raise ConfirmationRequiredError("owner_confirmation_required")
            try:
                self._require_active_actor_in_connection(connection, recipient_actor_id)
            except AuthenticationError as error:
                raise NotFoundError("recipient Actor is unavailable") from error
            assignment_id = self._insert_assignment(
                connection,
                acting_actor_id=acting_actor_id,
                recipient_actor_id=recipient_actor_id,
                person_id=person_id,
                role=role,
                scopes=scopes,
                event_type="grant",
                reason_code=f"{role}_grant",
                now=now,
            )
            if admin_claim:
                self._audit(
                    connection,
                    acting_actor_id,
                    "admin.unclaimed_person.claim",
                    "person",
                    person_id,
                    "admin_owner_grant",
                )
        return AssignmentRecord(
            assignment_id=assignment_id,
            actor_id=recipient_actor_id,
            person_id=person_id,
            role=role,
            scopes=frozenset(scopes),
            is_active=True,
        )

    def revise_assignment(
        self,
        acting_actor_id: str,
        person_id: str,
        assignment_id: str,
        optional_scopes: Set[str],
        policy_generation: str | None = None,
    ) -> AssignmentRecord:
        """Revise a caregiver assignment.

        The resulting scopes are built under the assignment's inferred
        generation by default, so a routine revision NEVER silently moves a
        v1 caregiver to v2. Passing an explicit ``policy_generation`` of
        ``family-access-v2`` for a v1 assignment is the controlled upgrade
        path: it produces a new consent event recording the full resulting
        scope set.
        """
        now = self._timestamp()
        with self._access_uow(acting_actor_id, begin_mode="IMMEDIATE") as connection:
            self._require_person_access_in_connection(
                connection, acting_actor_id, person_id, "access.manage"
            )
            current = connection.execute(
                """
                SELECT * FROM person_access_assignments
                WHERE assignment_id = ? AND person_id = ? AND is_active = 1
                """,
                (assignment_id, person_id),
            ).fetchone()
            if current is None:
                raise NotFoundError("assignment is unavailable")
            if str(current["role"]) != "caregiver":
                raise ValidationError("owner assignments cannot be revised")
            inferred_generation = infer_generation(
                json.loads(str(current["scopes_json"]))
            )
            generation = policy_generation or inferred_generation
            generations = (V1_POLICY_VERSION, V2_POLICY_VERSION, POLICY_VERSION)
            if generation not in generations:
                raise ValidationError("unsupported policy generation")
            if generations.index(generation) < generations.index(inferred_generation):
                raise ValidationError("policy generation cannot be downgraded")
            scopes = build_scopes("caregiver", optional_scopes, generation=generation)
            is_upgrade = generation != inferred_generation
            reason_code = (
                "caregiver_scope_generation_upgrade" if is_upgrade else "caregiver_scope_revision"
            )
            connection.execute(
                """
                UPDATE person_access_assignments
                SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?
                WHERE assignment_id = ?
                """,
                (now, acting_actor_id, assignment_id),
            )
            new_id = self._insert_assignment(
                connection,
                acting_actor_id=acting_actor_id,
                recipient_actor_id=str(current["actor_id"]),
                person_id=person_id,
                role="caregiver",
                scopes=scopes,
                event_type="revise",
                reason_code=reason_code,
                now=now,
                revision_of_assignment_id=assignment_id,
            )
        return AssignmentRecord(
            assignment_id=new_id,
            actor_id=str(current["actor_id"]),
            person_id=person_id,
            role="caregiver",
            scopes=frozenset(scopes),
            is_active=True,
        )

    def upgrade_owner_generation(
        self,
        acting_actor_id: str,
        person_id: str,
        assignment_id: str,
        *,
        confirm_full_owner_access: bool,
    ) -> AssignmentRecord:
        """Explicitly upgrade an owner assignment to the current generation.

        Requires the owner high-risk confirmation and an actor with
        ``access.manage``. The active assignment's scopes are replaced in
        place (the unique active-assignment index forbids a revoke+regrant
        for the same actor), a NEW append-only consent event records the full
        v2 scope set, and the old v1 consent event stays byte-identical in
        history. This is never automatic: it is the owner's explicit action.
        """
        if not confirm_full_owner_access:
            raise ConfirmationRequiredError("owner_confirmation_required")
        now = self._timestamp()
        with self._access_uow(acting_actor_id, begin_mode="IMMEDIATE") as connection:
            self._require_person_access_in_connection(
                connection, acting_actor_id, person_id, "access.manage"
            )
            current = connection.execute(
                """
                SELECT * FROM person_access_assignments
                WHERE assignment_id = ? AND person_id = ? AND is_active = 1
                """,
                (assignment_id, person_id),
            ).fetchone()
            if current is None:
                raise NotFoundError("assignment is unavailable")
            if str(current["role"]) != "owner":
                raise ValidationError("owner upgrade requires an owner assignment")
            if infer_generation(json.loads(str(current["scopes_json"]))) == POLICY_VERSION:
                raise ConflictError("assignment is already on the current generation")
            scopes = build_scopes("owner", generation=POLICY_VERSION)
            consent_id = self._insert_consent(
                connection,
                acting_actor_id=acting_actor_id,
                recipient_actor_id=str(current["actor_id"]),
                person_id=person_id,
                role="owner",
                scopes=scopes,
                event_type="revise",
                reason_code="owner_generation_upgrade",
                now=now,
            )
            connection.execute(
                """
                UPDATE person_access_assignments
                SET scopes_json = ?, consent_event_id = ?, granted_by_actor_id = ?,
                    scope_generation = ?
                WHERE assignment_id = ?
                """,
                (
                    self._scopes_json(scopes),
                    consent_id,
                    acting_actor_id,
                    POLICY_VERSION,
                    assignment_id,
                ),
            )
            self._audit(
                connection,
                acting_actor_id,
                "assignment.revise",
                "assignment",
                assignment_id,
                "owner_generation_upgrade",
            )
        return AssignmentRecord(
            assignment_id=assignment_id,
            actor_id=str(current["actor_id"]),
            person_id=person_id,
            role="owner",
            scopes=frozenset(scopes),
            is_active=True,
        )

    def revoke_assignment(
        self,
        acting_actor_id: str,
        person_id: str,
        assignment_or_actor_id: str,
    ) -> None:
        now = self._timestamp()
        with self._access_uow(acting_actor_id, begin_mode="IMMEDIATE") as connection:
            self._require_person_access_in_connection(
                connection, acting_actor_id, person_id, "access.manage"
            )
            row = connection.execute(
                """
                SELECT * FROM person_access_assignments
                WHERE person_id = ? AND is_active = 1
                      AND (assignment_id = ? OR actor_id = ?)
                """,
                (person_id, assignment_or_actor_id, assignment_or_actor_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("assignment is unavailable")
            if str(row["role"]) == "owner" and self._active_owner_count(connection, person_id) <= 1:
                raise LastOwnerError("cannot remove the final active owner")
            recipient_actor_id = str(row["actor_id"])
            connection.execute(
                """
                UPDATE own_person_links
                SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?
                WHERE actor_id = ? AND person_id = ? AND is_active = 1
                """,
                (now, acting_actor_id, recipient_actor_id, person_id),
            )
            self._insert_consent(
                connection,
                acting_actor_id=acting_actor_id,
                recipient_actor_id=recipient_actor_id,
                person_id=person_id,
                role=cast(AccessRole, str(row["role"])),
                scopes=frozenset(json.loads(str(row["scopes_json"]))),
                event_type="revoke",
                reason_code="assignment_revoked",
                now=now,
            )
            connection.execute(
                """
                UPDATE person_access_assignments
                SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?
                WHERE assignment_id = ?
                """,
                (now, acting_actor_id, str(row["assignment_id"])),
            )
            self._audit(
                connection,
                acting_actor_id,
                "assignment.revoke",
                "assignment",
                str(row["assignment_id"]),
                "assignment_revoked",
            )

    def list_assignments(self, actor_id: str, person_id: str) -> list[dict[str, object]]:
        with self._access_uow(actor_id) as connection:
            self._require_person_access_in_connection(
                connection, actor_id, person_id, "access.read"
            )
            rows = connection.execute(
                "SELECT * FROM person_access_assignments WHERE person_id = ? "
                "ORDER BY granted_at, assignment_id",
                (person_id,),
            ).fetchall()
        return [
            {
                "assignment_id": str(row["assignment_id"]),
                "actor_id": str(row["actor_id"]),
                "person_id": str(row["person_id"]),
                "role": str(row["role"]),
                "scopes": sorted(json.loads(str(row["scopes_json"]))),
                "is_active": bool(row["is_active"]),
            }
            for row in rows
        ]

    def list_consents(self, actor_id: str, person_id: str) -> list[dict[str, object]]:
        with self._access_uow(actor_id) as connection:
            self._require_person_access_in_connection(
                connection, actor_id, person_id, "access.read"
            )
            rows = connection.execute(
                "SELECT * FROM person_access_consent_history WHERE person_id = ? "
                "ORDER BY created_at, consent_event_id",
                (person_id,),
            ).fetchall()
        return [
            {
                "consent_event_id": str(row["consent_event_id"]),
                "event_type": str(row["event_type"]),
                "recipient_actor_id": str(row["recipient_actor_id"]),
                "person_id": str(row["person_id"]),
                "role": str(row["role"]),
                "scopes": sorted(json.loads(str(row["scopes_json"]))),
                "reason_code": str(row["reason_code"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def list_audits(self, actor_id: str, person_id: str) -> list[dict[str, object]]:
        with self._access_uow(actor_id) as connection:
            self._require_person_access_in_connection(
                connection, actor_id, person_id, "access.read"
            )
            rows = connection.execute(
                """
                SELECT audit_event_id, actor_id, action_code, target_class,
                       target_id, outcome, reason_code, created_at
                FROM access_audit_events
                WHERE target_id = ? OR (
                    target_class = 'assignment' AND target_id IN (
                        SELECT assignment_id FROM person_access_assignments WHERE person_id = ?
                    )
                )
                ORDER BY created_at, audit_event_id
                """,
                (person_id, person_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_invitation(
        self,
        acting_actor_id: str,
        person_id: str,
        *,
        role: AccessRole,
        optional_scopes: Set[str],
        expires_at: datetime,
        confirm_full_owner_access: bool,
    ) -> InvitationIssued:
        expires_at = expires_at.astimezone(UTC)
        if expires_at <= self._now():
            raise ValidationError("invitation expiry must be in the future")
        scopes = build_scopes(role, optional_scopes)
        secret = secrets.token_urlsafe(32)
        invitation_id = self._id()
        with self._access_uow(acting_actor_id, begin_mode="IMMEDIATE") as connection:
            admin_claim = self._authorize_assignment_management_in_connection(
                connection,
                acting_actor_id,
                person_id,
                requested_role=role,
                confirm_full_owner_access=confirm_full_owner_access,
            )
            if role == "owner" and not confirm_full_owner_access:
                raise ConfirmationRequiredError("owner_confirmation_required")
            connection.execute(
                """
                INSERT INTO access_invitations (
                    invitation_id, secret_hash, inviter_actor_id, person_id, role,
                    scopes_json, state, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    invitation_id,
                    hashlib.sha256(secret.encode("utf-8")).digest(),
                    acting_actor_id,
                    person_id,
                    role,
                    self._scopes_json(scopes),
                    self._timestamp(),
                    isoformat_utc(expires_at),
                ),
            )
            self._audit(
                connection,
                acting_actor_id,
                "invitation.create",
                "invitation",
                invitation_id,
                f"{role}_invitation",
            )
            if admin_claim:
                self._audit(
                    connection,
                    acting_actor_id,
                    "admin.unclaimed_person.invitation",
                    "person",
                    person_id,
                    "admin_owner_invitation",
                )
        return InvitationIssued(
            invitation_id=invitation_id,
            secret=secret,
            person_id=person_id,
            role=role,
            scopes=frozenset(scopes),
            expires_at=expires_at,
        )

    def revoke_invitation(self, acting_actor_id: str, person_id: str, invitation_id: str) -> None:
        now = self._timestamp()
        with self._access_uow(acting_actor_id, begin_mode="IMMEDIATE") as connection:
            decision, assignment = self._authorize_person_in_connection(
                connection, acting_actor_id, person_id, "access.manage"
            )
            invitation = connection.execute(
                """
                SELECT inviter_actor_id, role FROM access_invitations
                WHERE invitation_id = ? AND person_id = ?
                """,
                (invitation_id, person_id),
            ).fetchone()
            owner_can_revoke = (
                decision.allowed and assignment is not None and assignment.role == "owner"
            )
            repository = FamilyAccessRepository(connection)
            admin_claim_revoke = (
                not owner_can_revoke
                and invitation is not None
                and str(invitation["inviter_actor_id"]) == acting_actor_id
                and str(invitation["role"]) == "owner"
                and repository.is_active_admin(acting_actor_id)
                and self._active_owner_count(connection, person_id) == 0
                and connection.execute(
                    "SELECT 1 FROM people WHERE person_id = ? AND is_active = 1",
                    (person_id,),
                ).fetchone()
                is not None
            )
            if not owner_can_revoke and not admin_claim_revoke:
                raise PersonAccessDeniedError(person_id, "access.manage")
            cursor = connection.execute(
                """
                UPDATE access_invitations
                SET state = 'revoked', revoked_at = ?, revoked_by_actor_id = ?
                WHERE invitation_id = ? AND person_id = ? AND state = 'active'
                """,
                (now, acting_actor_id, invitation_id, person_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("invitation is unavailable")
            self._audit(
                connection,
                acting_actor_id,
                "invitation.revoke",
                "invitation",
                invitation_id,
                "invitation_revoked",
            )
            if admin_claim_revoke:
                self._audit(
                    connection,
                    acting_actor_id,
                    "admin.unclaimed_person.invitation_revoke",
                    "person",
                    person_id,
                    "admin_owner_invitation_revoke",
                )

    def preview_invitation(self, secret: str) -> InvitationPreview:
        with self.database.uow() as uow:
            assert uow.connection is not None
            row = self._valid_invitation(uow.connection, secret)
        if row is None:
            raise InvitationUnavailableError()
        return InvitationPreview(
            role=cast(AccessRole, str(row["role"])),
            scopes=frozenset(json.loads(str(row["scopes_json"]))),
            expires_at=parse_utc(str(row["expires_at"])),
        )

    def register_invitation(
        self,
        secret: str,
        *,
        username: str,
        display_name: str,
        password: str,
        confirm_full_owner_access: bool,
    ) -> ActorRecord:
        username_normalized = normalize_username(username)
        credential = hash_password(password)
        actor_id = self._id()
        now = self._timestamp()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            connection = uow.connection
            invitation = self._valid_invitation(connection, secret)
            if invitation is None:
                raise InvitationUnavailableError()
            role = cast(AccessRole, str(invitation["role"]))
            if role == "owner" and not confirm_full_owner_access:
                raise ConfirmationRequiredError("owner_confirmation_required")
            if connection.execute(
                "SELECT 1 FROM actors WHERE username_normalized = ?",
                (username_normalized,),
            ).fetchone() is not None:
                raise ConflictError("normalized username is already registered")
            connection.execute(
                """
                INSERT INTO actors (
                    actor_id, username_normalized, display_name, status, created_at
                ) VALUES (?, ?, ?, 'active', ?)
                """,
                (actor_id, username_normalized, self._clean_display_name(display_name), now),
            )
            self._insert_credential(connection, actor_id, credential, now)
            self._consume_invitation(connection, invitation, actor_id, now)
            self._audit(
                connection, actor_id, "actor.register", "actor", actor_id, "invitation_registration"
            )
            self._audit(
                connection,
                actor_id,
                "credential.create",
                "credential",
                None,
                "invitation_registration",
            )
        actor = self.get_actor(actor_id)
        assert actor is not None
        return actor

    def accept_invitation(
        self,
        actor_id: str,
        secret: str,
        *,
        confirm_full_owner_access: bool,
    ) -> AssignmentRecord:
        now = self._timestamp()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            self._require_active_actor_in_connection(uow.connection, actor_id)
            invitation = self._valid_invitation(uow.connection, secret)
            if invitation is None:
                raise InvitationUnavailableError()
            role = cast(AccessRole, str(invitation["role"]))
            if role == "owner" and not confirm_full_owner_access:
                raise ConfirmationRequiredError("owner_confirmation_required")
            assignment_id = self._consume_invitation(uow.connection, invitation, actor_id, now)
            scopes = frozenset(json.loads(str(invitation["scopes_json"])))
            return AssignmentRecord(
                assignment_id=assignment_id,
                actor_id=actor_id,
                person_id=str(invitation["person_id"]),
                role=role,
                scopes=scopes,
                is_active=True,
            )

    def create_family(self, actor_id: str, display_name: str) -> FamilyRecord:
        family_id = self._id()
        now = self._timestamp()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            self._require_active_actor_in_connection(uow.connection, actor_id)
            uow.connection.execute(
                """
                INSERT INTO families (
                    family_id, display_name, created_by_actor_id, created_at, is_archived
                ) VALUES (?, ?, ?, ?, 0)
                """,
                (family_id, self._clean_display_name(display_name), actor_id, now),
            )
            self._audit(
                uow.connection, actor_id, "family.create", "family", family_id, "family_created"
            )
        return FamilyRecord(
            family_id=family_id,
            display_name=self._clean_display_name(display_name),
            created_by_actor_id=actor_id,
            created_at=parse_utc(now),
            is_archived=False,
        )

    def list_families(self, actor_id: str) -> list[FamilyRecord]:
        with self.database.uow() as uow:
            assert uow.connection is not None
            self._require_active_actor_in_connection(uow.connection, actor_id)
            return self._list_families_in_connection(uow.connection, actor_id)

    def get_family(self, actor_id: str, family_id: str) -> dict[str, object]:
        with self.database.uow() as uow:
            assert uow.connection is not None
            connection = uow.connection
            self._require_active_actor_in_connection(connection, actor_id)
            families = {
                item.family_id: item
                for item in self._list_families_in_connection(connection, actor_id)
            }
            family = families.get(family_id)
            if family is None:
                raise NotFoundError("family is unavailable")
            membership_rows = connection.execute(
                "SELECT * FROM family_memberships WHERE family_id = ? AND is_active = 1",
                (family_id,),
            ).fetchall()
            visible_people = {
                str(row["person_id"])
                for row in membership_rows
                if self._authorize_person_in_connection(
                    connection, actor_id, str(row["person_id"]), "relationship.read"
                )[0].allowed
            }
            memberships = [
                {
                    "membership_id": str(row["membership_id"]),
                    "person_id": str(row["person_id"]),
                    "is_active": bool(row["is_active"]),
                }
                for row in membership_rows
                if str(row["person_id"]) in visible_people
            ]
            relationships = [
                {
                    "relationship_id": str(row["relationship_id"]),
                    "person_id": str(row["person_id"]),
                    "related_person_id": str(row["related_person_id"]),
                    "relationship_type": str(row["relationship_type"]),
                    "is_active": bool(row["is_active"]),
                }
                for row in connection.execute(
                    "SELECT * FROM person_relationships WHERE family_id = ? AND is_active = 1",
                    (family_id,),
                ).fetchall()
                if str(row["person_id"]) in visible_people
                and str(row["related_person_id"]) in visible_people
            ]
        return {"family": family, "memberships": memberships, "relationships": relationships}

    def _list_families_in_connection(
        self, connection: sqlite3.Connection, actor_id: str
    ) -> list[FamilyRecord]:
        rows = connection.execute(
            "SELECT * FROM families WHERE is_archived = 0 ORDER BY created_at, family_id"
        ).fetchall()
        visible: list[FamilyRecord] = []
        for row in rows:
            family_id = str(row["family_id"])
            if str(row["created_by_actor_id"]) == actor_id:
                visible.append(self._family(row))
                continue
            person_rows = connection.execute(
                "SELECT person_id FROM family_memberships "
                "WHERE family_id = ? AND is_active = 1",
                (family_id,),
            ).fetchall()
            if any(
                self._authorize_person_in_connection(
                    connection, actor_id, str(person[0]), "relationship.read"
                )[0].allowed
                for person in person_rows
            ):
                visible.append(self._family(row))
        return visible

    def add_membership(self, actor_id: str, family_id: str, person_id: str) -> MembershipRecord:
        membership_id = self._id()
        now = self._timestamp()
        with self._access_uow(actor_id, begin_mode="IMMEDIATE") as connection:
            self._require_person_access_in_connection(
                connection, actor_id, person_id, "relationship.manage"
            )
            self._require_family_mutable_in_connection(connection, family_id)
            self._require_family_visible_in_connection(connection, actor_id, family_id)
            if connection.execute(
                "SELECT 1 FROM family_memberships WHERE person_id = ? AND is_active = 1",
                (person_id,),
            ).fetchone() is not None:
                raise ConflictError("active membership already exists")
            connection.execute(
                """
                INSERT INTO family_memberships (
                    membership_id, family_id, person_id, created_by_actor_id,
                    is_active, created_at
                ) VALUES (?, ?, ?, ?, 1, ?)
                """,
                (membership_id, family_id, person_id, actor_id, now),
            )
            self._audit(
                connection,
                actor_id,
                "membership.create",
                "membership",
                membership_id,
                "family_membership_created",
            )
        return MembershipRecord(membership_id, family_id, person_id, True)

    def end_membership(self, actor_id: str, family_id: str, membership_id: str) -> None:
        now = self._timestamp()
        with self._access_uow(actor_id, begin_mode="IMMEDIATE") as connection:
            self._require_family_mutable_in_connection(connection, family_id)
            row = connection.execute(
                "SELECT person_id FROM family_memberships "
                "WHERE membership_id = ? AND family_id = ? AND is_active = 1",
                (membership_id, family_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("membership is unavailable")
            self._require_person_access_in_connection(
                connection, actor_id, str(row[0]), "relationship.manage"
            )
            connection.execute(
                """
                UPDATE family_memberships
                SET is_active = 0, ended_at = ?, ended_by_actor_id = ?
                WHERE membership_id = ?
                """,
                (now, actor_id, membership_id),
            )
            self._audit(
                connection,
                actor_id,
                "membership.end",
                "membership",
                membership_id,
                "family_membership_ended",
            )

    def create_relationship(
        self,
        actor_id: str,
        family_id: str,
        *,
        person_id: str,
        related_person_id: str,
        relationship_type: str,
    ) -> RelationshipRecord:
        relationship_id = self._id()
        now = self._timestamp()
        with self._access_uow(actor_id, begin_mode="IMMEDIATE") as connection:
            self._require_person_access_in_connection(
                connection, actor_id, person_id, "relationship.manage"
            )
            self._require_person_access_in_connection(
                connection, actor_id, related_person_id, "relationship.manage"
            )
            self._require_family_mutable_in_connection(connection, family_id)
            if connection.execute(
                """
                SELECT 1 FROM person_relationships
                WHERE family_id = ? AND person_id = ? AND related_person_id = ?
                      AND relationship_type = ? AND is_active = 1
                """,
                (family_id, person_id, related_person_id, relationship_type),
            ).fetchone() is not None:
                raise ConflictError("active relationship already exists")
            connection.execute(
                """
                INSERT INTO person_relationships (
                    relationship_id, family_id, person_id, related_person_id,
                    relationship_type, created_by_actor_id, is_active, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    relationship_id,
                    family_id,
                    person_id,
                    related_person_id,
                    relationship_type,
                    actor_id,
                    now,
                ),
            )
            self._audit(
                connection,
                actor_id,
                "relationship.create",
                "relationship",
                relationship_id,
                "relationship_created",
            )
        return RelationshipRecord(
            relationship_id, family_id, person_id, related_person_id, relationship_type, True
        )

    def end_relationship(self, actor_id: str, family_id: str, relationship_id: str) -> None:
        now = self._timestamp()
        with self._access_uow(actor_id, begin_mode="IMMEDIATE") as connection:
            self._require_family_mutable_in_connection(connection, family_id)
            row = connection.execute(
                "SELECT person_id, related_person_id FROM person_relationships "
                "WHERE relationship_id = ? AND family_id = ? AND is_active = 1",
                (relationship_id, family_id),
            ).fetchone()
            if row is None:
                raise NotFoundError("relationship is unavailable")
            self._require_person_access_in_connection(
                connection, actor_id, str(row[0]), "relationship.manage"
            )
            self._require_person_access_in_connection(
                connection, actor_id, str(row[1]), "relationship.manage"
            )
            connection.execute(
                """
                UPDATE person_relationships
                SET is_active = 0, ended_at = ?, ended_by_actor_id = ?
                WHERE relationship_id = ?
                """,
                (now, actor_id, relationship_id),
            )
            self._audit(
                connection,
                actor_id,
                "relationship.end",
                "relationship",
                relationship_id,
                "relationship_ended",
            )

    def archive_family(self, actor_id: str, family_id: str) -> None:
        now = self._timestamp()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            self._require_family_manage_in_connection(uow.connection, actor_id, family_id)
            cursor = uow.connection.execute(
                """
                UPDATE families
                SET is_archived = 1, archived_at = ?, archived_by_actor_id = ?
                WHERE family_id = ? AND is_archived = 0
                """,
                (now, actor_id, family_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError("family is unavailable")
            self._audit(
                uow.connection, actor_id, "family.archive", "family", family_id, "family_archived"
            )

    def deactivate_actor(self, acting_actor_id: str, target_actor_id: str) -> None:
        now = self._timestamp()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            connection = uow.connection
            self._require_admin_in_connection(connection, acting_actor_id)
            target = FamilyAccessRepository(connection).get_actor(target_actor_id)
            if target is None or target.status != "active":
                raise NotFoundError("Actor is unavailable")
            has_admin = connection.execute(
                "SELECT 1 FROM installation_admin_assignments WHERE actor_id = ? AND is_active = 1",
                (target_actor_id,),
            ).fetchone()
            if (
                has_admin is not None
                and connection.execute(
                    """
                    SELECT COUNT(*) FROM installation_admin_assignments AS iaa
                    JOIN actors AS a ON a.actor_id = iaa.actor_id
                    WHERE iaa.is_active = 1 AND a.status = 'active'
                    """
                ).fetchone()[0]
                <= 1
            ):
                raise LastAdministratorError("cannot disable the final administrator")
            assignments = connection.execute(
                "SELECT * FROM person_access_assignments WHERE actor_id = ? AND is_active = 1",
                (target_actor_id,),
            ).fetchall()
            for row in assignments:
                if (
                    str(row["role"]) == "owner"
                    and self._active_owner_count(connection, str(row["person_id"])) <= 1
                ):
                    raise LastOwnerError("cannot disable the final Person owner")
            own_links = connection.execute(
                "SELECT own_person_link_id, person_id FROM own_person_links "
                "WHERE actor_id = ? AND is_active = 1",
                (target_actor_id,),
            ).fetchall()
            connection.execute(
                """
                UPDATE own_person_links
                SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?
                WHERE actor_id = ? AND is_active = 1
                """,
                (now, acting_actor_id, target_actor_id),
            )
            for own_link in own_links:
                self._audit(
                    connection,
                    acting_actor_id,
                    "own_person_link.revoke",
                    "person",
                    str(own_link["person_id"]),
                    "actor_deactivated",
                )
            for row in assignments:
                self._insert_consent(
                    connection,
                    acting_actor_id=acting_actor_id,
                    recipient_actor_id=target_actor_id,
                    person_id=str(row["person_id"]),
                    role=cast(AccessRole, str(row["role"])),
                    scopes=frozenset(json.loads(str(row["scopes_json"]))),
                    event_type="revoke",
                    reason_code="actor_deactivated",
                    now=now,
                )
                connection.execute(
                    """
                    UPDATE person_access_assignments
                    SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?
                    WHERE assignment_id = ?
                    """,
                    (now, acting_actor_id, str(row["assignment_id"])),
                )
                self._audit(
                    connection,
                    acting_actor_id,
                    "assignment.revoke",
                    "assignment",
                    str(row["assignment_id"]),
                    "actor_deactivated",
                )
            admin_cursor = connection.execute(
                """
                UPDATE installation_admin_assignments
                SET is_active = 0, revoked_at = ?, revoked_by_actor_id = ?,
                    reason_code = 'actor_deactivated'
                WHERE actor_id = ? AND is_active = 1
                """,
                (now, acting_actor_id, target_actor_id),
            )
            if admin_cursor.rowcount:
                self._audit(
                    connection,
                    acting_actor_id,
                    "admin.revoke",
                    "actor",
                    target_actor_id,
                    "actor_deactivated",
                )
            connection.execute(
                """
                UPDATE actors
                SET status = 'disabled', disabled_at = ?, disabled_by_actor_id = ?
                WHERE actor_id = ? AND status = 'active'
                """,
                (now, acting_actor_id, target_actor_id),
            )
            self._audit(
                connection,
                acting_actor_id,
                "actor.deactivate",
                "actor",
                target_actor_id,
                "actor_deactivated",
            )
        self._invalidate_sessions(target_actor_id)

    def _consume_invitation(
        self,
        connection: sqlite3.Connection,
        invitation: sqlite3.Row,
        actor_id: str,
        now: str,
    ) -> str:
        role = cast(AccessRole, str(invitation["role"]))
        scopes = frozenset(json.loads(str(invitation["scopes_json"])))
        assignment_id = self._insert_assignment(
            connection,
            acting_actor_id=str(invitation["inviter_actor_id"]),
            recipient_actor_id=actor_id,
            person_id=str(invitation["person_id"]),
            role=role,
            scopes=scopes,
            event_type="accept",
            reason_code="invitation_accepted",
            now=now,
        )
        cursor = connection.execute(
            """
            UPDATE access_invitations
            SET state = 'redeemed', redeemed_at = ?, redeemed_by_actor_id = ?
            WHERE invitation_id = ? AND state = 'active'
            """,
            (now, actor_id, str(invitation["invitation_id"])),
        )
        if cursor.rowcount != 1:
            raise InvitationUnavailableError()
        self._audit(
            connection,
            actor_id,
            "invitation.redeem",
            "invitation",
            str(invitation["invitation_id"]),
            "invitation_accepted",
        )
        return assignment_id

    def _valid_invitation(self, connection: sqlite3.Connection, secret: str) -> sqlite3.Row | None:
        supplied_hash = hashlib.sha256(secret.encode("utf-8")).digest()
        result = connection.execute(
            "SELECT * FROM access_invitations WHERE secret_hash = ?",
            (supplied_hash,),
        ).fetchone()
        row: sqlite3.Row | None = result
        stored_hash = _DUMMY_INVITATION_HASH if row is None else bytes(row["secret_hash"])
        matches = hmac.compare_digest(supplied_hash, stored_hash)
        if (
            not matches
            or row is None
            or str(row["state"]) != "active"
            or parse_utc(str(row["expires_at"])) <= self._now()
        ):
            return None
        if connection.execute(
            "SELECT 1 FROM people WHERE person_id = ? AND is_active = 1",
            (str(row["person_id"]),),
        ).fetchone() is None:
            return None
        if connection.execute(
            "SELECT 1 FROM actors WHERE actor_id = ? AND status = 'active'",
            (str(row["inviter_actor_id"]),),
        ).fetchone() is None:
            return None
        try:
            scopes = json.loads(str(row["scopes_json"]))
        except (TypeError, ValueError):
            return None
        if not valid_role_scopes(str(row["role"]), scopes):
            return None
        inviter_actor_id = str(row["inviter_actor_id"])
        person_id = str(row["person_id"])
        inviter_decision, _ = self._authorize_person_in_connection(
            connection, inviter_actor_id, person_id, "access.manage"
        )
        if inviter_decision.allowed:
            return row
        admin_claim_is_still_valid = (
            str(row["role"]) == "owner"
            and FamilyAccessRepository(connection).is_active_admin(inviter_actor_id)
            and self._active_owner_count(connection, person_id) == 0
        )
        if not admin_claim_is_still_valid:
            return None
        return row

    def _insert_credential(
        self,
        connection: sqlite3.Connection,
        actor_id: str,
        credential: CredentialHash,
        now: str,
    ) -> str:
        credential_id = self._id()
        connection.execute(
            """
            INSERT INTO actor_credentials (
                credential_id, actor_id, algorithm, algorithm_version,
                salt, verifier, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                credential_id,
                actor_id,
                credential.algorithm,
                credential.algorithm_version,
                credential.salt,
                credential.verifier,
                now,
            ),
        )
        return credential_id

    def _insert_consent(
        self,
        connection: sqlite3.Connection,
        *,
        acting_actor_id: str,
        recipient_actor_id: str,
        person_id: str,
        role: AccessRole,
        scopes: Set[str],
        event_type: Literal["grant", "accept", "revise", "revoke", "expire"],
        reason_code: str,
        now: str,
    ) -> str:
        consent_id = self._id()
        connection.execute(
            """
            INSERT INTO person_access_consent_history (
                consent_event_id, event_type, acting_owner_actor_id,
                recipient_actor_id, person_id, role, scopes_json, reason_code, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                consent_id,
                event_type,
                acting_actor_id,
                recipient_actor_id,
                person_id,
                role,
                self._scopes_json(scopes),
                reason_code,
                now,
            ),
        )
        return consent_id

    def _insert_assignment(
        self,
        connection: sqlite3.Connection,
        *,
        acting_actor_id: str,
        recipient_actor_id: str,
        person_id: str,
        role: AccessRole,
        scopes: Set[str],
        event_type: Literal["grant", "accept", "revise", "revoke", "expire"],
        reason_code: str,
        now: str,
        revision_of_assignment_id: str | None = None,
    ) -> str:
        if not valid_role_scopes(role, scopes):
            raise ValidationError("assignment scopes are invalid")
        if connection.execute(
            """
            SELECT 1 FROM person_access_assignments
            WHERE actor_id = ? AND person_id = ? AND is_active = 1
            """,
            (recipient_actor_id, person_id),
        ).fetchone() is not None:
            raise ConflictError("active assignment already exists")
        consent_id = self._insert_consent(
            connection,
            acting_actor_id=acting_actor_id,
            recipient_actor_id=recipient_actor_id,
            person_id=person_id,
            role=role,
            scopes=scopes,
            event_type=event_type,
            reason_code=reason_code,
            now=now,
        )
        assignment_id = self._id()
        # scope_generation is DERIVED metadata: it always equals the value
        # inferred from the stored scopes (REFINEMENT 1).
        scope_generation = infer_generation(frozenset(scopes))
        connection.execute(
            """
            INSERT INTO person_access_assignments (
                assignment_id, actor_id, person_id, role, scopes_json,
                consent_event_id, granted_by_actor_id, is_active, granted_at,
                revision_of_assignment_id, scope_generation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                assignment_id,
                recipient_actor_id,
                person_id,
                role,
                self._scopes_json(scopes),
                consent_id,
                acting_actor_id,
                now,
                revision_of_assignment_id,
                scope_generation,
            ),
        )
        self._audit(
            connection,
            acting_actor_id,
            "assignment.create",
            "assignment",
            assignment_id,
            reason_code,
        )
        return assignment_id

    def _insert_own_link(
        self,
        connection: sqlite3.Connection,
        actor_id: str,
        person_id: str,
        acting_actor_id: str,
        now: str,
    ) -> str:
        if connection.execute(
            """
            SELECT 1 FROM own_person_links
            WHERE is_active = 1 AND (actor_id = ? OR person_id = ?)
            """,
            (actor_id, person_id),
        ).fetchone() is not None:
            raise ConflictError("active own-Person link already exists")
        link_id = self._id()
        connection.execute(
            """
            INSERT INTO own_person_links (
                own_person_link_id, actor_id, person_id, is_active, created_at
            ) VALUES (?, ?, ?, 1, ?)
            """,
            (link_id, actor_id, person_id, now),
        )
        self._audit(
            connection,
            acting_actor_id,
            "own_person_link.create",
            "person",
            person_id,
            "own_person_link_created",
        )
        return link_id

    @staticmethod
    def _active_owner_count(connection: sqlite3.Connection, person_id: str) -> int:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM person_access_assignments "
                "WHERE person_id = ? AND role = 'owner' AND is_active = 1",
                (person_id,),
            ).fetchone()[0]
        )

    def _require_family_visible(self, actor_id: str, family_id: str) -> None:
        if family_id not in {item.family_id for item in self.list_families(actor_id)}:
            raise NotFoundError("family is unavailable")

    def _require_family_visible_in_connection(
        self, connection: sqlite3.Connection, actor_id: str, family_id: str
    ) -> None:
        if family_id not in {
            family.family_id
            for family in self._list_families_in_connection(connection, actor_id)
        }:
            raise NotFoundError("family is unavailable")

    @staticmethod
    def _require_family_mutable_in_connection(
        connection: sqlite3.Connection, family_id: str
    ) -> None:
        if connection.execute(
            "SELECT 1 FROM families WHERE family_id = ? AND is_archived = 0",
            (family_id,),
        ).fetchone() is None:
            raise NotFoundError("family is unavailable")

    def _require_family_manage(self, actor_id: str, family_id: str) -> None:
        with self.database.connect() as connection:
            self._require_family_manage_in_connection(connection, actor_id, family_id)

    def _require_family_manage_in_connection(
        self, connection: sqlite3.Connection, actor_id: str, family_id: str
    ) -> None:
        self._require_active_actor_in_connection(connection, actor_id)
        family = connection.execute(
            "SELECT created_by_actor_id FROM families WHERE family_id = ? AND is_archived = 0",
            (family_id,),
        ).fetchone()
        if family is None:
            raise NotFoundError("family is unavailable")
        memberships = connection.execute(
            "SELECT person_id FROM family_memberships WHERE family_id = ? AND is_active = 1",
            (family_id,),
        ).fetchall()
        if not memberships:
            if str(family[0]) != actor_id:
                raise AuthorizationError("family management is unavailable")
            return
        if not any(
            self._authorize_person_in_connection(
                connection, actor_id, str(row[0]), "relationship.manage"
            )[0].allowed
            for row in memberships
        ):
            raise AuthorizationError("family management is unavailable")

    @staticmethod
    def _family(row: sqlite3.Row) -> FamilyRecord:
        return FamilyRecord(
            family_id=str(row["family_id"]),
            display_name=str(row["display_name"]),
            created_by_actor_id=str(row["created_by_actor_id"]),
            created_at=parse_utc(str(row["created_at"])),
            is_archived=bool(row["is_archived"]),
        )

    @staticmethod
    def _clean_display_name(value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 200:
            raise ValidationError("display name is invalid")
        return cleaned

    def _audit(
        self,
        connection: sqlite3.Connection,
        actor_id: str | None,
        action_code: str,
        target_class: str,
        target_id: str | None,
        reason_code: str,
        *,
        outcome: str = "success",
    ) -> None:
        self.audit_writer(
            connection,
            {
                "audit_event_id": self._id(),
                "actor_id": actor_id,
                "action_code": action_code,
                "target_class": target_class,
                "target_id": target_id,
                "outcome": outcome,
                "reason_code": reason_code,
                "created_at": self._timestamp(),
            },
        )

    @staticmethod
    def _default_audit_writer(connection: sqlite3.Connection, event: AuditEvent) -> None:
        connection.execute(
            """
            INSERT INTO access_audit_events (
                audit_event_id, actor_id, action_code, target_class, target_id,
                outcome, reason_code, created_at
            ) VALUES (
                :audit_event_id, :actor_id, :action_code, :target_class, :target_id,
                :outcome, :reason_code, :created_at
            )
            """,
            event,
        )

    def _best_effort_denial_audit(self, actor_id: str, person_id: str, required_scope: str) -> None:
        try:
            with self.database.uow() as uow:
                assert uow.connection is not None
                self._audit(
                    uow.connection,
                    actor_id,
                    "person_access.check",
                    "person",
                    person_id,
                    "person_access_denied",
                    outcome="denied",
                )
        except Exception:
            logger.error(
                "family_access_denial_audit_failed",
                extra={"reason_code": "denial_audit_storage_failure", "scope": required_scope},
                exc_info=False,
            )

    def _invalidate_sessions(self, actor_id: str) -> None:
        if self.session_invalidator is None:
            return
        try:
            self.session_invalidator(actor_id)
        except Exception:
            logger.error(
                "family_access_session_invalidation_failed",
                extra={"reason_code": "session_cleanup_failure"},
                exc_info=False,
            )
