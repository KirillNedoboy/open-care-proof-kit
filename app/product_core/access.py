from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import TypeVar

from app.family_access.api import AuthenticatedSession
from app.family_access.policy import PersonAccessPolicy, valid_role_scopes
from app.family_access.runtime import FamilyAccessRuntime
from app.product_core.errors import (
    AccessAuditUnavailableError,
    CandidateNotFoundError,
    NotFoundError,
    PersonNotFoundError,
    ScopeForbiddenError,
    SourceNotFoundError,
    VisitNotFoundError,
    VisitQuestionNotFoundError,
)
from app.product_core.models import Person
from app.product_core.runtime import ProductCoreRuntime

logger = logging.getLogger(__name__)
ErrorT = TypeVar("ErrorT", bound=NotFoundError)
MutationAuthorizer = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class ProductCoreAccess:
    """The sole Actor-to-Person authorization boundary for live Product Core."""

    runtime: ProductCoreRuntime
    family_runtime: FamilyAccessRuntime
    authenticated: AuthenticatedSession
    _authorization_cache: dict[tuple[object, ...], str] = field(
        default_factory=dict, compare=False, repr=False
    )

    @property
    def actor_id(self) -> str:
        return self.authenticated.actor.actor_id

    @property
    def active_person_id(self) -> str | None:
        return self.authenticated.record.active_person_id

    @property
    def policy(self) -> PersonAccessPolicy:
        return self.family_runtime.service.policy

    def list_people(self) -> list[Person]:
        with self.runtime.database.uow() as uow:
            assert uow.connection is not None
            rows = uow.connection.execute(
                """
                SELECT p.person_id
                FROM people AS p
                JOIN person_access_assignments AS paa
                  ON paa.person_id = p.person_id
                 AND paa.actor_id = ?
                 AND paa.is_active = 1
                JOIN actors AS a
                  ON a.actor_id = paa.actor_id
                 AND a.status = 'active'
                WHERE p.is_active = 1
                ORDER BY p.created_at, p.person_id
                """,
                (self.actor_id,),
            ).fetchall()
            people: list[Person] = []
            for row in rows:
                person_id = str(row["person_id"])
                if self._assignment_allows(uow.connection, person_id, ("person.read",)):
                    person = uow.people.get(person_id)
                    if person is not None:
                        people.append(person)
        self._best_effort_allowed_audit("person.list", None)
        return people

    def create_person(
        self,
        *,
        display_name: str,
        date_of_birth: date | None,
        confirm_owner_assignment: bool,
    ) -> str:
        return self.family_runtime.service.create_person(
            self.actor_id,
            display_name=display_name,
            date_of_birth=date_of_birth,
            confirm_owner_assignment=confirm_owner_assignment,
        )

    def require_person(
        self,
        person_id: str,
        *required_scopes: str,
        audit_action: str | None = None,
        required_audit: bool = False,
    ) -> str:
        return self._require_query(
            "SELECT p.person_id FROM people AS p "
            "WHERE p.person_id = ? AND p.is_active = 1",
            (person_id,),
            required_scopes,
            PersonNotFoundError,
            audit_action=audit_action,
            required_audit=required_audit,
        )

    def require_active_person(
        self,
        *required_scopes: str,
        audit_action: str | None = None,
        required_audit: bool = False,
    ) -> str:
        person_id = self.active_person_id
        if person_id is None:
            self._best_effort_denial_audit(None)
            raise PersonNotFoundError("Person was not found.")
        return self.require_person(
            person_id,
            *required_scopes,
            audit_action=audit_action,
            required_audit=required_audit,
        )

    def effective_scopes(self, person_id: str) -> frozenset[str]:
        """Return the current Actor's active assignment scopes on a Person.

        Read-only presentation metadata for the workspace capability map —
        never an authorization source. Mirrors ``require_person`` privacy
        semantics: a hidden or missing Person, or no active assignment for the
        current Actor, raises ``PersonNotFoundError`` (with a best-effort
        denial audit) and leaks nothing about other Actors, assignment history,
        or role names.
        """
        try:
            with self.runtime.database.uow() as uow:
                assert uow.connection is not None
                row = uow.connection.execute(
                    "SELECT p.person_id FROM people AS p "
                    "WHERE p.person_id = ? AND p.is_active = 1",
                    (person_id,),
                ).fetchone()
                resolved_person_id = None if row is None else str(row["person_id"])
                assignment_state = self._active_assignment_state(
                    uow.connection, resolved_person_id
                )
                if resolved_person_id is None or assignment_state is None:
                    raise PersonNotFoundError("Person was not found.")
                return assignment_state[1]
        except PersonNotFoundError:
            self._best_effort_denial_audit(None)
            raise

    def require_source(self, source_id: str, *required_scopes: str) -> str:
        """Resolve a source's owning Person server-side and require scopes.

        Mirrors require_source_for_person but resolves the owning Person from
        the sources table itself, so a source belonging to a Person the Actor
        cannot access (hidden or foreign) raises SourceNotFoundError — never a
        ScopeForbiddenError.
        """
        return self._require_query(
            """
            SELECT s.person_id
            FROM sources AS s
            JOIN people AS p ON p.person_id = s.person_id AND p.is_active = 1
            WHERE s.id = ?
            """,
            (source_id,),
            required_scopes,
            SourceNotFoundError,
        )

    def require_source_for_person(
        self,
        source_id: str,
        person_id: str,
        *required_scopes: str,
    ) -> str:
        return self._require_query(
            """
            SELECT s.person_id
            FROM sources AS s
            JOIN people AS p ON p.person_id = s.person_id AND p.is_active = 1
            WHERE s.id = ? AND s.person_id = ?
            """,
            (source_id, person_id),
            required_scopes,
            SourceNotFoundError,
        )

    def require_candidate(self, candidate_id: str, *required_scopes: str) -> str:
        return self._require_query(
            """
            SELECT c.person_id
            FROM candidate_facts AS c
            JOIN people AS p ON p.person_id = c.person_id AND p.is_active = 1
            WHERE c.id = ?
            """,
            (candidate_id,),
            required_scopes,
            CandidateNotFoundError,
        )

    def require_condition_record(self, record_id: str, *required_scopes: str) -> str:
        return self._require_query(
            """
            SELECT r.person_id
            FROM canonical_records AS r
            JOIN people AS p ON p.person_id = r.person_id AND p.is_active = 1
            WHERE r.id = ? AND r.fact_type = 'condition'
            """,
            (record_id,),
            required_scopes,
            NotFoundError,
        )

    def require_condition_candidate(self, candidate_id: str, *required_scopes: str) -> str:
        return self._require_query(
            """
            SELECT c.person_id
            FROM candidate_facts AS c
            JOIN people AS p ON p.person_id = c.person_id AND p.is_active = 1
            WHERE c.id = ? AND c.fact_type = 'condition'
            """,
            (candidate_id,),
            required_scopes,
            CandidateNotFoundError,
        )

    def require_lab_record(self, record_id: str, *required_scopes: str) -> str:
        return self._require_query(
            """
            SELECT r.person_id
            FROM canonical_records AS r
            JOIN people AS p ON p.person_id = r.person_id AND p.is_active = 1
            WHERE r.id = ? AND r.fact_type = 'lab'
            """,
            (record_id,),
            required_scopes,
            NotFoundError,
        )

    def require_lab_candidate(self, candidate_id: str, *required_scopes: str) -> str:
        return self._require_query(
            """
            SELECT c.person_id
            FROM candidate_facts AS c
            JOIN people AS p ON p.person_id = c.person_id AND p.is_active = 1
            WHERE c.id = ? AND c.fact_type = 'lab'
            """,
            (candidate_id,),
            required_scopes,
            CandidateNotFoundError,
        )

    def require_visit(self, visit_id: str, *required_scopes: str) -> str:
        return self._require_query(
            """
            SELECT v.person_id
            FROM visits AS v
            JOIN people AS p ON p.person_id = v.person_id AND p.is_active = 1
            WHERE v.visit_id = ?
            """,
            (visit_id,),
            required_scopes,
            VisitNotFoundError,
        )

    def require_question(self, question_id: str, *required_scopes: str) -> str:
        return self._require_query(
            """
            SELECT v.person_id
            FROM visit_questions AS q
            JOIN visits AS v ON v.visit_id = q.visit_id
            JOIN people AS p ON p.person_id = v.person_id AND p.is_active = 1
            WHERE q.question_id = ?
            """,
            (question_id,),
            required_scopes,
            VisitQuestionNotFoundError,
        )

    def require_brief_export(self, visit_id: str) -> str:
        return self._require_query(
            """
            SELECT v.person_id
            FROM visits AS v
            JOIN visit_briefs AS b ON b.visit_id = v.visit_id
            JOIN people AS p ON p.person_id = v.person_id AND p.is_active = 1
            WHERE v.visit_id = ?
            """,
            (visit_id,),
            ("brief.export",),
            VisitNotFoundError,
            audit_action="brief.export",
            required_audit=True,
        )

    def preflight_person(self, person_id: str, *required_scopes: str) -> str:
        return self._preflight_query(
            "SELECT p.person_id FROM people AS p "
            "WHERE p.person_id = ? AND p.is_active = 1",
            (person_id,),
            required_scopes,
            PersonNotFoundError,
        )

    def preflight_source_for_person(
        self,
        source_id: str,
        person_id: str,
        *required_scopes: str,
    ) -> str:
        return self._preflight_query(
            """
            SELECT s.person_id
            FROM sources AS s
            JOIN people AS p ON p.person_id = s.person_id AND p.is_active = 1
            WHERE s.id = ? AND s.person_id = ?
            """,
            (source_id, person_id),
            required_scopes,
            SourceNotFoundError,
        )

    def preflight_candidate(self, candidate_id: str, *required_scopes: str) -> str:
        return self._preflight_query(
            """
            SELECT c.person_id
            FROM candidate_facts AS c
            JOIN people AS p ON p.person_id = c.person_id AND p.is_active = 1
            WHERE c.id = ?
            """,
            (candidate_id,),
            required_scopes,
            CandidateNotFoundError,
        )

    def preflight_visit(self, visit_id: str, *required_scopes: str) -> str:
        return self._preflight_query(
            """
            SELECT v.person_id
            FROM visits AS v
            JOIN people AS p ON p.person_id = v.person_id AND p.is_active = 1
            WHERE v.visit_id = ?
            """,
            (visit_id,),
            required_scopes,
            VisitNotFoundError,
        )

    def preflight_question(self, question_id: str, *required_scopes: str) -> str:
        return self._preflight_query(
            """
            SELECT v.person_id
            FROM visit_questions AS q
            JOIN visits AS v ON v.visit_id = q.visit_id
            JOIN people AS p ON p.person_id = v.person_id AND p.is_active = 1
            WHERE q.question_id = ?
            """,
            (question_id,),
            required_scopes,
            VisitQuestionNotFoundError,
        )

    def authorize_person_mutation(
        self,
        person_id: str,
        *required_scopes: str,
        action: str | None = None,
    ) -> MutationAuthorizer:
        return self._mutation_authorizer(
            "SELECT p.person_id FROM people AS p "
            "WHERE p.person_id = ? AND p.is_active = 1",
            (person_id,),
            required_scopes,
            PersonNotFoundError,
            action=action,
        )

    def authorize_source_mutation(
        self,
        source_id: str,
        person_id: str,
        *required_scopes: str,
        action: str | None = None,
    ) -> MutationAuthorizer:
        return self._mutation_authorizer(
            """
            SELECT s.person_id
            FROM sources AS s
            JOIN people AS p ON p.person_id = s.person_id AND p.is_active = 1
            WHERE s.id = ? AND s.person_id = ?
            """,
            (source_id, person_id),
            required_scopes,
            SourceNotFoundError,
            action=action,
        )

    def authorize_candidate_mutation(
        self,
        candidate_id: str,
        *required_scopes: str,
        action: str | None = None,
    ) -> MutationAuthorizer:
        return self._mutation_authorizer(
            """
            SELECT c.person_id
            FROM candidate_facts AS c
            JOIN people AS p ON p.person_id = c.person_id AND p.is_active = 1
            WHERE c.id = ?
            """,
            (candidate_id,),
            required_scopes,
            CandidateNotFoundError,
            action=action,
        )

    def preflight_candidate_review(self, candidate_id: str) -> str:
        """Preflight a review decision with the fact-type-typed write scope."""
        with self.runtime.database.uow() as uow:
            assert uow.connection is not None
            return self._require_candidate_review_in_connection(
                uow.connection, candidate_id
            )

    def authorize_candidate_review_mutation(
        self,
        candidate_id: str,
        *,
        action: str,
    ) -> MutationAuthorizer:
        """Authorize a review decision inside the mutation transaction.

        The required write scope is derived from the candidate's fact_type in
        the same transaction (candidate.review + {fact_type}.write), so a
        reviewer can never confirm a fact family they were not granted.
        """

        def authorize(connection: sqlite3.Connection) -> None:
            person_id = self._require_candidate_review_in_connection(connection, candidate_id)
            self.family_runtime.service._audit(
                connection,
                self.actor_id,
                action,
                "person",
                person_id,
                "scope_granted",
            )

        return authorize

    def _require_candidate_review_in_connection(
        self,
        connection: sqlite3.Connection,
        candidate_id: str,
    ) -> str:
        row = connection.execute(
            """
            SELECT c.person_id, c.fact_type
            FROM candidate_facts AS c
            JOIN people AS p ON p.person_id = c.person_id AND p.is_active = 1
            WHERE c.id = ?
            """,
            (candidate_id,),
        ).fetchone()
        person_id = None if row is None else str(row["person_id"])
        # Always execute the assignment lookup, even for a missing resource, so a
        # hidden real identifier and an unknown identifier follow the same SQL shape.
        assignment_state = self._active_assignment_state(connection, person_id)
        if person_id is None or assignment_state is None:
            raise CandidateNotFoundError("Record was not found.")
        role, scopes = assignment_state
        mapping = {
            "actor_id": self.actor_id,
            "person_id": person_id,
            "role": role,
            "scopes": scopes,
            "is_active": True,
        }
        fact_type = str(row["fact_type"])
        write_scope = {
            "medication": "medication.write",
            "condition": "condition.write",
            "lab": "lab.write",
        }.get(fact_type)
        if write_scope is None:
            raise CandidateNotFoundError("Record was not found.")
        required_scopes = ("candidate.review", write_scope)
        if not all(
            self.policy.authorize(
                actor_id=self.actor_id,
                person_id=person_id,
                required_scope=scope,
                assignment=mapping,
            ).allowed
            for scope in required_scopes
        ):
            raise ScopeForbiddenError("Required scope is not granted.")
        return person_id

    def authorize_visit_mutation(
        self,
        visit_id: str,
        *required_scopes: str,
        action: str | None = None,
    ) -> MutationAuthorizer:
        return self._mutation_authorizer(
            """
            SELECT v.person_id
            FROM visits AS v
            JOIN people AS p ON p.person_id = v.person_id AND p.is_active = 1
            WHERE v.visit_id = ?
            """,
            (visit_id,),
            required_scopes,
            VisitNotFoundError,
            action=action,
        )

    def authorize_question_mutation(
        self,
        question_id: str,
        *required_scopes: str,
        action: str | None = None,
    ) -> MutationAuthorizer:
        return self._mutation_authorizer(
            """
            SELECT v.person_id
            FROM visit_questions AS q
            JOIN visits AS v ON v.visit_id = q.visit_id
            JOIN people AS p ON p.person_id = v.person_id AND p.is_active = 1
            WHERE q.question_id = ?
            """,
            (question_id,),
            required_scopes,
            VisitQuestionNotFoundError,
            action=action,
        )

    @staticmethod
    def combine_mutation_authorizers(
        *authorizers: MutationAuthorizer,
    ) -> MutationAuthorizer:
        def authorize(connection: sqlite3.Connection) -> None:
            for authorizer in authorizers:
                authorizer(connection)

        return authorize

    def audit_denial_best_effort(self, person_id: str | None = None) -> None:
        self._best_effort_denial_audit(person_id)

    def _require_query(
        self,
        resource_query: str,
        parameters: Sequence[object],
        required_scopes: Sequence[str],
        missing_error: type[ErrorT],
        *,
        audit_action: str | None = None,
        required_audit: bool = False,
    ) -> str:
        cache_key = (
            resource_query,
            tuple(parameters),
            tuple(required_scopes),
            audit_action,
            required_audit,
        )
        cached = self._authorization_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            with self.runtime.database.uow() as uow:
                assert uow.connection is not None
                person_id = self._require_query_in_connection(
                    uow.connection,
                    resource_query,
                    parameters,
                    required_scopes,
                    missing_error,
                )
        except (NotFoundError, ScopeForbiddenError):
            self._best_effort_denial_audit(None)
            raise

        action = audit_action or self._scope_action(required_scopes)
        if required_audit:
            self._required_allowed_audit(action, person_id, required_scopes)
        else:
            self._best_effort_allowed_audit(action, person_id)
        self._authorization_cache[cache_key] = person_id
        return person_id

    def _mutation_authorizer(
        self,
        resource_query: str,
        parameters: Sequence[object],
        required_scopes: Sequence[str],
        missing_error: type[ErrorT],
        *,
        action: str | None,
    ) -> MutationAuthorizer:
        def authorize(connection: sqlite3.Connection) -> None:
            person_id = self._require_query_in_connection(
                connection,
                resource_query,
                parameters,
                required_scopes,
                missing_error,
            )
            self.family_runtime.service._audit(
                connection,
                self.actor_id,
                action or self._scope_action(required_scopes),
                "person",
                person_id,
                "scope_granted",
            )

        return authorize

    def _preflight_query(
        self,
        resource_query: str,
        parameters: Sequence[object],
        required_scopes: Sequence[str],
        missing_error: type[ErrorT],
    ) -> str:
        with self.runtime.database.uow() as uow:
            assert uow.connection is not None
            return self._require_query_in_connection(
                uow.connection,
                resource_query,
                parameters,
                required_scopes,
                missing_error,
            )

    def _require_query_in_connection(
        self,
        connection: sqlite3.Connection,
        resource_query: str,
        parameters: Sequence[object],
        required_scopes: Sequence[str],
        missing_error: type[ErrorT],
    ) -> str:
        row = connection.execute(resource_query, parameters).fetchone()
        person_id = None if row is None else str(row["person_id"])
        # Always execute the assignment lookup, even for a missing resource, so a
        # hidden real identifier and an unknown identifier follow the same SQL shape.
        assignment_state = self._active_assignment_state(connection, person_id)
        if person_id is None or assignment_state is None:
            raise missing_error("Record was not found.")
        role, scopes = assignment_state
        mapping = {
            "actor_id": self.actor_id,
            "person_id": person_id,
            "role": role,
            "scopes": scopes,
            "is_active": True,
        }
        if not all(
            self.policy.authorize(
                actor_id=self.actor_id,
                person_id=person_id,
                required_scope=scope,
                assignment=mapping,
            ).allowed
            for scope in required_scopes
        ):
            raise ScopeForbiddenError("Required scope is not granted.")
        return person_id

    def _assignment_allows(
        self,
        connection: sqlite3.Connection,
        person_id: str,
        required_scopes: Sequence[str],
    ) -> bool:
        state = self._active_assignment_state(connection, person_id)
        if state is None:
            return False
        role, scopes = state
        mapping = {
            "actor_id": self.actor_id,
            "person_id": person_id,
            "role": role,
            "scopes": scopes,
            "is_active": True,
        }
        return all(
            self.policy.authorize(
                actor_id=self.actor_id,
                person_id=person_id,
                required_scope=scope,
                assignment=mapping,
            ).allowed
            for scope in required_scopes
        )

    def _active_assignment_state(
        self, connection: sqlite3.Connection, person_id: str | None
    ) -> tuple[str, frozenset[str]] | None:
        row = connection.execute(
            """
            SELECT paa.role, paa.scopes_json
            FROM person_access_assignments AS paa
            JOIN actors AS a ON a.actor_id = paa.actor_id AND a.status = 'active'
            JOIN people AS p ON p.person_id = paa.person_id AND p.is_active = 1
            WHERE paa.actor_id = ? AND paa.person_id = ? AND paa.is_active = 1
            """,
            (self.actor_id, person_id),
        ).fetchone()
        if row is None:
            return None
        from app.family_access.repository import deserialize_scopes

        role = str(row["role"])
        scopes = deserialize_scopes(row["scopes_json"])
        if not isinstance(scopes, frozenset) or not valid_role_scopes(role, scopes):
            return None
        return role, scopes

    def _required_allowed_audit(
        self, action: str, person_id: str, required_scopes: Sequence[str]
    ) -> None:
        try:
            with self.runtime.database.uow(begin_mode="IMMEDIATE") as uow:
                assert uow.connection is not None
                if not self._assignment_allows(
                    uow.connection, person_id, required_scopes
                ):
                    raise ScopeForbiddenError("Required scope is not granted.")
                self.family_runtime.service._audit(
                    uow.connection,
                    self.actor_id,
                    action,
                    "person",
                    person_id,
                    "scope_granted",
                )
        except ScopeForbiddenError:
            self._best_effort_denial_audit(person_id)
            raise
        except Exception as exc:
            raise AccessAuditUnavailableError(
                "Sensitive access could not be audited."
            ) from exc

    def _best_effort_allowed_audit(self, action: str, person_id: str | None) -> None:
        try:
            with self.runtime.database.uow() as uow:
                assert uow.connection is not None
                self.family_runtime.service._audit(
                    uow.connection,
                    self.actor_id,
                    action,
                    "person",
                    person_id,
                    "scope_granted",
                )
        except Exception:
            logger.error(
                "product_core_access_audit_failed",
                extra={"reason_code": "allowed_audit_storage_failure", "action": action},
                exc_info=False,
            )

    def _best_effort_denial_audit(self, person_id: str | None) -> None:
        try:
            with self.runtime.database.uow() as uow:
                assert uow.connection is not None
                self.family_runtime.service._audit(
                    uow.connection,
                    self.actor_id,
                    "person_access.check",
                    "person",
                    person_id,
                    "person_access_denied",
                    outcome="denied",
                )
        except Exception:
            logger.error(
                "product_core_denial_audit_failed",
                extra={"reason_code": "denial_audit_storage_failure"},
                exc_info=False,
            )

    @staticmethod
    def _scope_action(scopes: Sequence[str]) -> str:
        if not scopes:
            return "person_access.check"
        return scopes[0] if len(scopes) == 1 else "+".join(scopes)
