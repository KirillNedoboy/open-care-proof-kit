"""OpenCare P2 local reviewer (``python -m evals.p2_review``).

Deterministic, offline reviewer for the P2 "OpenCare Health Workspace" contract
(design: ``docs/architecture/p2-usable-family-workspace.md``). It builds a
temporary SQLite database and source directory, runs a compact scripted
scenario through the real Product Core services and the real
``ProductCoreAccess`` authorization boundary, and asserts the workspace
capability / usability / security contract:

- workspace capability calculation via ``ProductCoreAccess.effective_scopes``
  (owner all-true, bounded caregiver set, read-only caregiver, hidden Person
  fails closed, legacy v1 grants never gain condition/lab);
- current-vs-historical record grouping after a medication correction chain
  (``is_active`` / ``superseded_by_record_id``);
- unified pending review across fact families (rejected/unsupported are never
  canonical; a pending correction candidate exists);
- Person-isolated source provenance metadata via the safe shape (no filesystem
  path, no payload, no other-Person metadata);
- timeline readability mapping applied without mutating stored event codes;
- Visit + Questions + a three-family Visit Brief (content schema v2) with v1
  revisions still readable;
- export filename/version coherence (``PORTABLE_VAULT_FORMAT_VERSION == 4``,
  server ``Content-Disposition`` derives from the constant);
- revocation fail-closed, and the six P2 security counters all zero.

It never touches the network, Ollama, Sentient, a browser, Docker, an external
account, real health data, or an LLM, and it never runs the pytest suite.

Exit codes: ``0`` pass (``PASS``), ``1`` any failure (``FAIL``), ``2`` usage.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import tempfile
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

from app.config import Settings
from app.family_access import policy as family_policy
from app.family_access.policy import (
    CAREGIVER_BASE_SCOPES_V1,
    CAREGIVER_BASE_SCOPES_V3,
    OWNER_SCOPES_V3,
    build_scopes,
)
from app.family_access.runtime import FamilyAccessRuntime
from app.family_access.service import FamilyAccessService
from app.family_access.sessions import SessionStore
from app.product_core import migrations as product_migrations
from app.product_core.access import ProductCoreAccess
from app.product_core.errors import (
    PersonNotFoundError,
    SourceNotFoundError,
)
from app.product_core.genetics import GeneticsService
from app.product_core.models import (
    ConditionCandidateInput,
    LabCandidateDetail,
    LabCandidateInput,
    PersistedVisitBriefRevision,
    Person,
    Source,
    parse_utc_datetime,
)
from app.product_core.persisted_visit_briefs import (
    CONTENT_SCHEMA_VERSION,
    SUPPORTED_CONTENT_SCHEMA_VERSIONS,
    PersistedVisitBriefService,
    verify_persisted_visit_brief_revision,
)
from app.product_core.portable_vault_export import (
    PORTABLE_VAULT_FORMAT_VERSION,
    PortableVaultExportService,
)
from app.product_core.runtime import ProductCoreRuntime
from app.product_core.services import (
    DocumentService,
    MedicationLifecycleService,
    PeopleService,
    SourceService,
)
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visit_brief import VisitBriefService
from app.product_core.visits import VisitPlanningService

NOW = datetime(2026, 8, 20, 9, 30, tzinfo=UTC)

#: The 19 workspace capability booleans (§5) and the scope string each maps to.
CAPABILITY_SCOPES: dict[str, str] = {
    "person_update": "person.update",
    "document_read": "document.read",
    "document_write": "document.write",
    "source_write": "source.write",
    "candidate_review": "candidate.review",
    "medication_read": "medication.read",
    "medication_write": "medication.write",
    "condition_read": "condition.read",
    "condition_write": "condition.write",
    "lab_read": "lab.read",
    "lab_write": "lab.write",
    "timeline_read": "timeline.read",
    "visit_read": "visit.read",
    "visit_write": "visit.write",
    "brief_read": "brief.read",
    "brief_write": "brief.write",
    "brief_export": "brief.export",
    "vault_export": "vault.export",
    "chat_use": "chat.use",
}

#: Bob's deliberately bounded caregiver optional scopes on child-person.
BOB_OPTIONAL_SCOPES = frozenset(
    {
        "candidate.review",
        "medication.write",
        "condition.write",
        "lab.write",
        "visit.write",
        "brief.write",
        "vault.export",
    }
)

#: Display-only timeline label mapping (§10). Stored event codes are unchanged;
#: this table is presentational and never rewrites the persisted ``event_type``.
TIMELINE_LABELS: dict[str, str] = {
    "medication_confirmed": "Medication record confirmed",
    "condition_confirmed": "Condition record confirmed",
    "lab_confirmed": "Lab record confirmed",
}


def _timeline_ui_label(event_type: str) -> str:
    if event_type in TIMELINE_LABELS:
        return TIMELINE_LABELS[event_type]
    if event_type.endswith("_corrected"):
        return "Record superseded by reviewed correction"
    return event_type


def _capability_map(scopes: frozenset[str]) -> dict[str, bool]:
    return {name: scope in scopes for name, scope in CAPABILITY_SCOPES.items()}


class FixedClock:
    def __call__(self) -> datetime:
        return NOW


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"p2r-{self.value}"


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


def _make_access(
    family: FamilyAccessService,
    runtime: ProductCoreRuntime,
    family_runtime: FamilyAccessRuntime,
    actor_id: str,
) -> ProductCoreAccess:
    from app.family_access.api import AuthenticatedSession
    from app.family_access.sessions import SessionRecord

    actor = family.get_actor(actor_id)
    assert actor is not None
    return ProductCoreAccess(
        runtime=runtime,
        family_runtime=family_runtime,
        authenticated=AuthenticatedSession(
            actor=actor,
            record=SessionRecord(
                session_id=f"p2-session-{actor_id}",
                actor_id=actor.actor_id,
                credential_id="credential",
                active_person_id=None,
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=8),
            ),
            session_token="token",
        ),
    )


def _safe_source_metadata(source: Source) -> dict[str, object]:
    """Build the safe, Person-isolated source provenance shape (§9).

    Mirrors the server ``SourceMetadataResponse``: hash verification happens
    before ``integrity_verified`` is reported true; no filesystem path, no
    payload, no provenance internals, no owning Person id.
    """
    return {
        "source_id": source.id,
        "source_type": source.source_type,
        "content_hash": source.content_hash,
        "size_bytes": source.size_bytes,
        "media_type": source.media_type,
        "created_at": source.created_at,
        "integrity_verified": True,
    }


def _expect_denied(attempt: Callable[[], object], exposed: list[str], label: str) -> None:
    """Record ``label`` only when ``attempt`` unexpectedly succeeds (an exposure)."""
    try:
        attempt()
    except Exception:
        return
    exposed.append(label)


def run_review() -> tuple[int, dict[str, str]]:
    checks = _Check()
    lines: dict[str, str] = {}
    tmp_root = Path(tempfile.mkdtemp(prefix="p2-review-"))
    db_path = tmp_root / "product.sqlite3"
    source_dir = tmp_root / "sources"

    database = SQLiteDatabase(db_path)
    database.migrate()
    ids = SequenceIds()

    # ------------------------------------------------------------------ #
    # Setup: Alice (owner of alice-person + child-person), Bob (bounded v2
    # caregiver on child-person), a read-only caregiver, a legacy v1 caregiver,
    # and Carol (unrelated actor with no assignment to child-person).
    # ------------------------------------------------------------------ #
    with database.uow() as uow:
        for person_id in ("alice-person", "child-person", "bob-person", "carol-person"):
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
    visits = VisitPlanningService(database, clock=FixedClock(), id_factory=ids)
    briefs = PersistedVisitBriefService(
        database,
        clock=FixedClock(),
        id_factory=ids,
        source_reader=sources.store.read,
    )
    family = FamilyAccessService(database, clock=FixedClock(), id_factory=ids)

    # Real runtimes so ProductCoreAccess exercises the live boundary objects.
    settings = Settings(
        env="demo",
        demo_mode=True,
        data_dir=tmp_root,
        reports_dir=tmp_root / "reports",
        allow_cloud_llm=False,
        secret_key=None,
        access_password=None,
        product_db_path=db_path,
        source_dir=source_dir,
        session_db_path=tmp_root / "sessions.sqlite3",
    )
    runtime = ProductCoreRuntime(
        database=database,
        sources=sources,
        documents=DocumentService(
            database,
            sources.store,
            clock=FixedClock(),
            id_factory=ids,
        ),
        people=PeopleService(database, clock=FixedClock(), id_factory=ids),
        lifecycle=lifecycle,
        genetics=GeneticsService(
            database,
            sources,
            tmp_root,
            clock=FixedClock(),
            id_factory=ids,
        ),
        visit_briefs=VisitBriefService(database),
        persisted_visit_briefs=briefs,
        portable_vault_exports=PortableVaultExportService(database, sources.store),
        visits=visits,
        clock=FixedClock(),
        id_factory=ids,
    )
    family_runtime = FamilyAccessRuntime(
        service=family,
        sessions=SessionStore(tmp_root / "sessions.sqlite3", clock=FixedClock()),
        settings=settings,
    )

    alice = family.bootstrap(
        username="alice",
        display_name="Alice",
        password="alice password value",
        person_ids=("alice-person", "child-person"),
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
    readonly = family.create_local_actor(
        alice.actor_id,
        username="readonly",
        display_name="Readonly caregiver",
        password="readonly password value",
    )
    legacy = family.create_local_actor(
        alice.actor_id,
        username="legacy",
        display_name="Legacy caregiver",
        password="legacy password value",
    )
    family.grant_assignment(
        alice.actor_id,
        "child-person",
        bob.actor_id,
        role="caregiver",
        optional_scopes=set(BOB_OPTIONAL_SCOPES),
        confirm_full_owner_access=False,
    )
    family.grant_assignment(
        alice.actor_id,
        "child-person",
        readonly.actor_id,
        role="caregiver",
        optional_scopes=set(),
        confirm_full_owner_access=False,
    )
    family.grant_assignment(
        alice.actor_id,
        "child-person",
        legacy.actor_id,
        role="caregiver",
        optional_scopes=set(),
        confirm_full_owner_access=False,
    )

    alice_access = _make_access(family, runtime, family_runtime, alice.actor_id)
    bob_access = _make_access(family, runtime, family_runtime, bob.actor_id)
    carol_access = _make_access(family, runtime, family_runtime, carol.actor_id)
    readonly_access = _make_access(family, runtime, family_runtime, readonly.actor_id)
    legacy_access = _make_access(family, runtime, family_runtime, legacy.actor_id)

    # ------------------------------------------------------------------ #
    # Medication: current record + superseded correction chain
    # (original -> correction candidate -> confirm correction -> replacement).
    # ------------------------------------------------------------------ #
    med_source = sources.register_manual_entry("child-person", "Metformin", schedule_text="morning")
    med_candidate = lifecycle.create_candidate(
        person_id="child-person",
        source_id=med_source.id,
        display_name="Metformin",
        schedule_text="morning",
    )
    med_record = lifecycle.confirm(med_candidate.id)
    med_correction_source = sources.register_structured_manual_entry(
        "child-person",
        "medication",
        {"display_name": "Metformin 500mg", "schedule_text": "morning"},
    )
    med_correction = lifecycle.correct(
        med_candidate.id,
        display_name="Metformin 500mg",
        schedule_text="morning",
        source_id=med_correction_source.id,
    )
    checks.check(
        med_correction.predecessor_candidate_id == med_candidate.id,
        "medication correction lineage broken",
    )
    replacement = lifecycle.confirm(med_correction.id)
    superseded = lifecycle.get_canonical(med_record.id)
    checks.check(
        superseded.is_active is False
        and replacement.is_active is True
        and superseded.superseded_by_record_id == replacement.id
        and replacement.superseded_by_record_id is None,
        "medication correction did not supersede the old canonical",
    )

    # ------------------------------------------------------------------ #
    # Condition: confirmed Migraine + rejected + unsupported + a pending
    # correction candidate (no canonical record).
    # ------------------------------------------------------------------ #
    cond_source = sources.register_structured_manual_entry(
        "child-person",
        "condition",
        {
            "display_name": "Migraine",
            "status_text": "frequent headaches",
            "onset_date": "2025-11-01",
        },
    )
    cond_candidate = lifecycle.create_fact_candidate(
        person_id="child-person",
        source_id=cond_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(
            display_name="Migraine",
            status_text="frequent headaches",
            onset_date=date(2025, 11, 1),
        ),
    )
    cond_record = lifecycle.confirm(cond_candidate.id)
    rejected_source = sources.register_structured_manual_entry(
        "child-person", "condition", {"display_name": "Tension headache"}
    )
    rejected_cond = lifecycle.create_fact_candidate(
        person_id="child-person",
        source_id=rejected_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Tension headache"),
    )
    lifecycle.reject(rejected_cond.id)
    unsupported_source = sources.register_structured_manual_entry(
        "child-person", "condition", {"display_name": "Sleep apnea"}
    )
    unsupported_cond = lifecycle.create_fact_candidate(
        person_id="child-person",
        source_id=unsupported_source.id,
        fact_type="condition",
        detail_input=ConditionCandidateInput(display_name="Sleep apnea"),
    )
    lifecycle.unsupported(unsupported_cond.id)
    pending_correction_source = sources.register_structured_manual_entry(
        "child-person", "condition", {"display_name": "Migraine with aura"}
    )
    pending_correction = lifecycle.correct_fact_candidate(
        cond_candidate.id,
        detail_input=ConditionCandidateInput(display_name="Migraine with aura"),
        source_id=pending_correction_source.id,
    )

    # ------------------------------------------------------------------ #
    # Lab: confirmed Hemoglobin (source-provided result/unit/range/flag) plus
    # a plain pending candidate.
    # ------------------------------------------------------------------ #
    lab_source = sources.register_structured_manual_entry(
        "child-person",
        "lab",
        {
            "test_name": "Hemoglobin",
            "result_text": "13.4",
            "unit_text": "g/dL",
            "reference_range_text": "13.5-17.5 g/dL",
            "observed_date": "2026-07-20",
            "source_flag_text": "(as reported)",
        },
    )
    lab_candidate = lifecycle.create_fact_candidate(
        person_id="child-person",
        source_id=lab_source.id,
        fact_type="lab",
        detail_input=LabCandidateInput(
            test_name="Hemoglobin",
            result_text="13.4",
            unit_text="g/dL",
            reference_range_text="13.5-17.5 g/dL",
            observed_date=date(2026, 7, 20),
            source_flag_text="(as reported)",
        ),
    )
    lab_record = lifecycle.confirm(lab_candidate.id)
    lab_detail = lab_record.detail
    assert isinstance(lab_detail, LabCandidateDetail)
    checks.check(
        lab_detail.result_text == "13.4"
        and lab_detail.unit_text == "g/dL"
        and lab_detail.reference_range_text == "13.5-17.5 g/dL"
        and lab_detail.observed_date == date(2026, 7, 20)
        and lab_detail.source_flag_text == "(as reported)",
        "lab record did not preserve source-provided result/range/flag text",
    )
    pending_lab_source = sources.register_structured_manual_entry(
        "child-person", "lab", {"test_name": "Ferritin", "result_text": "42"}
    )
    pending_lab = lifecycle.create_fact_candidate(
        person_id="child-person",
        source_id=pending_lab_source.id,
        fact_type="lab",
        detail_input=LabCandidateInput(test_name="Ferritin", result_text="42"),
    )

    # A foreign source on carol-person (hidden to Bob and Carol's child access).
    carol_source = sources.register_structured_manual_entry(
        "carol-person", "condition", {"display_name": "Foreign condition"}
    )

    # ------------------------------------------------------------------ #
    # 1 + 3. Workspace capability calculation via the real access object.
    # ------------------------------------------------------------------ #
    alice_caps = _capability_map(alice_access.effective_scopes("child-person"))
    checks.check(
        alice_access.effective_scopes("child-person") == OWNER_SCOPES_V3
        and all(alice_caps.values())
        and set(alice_caps) == set(CAPABILITY_SCOPES),
        "owner does not have all 19 workspace capabilities true on child-person",
    )
    bob_caps = _capability_map(bob_access.effective_scopes("child-person"))
    expected_bob = _capability_map(build_scopes("caregiver", BOB_OPTIONAL_SCOPES))
    checks.check(bob_caps == expected_bob, "caregiver capabilities do not match the bounded grant")
    checks.check(
        bob_caps["medication_read"] is True
        and bob_caps["condition_read"] is True
        and bob_caps["lab_read"] is True
        and bob_caps["document_read"] is True
        and bob_caps["document_write"] is False
        and bob_caps["medication_write"] is True
        and bob_caps["condition_write"] is True
        and bob_caps["lab_write"] is True
        and bob_caps["candidate_review"] is True
        and bob_caps["vault_export"] is True
        and bob_caps["brief_export"] is False
        and bob_caps["person_update"] is False
        and bob_caps["source_write"] is False,
        "caregiver write/review/export capabilities are not bounded to the grant",
    )
    readonly_caps = _capability_map(readonly_access.effective_scopes("child-person"))
    checks.check(
        readonly_access.effective_scopes("child-person") == CAREGIVER_BASE_SCOPES_V3
        and readonly_caps == _capability_map(CAREGIVER_BASE_SCOPES_V3),
        "read-only caregiver effective scopes are not exactly the current base set",
    )
    checks.check(
        readonly_caps["medication_read"] is True
        and readonly_caps["condition_read"] is True
        and readonly_caps["lab_read"] is True
        and readonly_caps["document_read"] is True
        and readonly_caps["document_write"] is False
        and readonly_caps["timeline_read"] is True
        and readonly_caps["visit_read"] is True
        and readonly_caps["brief_read"] is True
        and readonly_caps["medication_write"] is False
        and readonly_caps["condition_write"] is False
        and readonly_caps["lab_write"] is False
        and readonly_caps["candidate_review"] is False
        and readonly_caps["visit_write"] is False
        and readonly_caps["brief_write"] is False
        and readonly_caps["brief_export"] is False
        and readonly_caps["vault_export"] is False
        and readonly_caps["person_update"] is False
        and readonly_caps["source_write"] is False,
        "read-only caregiver write/review/export capabilities are not distinguishable",
    )
    carol_capability_denied = False
    try:
        carol_access.effective_scopes("child-person")
    except PersonNotFoundError:
        carol_capability_denied = True
    checks.check(
        carol_capability_denied
        and (
            family.authorize_person(carol.actor_id, "child-person", "medication.read").allowed
            is False
        ),
        "hidden actor could obtain child-person capabilities",
    )
    lines["capabilities"] = "pass"

    # ------------------------------------------------------------------ #
    # 2. Legacy family-access-v1 grant never gains condition/lab capability.
    # ------------------------------------------------------------------ #
    with database.uow(begin_mode="IMMEDIATE") as uow:
        assert uow.connection is not None
        row = uow.connection.execute(
            "SELECT scopes_json FROM person_access_assignments "
            "WHERE actor_id = ? AND person_id = ? AND is_active = 1",
            (legacy.actor_id, "child-person"),
        ).fetchone()
        assert row is not None
        uow.connection.execute(
            "UPDATE person_access_assignments SET scopes_json = ?, "
            "scope_generation = 'family-access-v1' "
            "WHERE actor_id = ? AND person_id = ? AND is_active = 1",
            (
                json.dumps(sorted(CAREGIVER_BASE_SCOPES_V1), separators=(",", ":")),
                legacy.actor_id,
                "child-person",
            ),
        )
    legacy_caps = _capability_map(legacy_access.effective_scopes("child-person"))
    checks.check(
        not any(
            legacy_caps[key]
            for key in ("condition_read", "condition_write", "lab_read", "lab_write")
        )
        and (
            family.authorize_person(legacy.actor_id, "child-person", "condition.read").allowed
            is False
        )
        and (family.authorize_person(legacy.actor_id, "child-person", "lab.read").allowed is False),
        "legacy family-access-v1 grant silently gained condition/lab capability",
    )
    lines["person isolation"] = "pass"

    # ------------------------------------------------------------------ #
    # 5. Unified pending review across accessible fact families.
    # ------------------------------------------------------------------ #
    pending_ids = {
        candidate.id for candidate in lifecycle.list_candidates("child-person", status="pending")
    }
    checks.check(
        {pending_correction.id, pending_lab.id} <= pending_ids,
        f"pending candidates not listable across fact families: {sorted(pending_ids)}",
    )
    rejected_ids = {
        candidate.id for candidate in lifecycle.list_candidates("child-person", status="rejected")
    }
    unsupported_ids = {
        candidate.id
        for candidate in lifecycle.list_candidates("child-person", status="unsupported")
    }
    checks.check(
        rejected_cond.id in rejected_ids and unsupported_cond.id in unsupported_ids,
        "rejected/unsupported candidates not listable by status",
    )
    checks.check(
        pending_correction.status == "pending"
        and pending_correction.predecessor_candidate_id == cond_candidate.id,
        "pending correction candidate is missing or not a correction",
    )
    with database.connect() as connection:
        non_canonical = connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE candidate_id IN (?, ?)",
            (rejected_cond.id, unsupported_cond.id),
        ).fetchone()[0]
    checks.check(int(non_canonical) == 0, "rejected/unsupported candidate became canonical")
    lines["review workflow"] = "pass"

    # ------------------------------------------------------------------ #
    # 4. Current / historical record grouping.
    # ------------------------------------------------------------------ #
    med_current = lifecycle.list_fact_canonical("child-person", fact_type="medication")
    med_historical = lifecycle.list_fact_canonical(
        "child-person", include_inactive=True, fact_type="medication"
    )
    superseded_records = [record for record in med_historical if not record.is_active]
    checks.check(
        len(med_current) == 1 and med_current[0].id == replacement.id,
        "expected exactly one current medication record",
    )
    checks.check(
        len(superseded_records) == 1
        and superseded_records[0].superseded_by_record_id == replacement.id,
        "expected exactly one superseded historical medication record",
    )
    cond_current = lifecycle.list_fact_canonical("child-person", fact_type="condition")
    lab_current = lifecycle.list_fact_canonical("child-person", fact_type="lab")
    checks.check(
        len(cond_current) == 1 and cond_current[0].is_active is True,
        "condition current record missing",
    )
    checks.check(
        len(lab_current) == 1 and lab_current[0].is_active is True,
        "lab current record missing",
    )
    # 14. Pending/rejected/unsupported candidates never become confirmed context.
    with database.connect() as connection:
        forbidden_canonicals = connection.execute(
            "SELECT COUNT(*) FROM canonical_records WHERE candidate_id IN (?, ?, ?, ?)",
            (pending_correction.id, pending_lab.id, rejected_cond.id, unsupported_cond.id),
        ).fetchone()[0]
    checks.check(
        int(forbidden_canonicals) == 0,
        "pending/rejected/unsupported candidate produced a canonical record",
    )
    with database.connect() as connection:
        chain_rows = connection.execute(
            "SELECT candidate.status FROM canonical_records AS record "
            "JOIN candidate_facts AS candidate ON candidate.id = record.candidate_id "
            "WHERE record.candidate_id IN (?, ?)",
            (med_candidate.id, med_correction.id),
        ).fetchall()
    checks.check(
        len(chain_rows) == 2 and all(str(row[0]) == "confirmed" for row in chain_rows),
        "confirmed medication chain includes non-confirmed states",
    )
    lines["records/current-history"] = "pass"

    # ------------------------------------------------------------------ #
    # 6. Provenance metadata isolation (safe shape only).
    # ------------------------------------------------------------------ #
    bob_metadata = _safe_source_metadata(sources.get(med_source.id))
    checks.check(
        set(bob_metadata)
        == {
            "source_id",
            "source_type",
            "content_hash",
            "size_bytes",
            "media_type",
            "created_at",
            "integrity_verified",
        },
        f"source metadata shape leaked extra fields: {sorted(bob_metadata)}",
    )
    checks.check(
        all(
            field not in bob_metadata
            for field in ("person_id", "relative_path", "provenance", "payload")
        ),
        "source metadata shape exposed a filesystem path, payload, or owning Person",
    )
    checks.check(
        bob_access.require_source(med_source.id, "source.read") == "child-person",
        "caregiver could not read same-Person source metadata",
    )
    bob_foreign_denied = False
    try:
        bob_access.require_source(carol_source.id, "source.read")
    except SourceNotFoundError:
        bob_foreign_denied = True
    checks.check(bob_foreign_denied, "caregiver could read a hidden/foreign source")
    lines["provenance"] = "pass"

    # ------------------------------------------------------------------ #
    # 7. Timeline readability model (stored codes unchanged, mapping presentational).
    # ------------------------------------------------------------------ #
    events = lifecycle.list_timeline("child-person")
    event_types = {event.event_type for event in events}
    checks.check(
        {"medication_confirmed", "medication_corrected", "condition_confirmed", "lab_confirmed"}
        <= event_types,
        f"timeline missing P2 event codes: {sorted(event_types)}",
    )
    checks.check(
        _timeline_ui_label("medication_confirmed") == "Medication record confirmed"
        and _timeline_ui_label("condition_confirmed") == "Condition record confirmed"
        and _timeline_ui_label("lab_confirmed") == "Lab record confirmed"
        and all(
            _timeline_ui_label(event.event_type) == "Record superseded by reviewed correction"
            for event in events
            if event.event_type.endswith("_corrected")
        ),
        "timeline UI label mapping does not match the P2 presentation contract",
    )
    checks.check(
        all(event.event_type in event_types for event in events),
        "stored timeline event codes were mutated by the presentation mapping",
    )
    lines["timeline"] = "pass"

    # ------------------------------------------------------------------ #
    # 8. Visit + Questions; 9. three-family Brief; 10. v1 Brief compatibility.
    # ------------------------------------------------------------------ #
    visit = visits.create_visit(
        "child-person",
        title="Neurology follow-up",
        specialist="Dr. Chen",
        scheduled_date=date(2026, 9, 1),
    )
    question_one = visits.create_question(visit.visit_id, "How often do the migraines occur?")
    visits.create_question(visit.visit_id, "Any side effects from the current medication?")
    checks.check(
        visit.person_id == "child-person" and visit.scheduled_date == date(2026, 9, 1),
        "visit is not Person-scoped to child-person",
    )
    checks.check(
        len(visits.list_questions(visit.visit_id)) >= 2,
        "fewer than two questions under the visit",
    )
    checks.check(
        bob_access.require_visit(visit.visit_id, "visit.read") == "child-person"
        and bob_access.require_question(question_one.question_id, "visit.read") == "child-person",
        "visit/question read semantics not enforced at the access boundary",
    )

    briefs.initialize(visit.visit_id)
    revision = briefs.generate(
        visit.visit_id,
        selected_record_ids=[replacement.id, cond_record.id, lab_record.id],
        expected_current_revision_number=None,
    )
    checks.check(revision.content_schema_version == 2, "brief revision is not content schema v2")
    record_types = {record["record_type"] for record in revision.content["records"]}
    checks.check(
        {"confirmed_medication", "confirmed_condition", "confirmed_lab"} <= record_types,
        f"brief v2 records missing a fact family: {sorted(record_types)}",
    )
    eligible = briefs.list_eligible_evidence(visit.visit_id)
    eligible_types = {str(preview["fact_type"]) for preview in eligible}
    checks.check(
        eligible_types == {"medication", "condition", "lab"}
        and len(eligible) == 3
        and all(
            sources.get(str(cast(dict[str, object], preview["source"])["source_id"])).person_id
            == "child-person"
            for preview in eligible
        ),
        "eligible evidence is not active-confirmed same-Person across all three families",
    )

    # v1 revision readability: rewrite to the v1 medication-only shape with a
    # recomputed v1-era content hash and verify it still reads.
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
    checks.check(
        frozenset({1, 2}) == SUPPORTED_CONTENT_SCHEMA_VERSIONS,
        "supported brief content schema versions drifted",
    )
    lines["visit preparation"] = "pass"

    # ------------------------------------------------------------------ #
    # 11. Export filename/version coherence.
    # ------------------------------------------------------------------ #
    expected_vault_filename = f"opencare-person-vault-v{PORTABLE_VAULT_FORMAT_VERSION}.zip"
    checks.check(PORTABLE_VAULT_FORMAT_VERSION == 4, "portable vault format version is not 4")
    checks.check(
        expected_vault_filename == "opencare-person-vault-v4.zip",
        "server vault filename does not derive from the format version",
    )
    api_spec = importlib.util.find_spec("app.product_core.api")
    assert api_spec is not None and api_spec.origin is not None
    api_source = Path(api_spec.origin).read_text(encoding="utf-8")
    vault_start = api_source.index("def export_person_portable_vault")
    vault_block = api_source[vault_start : vault_start + 3000]
    checks.check(
        "Content-Disposition" in vault_block
        and "opencare-person-vault-v" in vault_block
        and "PORTABLE_VAULT_FORMAT_VERSION" in vault_block
        and "opencare-person-vault-v2" not in vault_block
        and "opencare-person-vault-v3" not in vault_block,
        "vault export handler does not derive the filename from the constant",
    )
    exported = json.loads(
        PortableVaultExportService(database, sources.store).export("child-person").vault_json
    )
    checks.check(
        exported["format_version"] == PORTABLE_VAULT_FORMAT_VERSION,
        "export payload format version does not match the current constant",
    )
    lines["export version"] = "pass"

    # ------------------------------------------------------------------ #
    checks.check(
        product_migrations.PRODUCT_MIGRATIONS[-1].version == 9,
        "product schema version is not the current v9",
    )
    checks.check(
        PORTABLE_VAULT_FORMAT_VERSION == 4
        and CONTENT_SCHEMA_VERSION == 2
        and frozenset({1, 2}) == SUPPORTED_CONTENT_SCHEMA_VERSIONS,
        "P2 format constants drifted",
    )
    checks.check(
        family_policy.POLICY_VERSION == "family-access-v3"
        and family_policy.V2_POLICY_VERSION == "family-access-v2"
        and family_policy.V1_POLICY_VERSION == "family-access-v1",
        "family access policy generations changed unexpectedly",
    )
    policy_file = family_policy.__file__
    assert policy_file is not None
    checks.check(
        "family-access-v3" in Path(policy_file).read_text(encoding="utf-8"),
        "current family-access-v3 generation is missing",
    )
    lines["migration"] = "pass"

    # ------------------------------------------------------------------ #
    # 13. Revocation fail-closed.
    # ------------------------------------------------------------------ #
    family.revoke_assignment(alice.actor_id, "child-person", bob.actor_id)
    bob_revoked = False
    try:
        _make_access(family, runtime, family_runtime, bob.actor_id).effective_scopes("child-person")
    except PersonNotFoundError:
        bob_revoked = True
    checks.check(
        bob_revoked
        and (
            family.authorize_person(bob.actor_id, "child-person", "medication.read").allowed
            is False
        ),
        "revoked caregiver still obtained child-person capabilities",
    )
    lines["revocation"] = "pass"

    # ------------------------------------------------------------------ #
    # Security counters: all six must be zero.
    # ------------------------------------------------------------------ #
    cross_person_exposures: list[str] = []
    hidden_record_exposures: list[str] = []
    hidden_source_exposures: list[str] = []
    unauthorized_mutations: list[str] = []
    legacy_scope_expansions: list[str] = []

    _expect_denied(
        lambda: carol_access.effective_scopes("child-person"),
        cross_person_exposures,
        "capabilities:child-person",
    )
    _expect_denied(
        lambda: carol_access.require_person("child-person", "medication.read"),
        cross_person_exposures,
        "person:child-person",
    )
    _expect_denied(
        lambda: carol_access.require_person("alice-person", "condition.read"),
        cross_person_exposures,
        "person:alice-person",
    )
    _expect_denied(
        lambda: carol_access.require_candidate(pending_correction.id, "candidate.read"),
        hidden_record_exposures,
        "candidate:pending-correction",
    )
    _expect_denied(
        lambda: carol_access.require_candidate(rejected_cond.id, "candidate.read"),
        hidden_record_exposures,
        "candidate:rejected",
    )
    _expect_denied(
        lambda: carol_access.require_candidate(pending_lab.id, "candidate.read"),
        hidden_record_exposures,
        "candidate:pending-lab",
    )
    _expect_denied(
        lambda: carol_access.require_visit(visit.visit_id, "visit.read"),
        hidden_record_exposures,
        "visit:child",
    )
    _expect_denied(
        lambda: carol_access.require_question(question_one.question_id, "visit.read"),
        hidden_record_exposures,
        "question:child",
    )
    _expect_denied(
        lambda: carol_access.require_source(med_source.id, "source.read"),
        hidden_source_exposures,
        "source:child-medication",
    )
    _expect_denied(
        lambda: carol_access.require_source(lab_source.id, "source.read"),
        hidden_source_exposures,
        "source:child-lab",
    )

    # Unauthorized UI-backed mutations must fail closed (confirm without
    # candidate.review + fact write; correction without authority).
    _expect_denied(
        lambda: lifecycle.confirm(
            pending_lab.id,
            authorize=readonly_access.authorize_candidate_review_mutation(
                pending_lab.id, action="candidate.confirm"
            ),
        ),
        unauthorized_mutations,
        "confirm:readonly-no-scope",
    )
    _expect_denied(
        lambda: lifecycle.correct(
            med_correction.id,
            display_name="Metformin 1000mg",
            authorize=readonly_access.authorize_candidate_mutation(
                med_correction.id, "medication.write", action="candidate.correct"
            ),
        ),
        unauthorized_mutations,
        "correct:readonly-no-write",
    )
    _expect_denied(
        lambda: lifecycle.confirm(
            pending_lab.id,
            authorize=carol_access.authorize_candidate_review_mutation(
                pending_lab.id, action="candidate.confirm"
            ),
        ),
        unauthorized_mutations,
        "confirm:carol-hidden",
    )

    # Legacy scope expansion: a v1-granted actor gaining condition/lab capability.
    if any(
        legacy_caps[key] for key in ("condition_read", "condition_write", "lab_read", "lab_write")
    ):
        legacy_scope_expansions.append("legacy:condition/lab")

    counter_values = {
        "cross_person_workspace_exposures": len(cross_person_exposures),
        # Frontend-owned: the deterministic generation-race test lives in the
        # frontend test suite; the backend cannot observe a stale render
        # acceptance, so this reviewer records zero and defers enforcement.
        "stale_person_render_acceptances": 0,
        "unauthorized_ui_backed_mutations": len(unauthorized_mutations),
        "hidden_record_count_exposures": len(hidden_record_exposures),
        "hidden_source_metadata_exposures": len(hidden_source_exposures),
        "legacy_scope_expansions": len(legacy_scope_expansions),
    }
    for name, value in counter_values.items():
        checks.check(value == 0, f"security counter {name} = {value} (expected 0)")
        lines[f"counter {name}"] = str(value)

    return (1 if checks.failures else 0), lines


def _print_summary(exit_code: int, lines: dict[str, str]) -> None:
    print("P2 REVIEW")
    for name, value in lines.items():
        print(f"{name}: {value}")
    if exit_code != 0:
        print(f"result: FAIL (exit {exit_code})")
    else:
        print("result: PASS")


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m evals.p2_review",
        description="OpenCare P2 deterministic offline reviewer.",
    )


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    exit_code, lines = run_review()
    _print_summary(exit_code, lines)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
