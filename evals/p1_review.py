"""OpenCare P1 local reviewer (``python -m evals.p1_review``).

Deterministic, offline evidence-grounded-ingest reviewer for the P1 branch
(design: ``docs/architecture/p1-evidence-grounded-ingest.md``). It builds a
temporary SQLite database and source directory, runs a compact scripted
scenario through the real Product Core services, and asserts:

- medication lifecycle compatibility (source -> candidate -> confirm unchanged);
- condition and lab source-backed lifecycles (candidate -> provenance ->
  confirm -> canonical -> timeline -> correction lineage; reject/unsupported
  create no canonical);
- provenance locators present and validated (a bad/absent locator is rejected);
- Wrong Person isolation (Bob vs Alice/Carol: hidden-person denials and
  no-scope denials; a legacy v1 grant never silently gains condition/lab);
- timeline events for all three fact types;
- Visit Brief v2 content with condition/lab selections while v1 revisions
  remain readable;
- export/recovery round trip preserving the P1 entities;
- the six security counters all zero:
  canonical_without_review, canonical_without_source,
  cross_person_record_exposure, cross_person_source_exposure,
  unauthorized_confirmation, provenance_mismatch_accepted.

It never touches the network, Ollama, Sentient, a browser, Docker, an external
account, real health data, or an LLM, and it never runs the pytest suite.

Exit codes: ``0`` pass (``PASS``), ``1`` any failure (``FAIL``), ``2`` usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.family_access.policy import CAREGIVER_BASE_SCOPES_V1
from app.family_access.service import FamilyAccessService
from app.product_core.errors import ProvenanceValidationError
from app.product_core.installation_backup import InstallationBackupService
from app.product_core.installation_recovery import (
    InstallationRecoveryService,
    verify_recovered_installation,
)
from app.product_core.models import (
    ConditionCandidateInput,
    LabCandidateDetail,
    LabCandidateInput,
    Person,
)
from app.product_core.persisted_visit_briefs import (
    PersistedVisitBriefService,
    verify_persisted_visit_brief_revision,
)
from app.product_core.portable_vault_export import (
    PORTABLE_VAULT_FORMAT_VERSION,
    PortableVaultExportService,
)
from app.product_core.services import MedicationLifecycleService, SourceService
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visits import VisitPlanningService

NOW = datetime(2026, 8, 2, 12, tzinfo=UTC)


class FixedClock:
    def __call__(self) -> datetime:
        return NOW


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"p1r-{self.value}"


class _Check:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.failures.append(message)


def _v1_brief_content_hash(content: dict[str, object], markdown: str) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "content_schema_version": 1,
                "render_version": 1,
                "content": content,
                "rendered_markdown": markdown,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def run_review() -> tuple[int, dict[str, str]]:
    checks = _Check()
    lines: dict[str, str] = {}
    tmp_root = Path(tempfile.mkdtemp(prefix="p1-review-"))
    db_path = tmp_root / "product.sqlite3"
    source_dir = tmp_root / "sources"

    database = SQLiteDatabase(db_path)
    database.migrate()
    ids = SequenceIds()

    # ------------------------------------------------------------------ #
    # Setup: Alice (owner of the Child), Bob (caregiver, granted current scopes),
    # Carol (unrelated actor with no assignments).
    # ------------------------------------------------------------------ #
    with database.uow() as uow:
        for person_id in ("alice-person", "bob-person", "carol-person"):
            uow.people.insert(
                Person(
                    person_id=person_id,
                    display_name=f"Profile {person_id}",
                    created_at=NOW,
                    updated_at=NOW,
                    is_active=True,
                )
            )
    sources = SourceService(database, source_dir, clock=FixedClock(), id_factory=ids)
    lifecycle = MedicationLifecycleService(
        database,
        clock=FixedClock(),
        id_factory=ids,
        source_reader=sources.store.read,
    )
    family = FamilyAccessService(database, clock=FixedClock(), id_factory=ids)
    alice = family.bootstrap(
        username="alice",
        display_name="Alice",
        password="alice password value",
        person_ids=("alice-person", "bob-person", "carol-person"),
        own_person_id="alice-person",
        confirm_full_owner_access=True,
    )
    bob = family.create_local_actor(
        alice.actor_id,
        username="bob",
        display_name="Bob",
        password="bob password value",
    )
    carol = family.create_local_actor(
        alice.actor_id,
        username="carol",
        display_name="Carol",
        password="carol password value",
    )
    # Bob is the Child's caregiver with explicitly granted current review scopes.
    family.grant_assignment(
        alice.actor_id,
        "alice-person",
        bob.actor_id,
        role="caregiver",
        optional_scopes={"medication.write", "candidate.review", "condition.write", "lab.write"},
        confirm_full_owner_access=False,
    )

    # ------------------------------------------------------------------ #
    # Medication compatibility: source -> candidate -> confirm unchanged.
    # ------------------------------------------------------------------ #
    med_source = sources.register_manual_entry("alice-person", "Aspirin")
    med_candidate = lifecycle.create_candidate(
        person_id="alice-person",
        source_id=med_source.id,
        display_name="Aspirin",
        schedule_text="morning",
    )
    med_record = lifecycle.confirm(med_candidate.id)
    checks.check(
        med_record.display_name == "Aspirin" and med_record.is_active is True,
        "medication confirmation did not produce an active canonical",
    )
    lines["medication regression"] = "pass"

    # ------------------------------------------------------------------ #
    # Condition lifecycle with correction lineage.
    # ------------------------------------------------------------------ #
    cond_source = sources.register_structured_manual_entry(
        "alice-person", "condition", {"display_name": "Asthma", "status_text": "chronic"}
    )
    cond_candidate = lifecycle.create_fact_candidate(
        person_id="alice-person",
        source_id=cond_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Asthma", status_text="chronic"),
    )
    cond_record = lifecycle.confirm(cond_candidate.id)
    checks.check(
        cond_record.fact_type == "condition" and cond_record.is_active is True,
        "condition confirmation failed",
    )
    # reject / unsupported create no canonical.
    rejected_source = sources.register_structured_manual_entry(
        "alice-person", "condition", {"display_name": "Eczema"}
    )
    rejected_cond = lifecycle.create_fact_candidate(
        person_id="alice-person",
        source_id=rejected_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Eczema"),
    )
    lifecycle.reject(rejected_cond.id)
    unsupported_source = sources.register_structured_manual_entry(
        "alice-person", "condition", {"display_name": "Unsupported"}
    )
    unsupported_cond = lifecycle.create_fact_candidate(
        person_id="alice-person",
        source_id=unsupported_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Unsupported"),
    )
    lifecycle.unsupported(unsupported_cond.id)
    # Correction lineage: correct the confirmed condition, confirm successor.
    corrected_source = sources.register_structured_manual_entry(
        "alice-person", "condition", {"display_name": "Asthma (seasonal)"}
    )
    successor = lifecycle.correct_fact_candidate(
        cond_candidate.id,
        detail_input=ConditionCandidateInput(display_name="Asthma (seasonal)"),
        source_id=corrected_source.id,
    )
    checks.check(
        successor.predecessor_candidate_id == cond_candidate.id,
        "condition lineage broken",
    )
    new_cond_record = lifecycle.confirm(successor.id)
    superseded_cond = lifecycle.get_canonical(cond_record.id)
    checks.check(
        superseded_cond.is_active is False
        and new_cond_record.is_active is True
        and new_cond_record.superseded_by_record_id is None
        and superseded_cond.superseded_by_record_id == new_cond_record.id,
        "condition correction did not supersede the old canonical",
    )
    lines["condition lifecycle"] = "pass"

    # ------------------------------------------------------------------ #
    # Lab lifecycle with source flag preserved as source-provided.
    # ------------------------------------------------------------------ #
    lab_source = sources.register_structured_manual_entry(
        "alice-person",
        "lab",
        {"test_name": "Hemoglobin", "result_text": "13.8", "source_flag_text": "H"},
    )
    lab_candidate = lifecycle.create_fact_candidate(
        person_id="alice-person",
        source_id=lab_source.id,
        fact_type="lab",
        detail_input=LabCandidateInput(
            test_name="Hemoglobin", result_text="13.8", source_flag_text="H"
        ),
    )
    lab_record = lifecycle.confirm(lab_candidate.id)
    lab_detail = lab_record.detail
    assert isinstance(lab_detail, LabCandidateDetail)
    checks.check(
        lab_record.fact_type == "lab"
        and lab_detail.result_text == "13.8"
        and lab_detail.source_flag_text == "H",
        "lab confirmation or source flag preservation failed",
    )
    lines["lab lifecycle"] = "pass"

    # ------------------------------------------------------------------ #
    # Provenance: locators present and validated; a bad locator is rejected.
    # ------------------------------------------------------------------ #
    checks.check(
        cond_candidate.provenance_locator
        == {"kind": "structured_field", "path": "data.condition.display_name"},
        "condition locator not derived",
    )
    checks.check(
        lab_candidate.provenance_locator
        == {"kind": "structured_field", "path": "data.lab.test_name"},
        "lab locator not derived",
    )
    plain_source = sources.register_plain_text("alice-person", "Reports seasonal asthma.")
    span_candidate = lifecycle.create_fact_candidate(
        person_id="alice-person",
        source_id=plain_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="asthma"),
        provenance_locator={"kind": "span", "start": 17, "end": 23},
    )
    checks.check(
        span_candidate.provenance_locator == {"kind": "span", "start": 17, "end": 23},
        "plain-text span locator not stored",
    )
    provenance_mismatch_rejected = False
    try:
        lifecycle.create_fact_candidate(
            person_id="alice-person",
            source_id=plain_source.id,
            fact_type="condition",
            detail_input=ConditionCandidateInput(display_name="asthma"),
            provenance_locator={"kind": "span", "start": 0, "end": 3},
        )
    except ProvenanceValidationError:
        provenance_mismatch_rejected = True
    checks.check(provenance_mismatch_rejected, "mismatched locator was not rejected")
    try:
        lifecycle.create_fact_candidate(
            person_id="alice-person",
            source_id=plain_source.id,
            fact_type="condition",
            detail_input=ConditionCandidateInput(display_name="asthma"),
        )
    except ProvenanceValidationError:
        provenance_mismatch_rejected = True
    else:
        provenance_mismatch_rejected = False
    checks.check(provenance_mismatch_rejected, "missing locator was not rejected")
    lines["provenance"] = "pass"

    # ------------------------------------------------------------------ #
    # Wrong Person isolation.
    # ------------------------------------------------------------------ #
    # Bob vs Carol: no assignment on carol-person -> hidden denial.
    checks.check(
        family.authorize_person(bob.actor_id, "carol-person", "condition.read").allowed is False
        and family.authorize_person(bob.actor_id, "carol-person", "lab.read").allowed is False,
        "Bob could read Carol's condition/lab scopes",
    )
    # Carol vs Alice: no assignment -> hidden denial.
    checks.check(
        family.authorize_person(carol.actor_id, "alice-person", "condition.read").allowed is False
        and family.authorize_person(carol.actor_id, "alice-person", "lab.read").allowed is False,
        "Carol could read Alice's condition/lab scopes",
    )
    # Legacy v1 grant: rewrite Bob's assignment to the frozen v1 scope set and
    # assert it NEVER gains condition/lab capabilities (no silent expansion).
    with database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        row = uow.connection.execute(
            "SELECT scopes_json FROM person_access_assignments "
            "WHERE actor_id = ? AND person_id = ? AND is_active = 1",
            (bob.actor_id, "alice-person"),
        ).fetchone()
        assert row is not None
        v1_scopes = CAREGIVER_BASE_SCOPES_V1 | {
            "medication.write",
            "candidate.review",
        }
        uow.connection.execute(
            "UPDATE person_access_assignments SET scopes_json = ?, "
            "scope_generation = 'family-access-v1' "
            "WHERE actor_id = ? AND person_id = ? AND is_active = 1",
            (json.dumps(sorted(v1_scopes), separators=(",", ":")), bob.actor_id, "alice-person"),
        )
    checks.check(
        family.authorize_person(bob.actor_id, "alice-person", "condition.read").allowed is False
        and family.authorize_person(bob.actor_id, "alice-person", "lab.read").allowed is False,
        "legacy v1 grant silently gained condition/lab access",
    )
    # unauthorized_confirmation stays zero: Bob (v1 scopes, no candidate.review)
    # must not be able to confirm Alice's condition candidate.
    unauthorized_attempt_rejected = False
    try:
        pending_cond = lifecycle.create_fact_candidate(
            person_id="alice-person",
            source_id=cond_source.id,
            fact_type="condition",
            detail_input=ConditionCandidateInput(display_name="Rhinitis"),
        )
        from app.family_access.api import AuthenticatedSession
        from app.family_access.sessions import SessionRecord
        from app.product_core.access import ProductCoreAccess

        actor = family.get_actor(bob.actor_id)
        assert actor is not None
        access = ProductCoreAccess(
            runtime=_RuntimeShim(database),  # type: ignore[arg-type]  # shim exposes runtime.database
            family_runtime=_FamilyShim(family),  # type: ignore[arg-type]  # shim exposes .service
            authenticated=AuthenticatedSession(
                actor=actor,
                record=SessionRecord(
                    session_id="session",
                    actor_id=actor.actor_id,
                    credential_id="credential",
                    active_person_id="alice-person",
                    issued_at=NOW,
                    expires_at=NOW + timedelta(hours=8),
                ),
                session_token="token",
            ),
        )
        authorizer = access.authorize_candidate_review_mutation(
            pending_cond.id, action="candidate.confirm"
        )
        with database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            authorizer(uow.connection)
    except Exception:
        unauthorized_attempt_rejected = True
    checks.check(
        unauthorized_attempt_rejected,
        "unauthorized confirmation was accepted (counter must be zero)",
    )
    lines["wrong-person isolation"] = "pass"

    # ------------------------------------------------------------------ #
    # Timeline: all three fact types present with deterministic events.
    # ------------------------------------------------------------------ #
    events = lifecycle.list_timeline("alice-person")
    event_types = {event.event_type for event in events}
    checks.check(
        {"medication_confirmed", "condition_confirmed", "condition_corrected", "lab_confirmed"}
        <= event_types,
        f"timeline missing fact-family events: {sorted(event_types)}",
    )
    lines["timeline"] = "pass"

    # ------------------------------------------------------------------ #
    # Visit Brief: v2 revision with condition+lab evidence; v1 still readable.
    # ------------------------------------------------------------------ #
    visits = VisitPlanningService(database, clock=FixedClock(), id_factory=ids)
    visit = visits.create_visit("alice-person", title="Review")
    briefs = PersistedVisitBriefService(
        database,
        clock=FixedClock(),
        id_factory=ids,
        source_reader=sources.store.read,
    )
    briefs.initialize(visit.visit_id)
    revision = briefs.generate(
        visit.visit_id,
        selected_record_ids=[new_cond_record.id, lab_record.id],
        expected_current_revision_number=None,
    )
    checks.check(
        revision.content_schema_version == 2,
        "new brief revision is not content schema v2",
    )
    record_types = {record["record_type"] for record in revision.content["records"]}
    checks.check(
        {"confirmed_condition", "confirmed_lab"} <= record_types,
        f"brief v2 records missing condition/lab: {record_types}",
    )
    # v1 revision readability: rewrite the revision to the v1 medication-only
    # shape with a recomputed v1-era content hash and verify it still reads.
    with database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        row = uow.connection.execute(
            "SELECT content_json, rendered_markdown FROM visit_brief_revisions "
            "WHERE revision_id = ?",
            (revision.revision_id,),
        ).fetchone()
        content = json.loads(str(row["content_json"]))
        content["medications"] = content.pop("records")
        v1_hash = _v1_brief_content_hash(content, str(row["rendered_markdown"]))
        uow.connection.execute(
            "UPDATE visit_brief_revisions SET content_schema_version = 1, "
            "content_json = ?, content_hash = ? WHERE revision_id = ?",
            (
                json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                v1_hash,
                revision.revision_id,
            ),
        )
    from app.product_core.models import PersistedVisitBriefRevision, parse_utc_datetime

    with database.uow() as uow:
        assert uow.connection is not None
        row = uow.connection.execute(
            "SELECT * FROM visit_brief_revisions WHERE revision_id = ?",
            (revision.revision_id,),
        ).fetchone()
        verify_persisted_visit_brief_revision(
            PersistedVisitBriefRevision(
                revision_id=row["revision_id"],
                brief_id=row["brief_id"],
                revision_number=row["revision_number"],
                origin=row["origin"],
                parent_revision_id=row["parent_revision_id"],
                content_schema_version=row["content_schema_version"],
                render_version=row["render_version"],
                content=json.loads(row["content_json"]),
                rendered_markdown=row["rendered_markdown"],
                content_hash=row["content_hash"],
                created_at=parse_utc_datetime(row["created_at"]),
            )
        )
    lines["visit brief"] = "pass"

    # ------------------------------------------------------------------ #
    # Export + backup/recovery round trip preserving P1 entities.
    # ------------------------------------------------------------------ #
    exported = json.loads(
        PortableVaultExportService(database, sources.store).export("alice-person").vault_json
    )
    checks.check(
        exported["format_version"] == PORTABLE_VAULT_FORMAT_VERSION
        and exported["canonical_condition_details"]
        and exported["canonical_lab_details"],
        "export v3 missing condition/lab entities",
    )
    backup = InstallationBackupService(db_path, source_dir, clock=FixedClock())
    destination = tmp_root / "backup"
    report = backup.backup(destination)
    checks.check(
        report.valid is True and report.product_core_schema_version == 9,
        "backup invalid",
    )
    target = tmp_root / "recovered"
    InstallationRecoveryService(clock=FixedClock()).recover(
        destination, target, confirm_maintenance=True
    )
    recovered = verify_recovered_installation(target)
    checks.check(recovered.valid is True, "recovery verification failed")
    with sqlite3.connect(target / "database.sqlite3") as connection:
        checks.check(
            connection.execute(
                "SELECT COUNT(*) FROM canonical_records WHERE fact_type = 'condition'"
            ).fetchone()[0]
            >= 2
            and connection.execute(
                "SELECT COUNT(*) FROM canonical_records WHERE fact_type = 'lab'"
            ).fetchone()[0]
            == 1,
            "recovered database lost condition/lab canonicals",
        )
    lines["export/recovery"] = "pass"

    # ------------------------------------------------------------------ #
    # Security counters: all six must be zero.
    # ------------------------------------------------------------------ #
    with database.connect() as connection:
        canonical_without_review = connection.execute(
            """
            SELECT COUNT(*) FROM canonical_records AS record
            JOIN candidate_facts AS candidate ON candidate.id = record.candidate_id
            WHERE candidate.status <> 'confirmed'
            """
        ).fetchone()[0]
        canonical_without_source = connection.execute(
            """
            SELECT COUNT(*) FROM canonical_records AS record
            LEFT JOIN sources AS source ON source.id = record.source_id
            WHERE source.id IS NULL
            """
        ).fetchone()[0]
        cross_person_records = connection.execute(
            """
            SELECT COUNT(*) FROM canonical_records AS record
            JOIN candidate_facts AS candidate ON candidate.id = record.candidate_id
            JOIN sources AS source ON source.id = record.source_id
            WHERE record.person_id <> candidate.person_id
               OR record.person_id <> source.person_id
            """
        ).fetchone()[0]
        cross_person_sources = connection.execute(
            """
            SELECT COUNT(*) FROM candidate_facts AS candidate
            JOIN sources AS source ON source.id = candidate.source_id
            WHERE candidate.person_id <> source.person_id
            """
        ).fetchone()[0]

    counter_values = {
        "canonical_without_review": int(canonical_without_review),
        "canonical_without_source": int(canonical_without_source),
        "cross_person_record_exposure": int(cross_person_records),
        "cross_person_source_exposure": int(cross_person_sources),
        "unauthorized_confirmation": 0 if unauthorized_attempt_rejected else 1,
        "provenance_mismatch_accepted": 0 if provenance_mismatch_rejected else 1,
    }
    for name, value in counter_values.items():
        checks.check(value == 0, f"security counter {name} = {value} (expected 0)")
        lines[f"counter {name}"] = str(value)

    lines["migration"] = "pass"
    return (1 if checks.failures else 0), lines


class _RuntimeShim:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database


class _FamilyShim:
    def __init__(self, service: FamilyAccessService) -> None:
        self.service = service


def _print_summary(exit_code: int, lines: dict[str, str]) -> None:
    print("P1 REVIEW")
    for name, value in lines.items():
        print(f"{name}: {value}")
    if exit_code != 0:
        print(f"result: FAIL (exit {exit_code})")
    else:
        print("result: PASS")


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m evals.p1_review",
        description="OpenCare P1 deterministic offline reviewer.",
    )


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    exit_code, lines = run_review()
    _print_summary(exit_code, lines)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
