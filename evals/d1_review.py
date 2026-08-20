"""Deterministic offline D1 evidence-document-ingest reviewer.

Run with ``python -m evals.d1_review``. The reviewer uses only synthetic bytes,
a temporary SQLite database/source tree, deterministic IDs, and a fixed clock.
It never invokes a network, model, OCR, browser, container, or external service.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.agent.context import build_product_core_agent_context
from app.config import Settings
from app.family_access.policy import CAREGIVER_BASE_SCOPES_V2
from app.family_access.runtime import FamilyAccessRuntime
from app.family_access.service import FamilyAccessService
from app.family_access.sessions import SessionStore
from app.product_core.access import ProductCoreAccess
from app.product_core.genetics import GeneticsService
from app.product_core.installation_backup import InstallationBackupService
from app.product_core.installation_recovery import (
    InstallationRecoveryService,
    verify_recovered_installation,
)
from app.product_core.models import Person
from app.product_core.persisted_visit_briefs import PersistedVisitBriefService
from app.product_core.portable_vault_export import PortableVaultExportService
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

NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)
RAW_MARKER = "D1_RAW_DOCUMENT_MARKER_7d54c2"
COUNTER_NAMES = (
    "cross_person_document_exposures",
    "legacy_document_scope_expansions",
    "unauthorized_document_writes",
    "provenance_span_mismatches_accepted",
    "unreviewed_document_canonicalizations",
    "raw_document_agent_disclosures",
    "corrupted_document_sources_accepted",
    "corrupted_extractions_accepted",
)
HEADINGS = (
    "source integrity",
    "PDF/TXT extraction",
    "v3 document access",
    "legacy isolation",
    "page/span provenance",
    "review lifecycle",
    "person isolation",
    "revocation",
    "agent raw-document isolation",
    "export/recovery",
)


class FixedClock:
    def __call__(self) -> datetime:
        return NOW


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"d1r-{self.value}"


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, condition: bool, message: str) -> None:
        if not condition:
            self.failures.append(message)


def _pdf(pages: tuple[str, ...]) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    for text in pages:
        page = writer.add_blank_page(width=300, height=300)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        stream = DecodedStreamObject()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(f"BT /F1 12 Tf 20 250 Td ({escaped}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _encrypted_pdf() -> bytes:
    writer = PdfWriter()
    writer.append_pages_from_reader(PdfReader(io.BytesIO(_pdf(("secret",)))))
    writer.encrypt("synthetic-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


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
                session_id=f"d1-session-{actor_id}",
                actor_id=actor_id,
                credential_id="synthetic-credential",
                active_person_id=None,
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=8),
            ),
            session_token="synthetic-session-token",
        ),
    )


def _rejected(attempt: Callable[[], object]) -> bool:
    try:
        attempt()
    except Exception:
        return True
    return False


def _document_rejected(documents: DocumentService, body: bytes, media_type: str) -> bool:
    return _rejected(lambda: documents.register("alice-person", body, media_type))


def _locator(
    source_id: str,
    content_hash: str,
    extraction_id: str,
    page_number: int,
    page_text: str,
    selected: str,
) -> dict[str, object]:
    start = page_text.index(selected)
    end = start + len(selected)
    return {
        "kind": "document_text_span",
        "source_id": source_id,
        "content_hash": content_hash,
        "extraction_id": extraction_id,
        "page_number": page_number,
        "start_codepoint": start,
        "end_codepoint": end,
        "selected_text_sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(),
    }


def run_review() -> tuple[int, dict[str, str], dict[str, int]]:
    checks = Checks()
    counters = dict.fromkeys(COUNTER_NAMES, 0)
    lines = dict.fromkeys(HEADINGS, "pass")

    with tempfile.TemporaryDirectory(prefix="d1-review-") as temporary:
        root = Path(temporary)
        db_path = root / "product.sqlite3"
        source_dir = root / "sources"
        database = SQLiteDatabase(db_path)
        database.migrate()
        ids = SequenceIds()
        clock = FixedClock()

        with database.uow() as uow:
            for person_id in ("alice-person", "carol-person"):
                uow.people.insert(
                    Person(
                        person_id=person_id,
                        display_name=person_id,
                        created_at=NOW,
                        updated_at=NOW,
                        is_active=True,
                    )
                )

        sources = SourceService(database, source_dir, clock=clock, id_factory=ids)
        documents = DocumentService(database, sources.store, clock=clock, id_factory=ids)
        lifecycle = MedicationLifecycleService(
            database,
            clock=clock,
            id_factory=ids,
            source_reader=sources.store.read,
        )
        family = FamilyAccessService(database, clock=clock, id_factory=ids)
        settings = Settings(
            env="demo",
            demo_mode=True,
            data_dir=root,
            reports_dir=root / "reports",
            allow_cloud_llm=False,
            secret_key=None,
            access_password=None,
            product_db_path=db_path,
            source_dir=source_dir,
            session_db_path=root / "sessions.sqlite3",
        )
        runtime = ProductCoreRuntime(
            database=database,
            sources=sources,
            documents=documents,
            people=PeopleService(database, clock=clock, id_factory=ids),
            lifecycle=lifecycle,
            genetics=GeneticsService(
                database,
                sources,
                root,
                clock=clock,
                id_factory=ids,
            ),
            visit_briefs=VisitBriefService(database),
            persisted_visit_briefs=PersistedVisitBriefService(
                database,
                clock=clock,
                id_factory=ids,
                source_reader=sources.store.read,
            ),
            portable_vault_exports=PortableVaultExportService(database, sources.store),
            visits=VisitPlanningService(database, clock=clock, id_factory=ids),
            clock=clock,
            id_factory=ids,
        )
        family_runtime = FamilyAccessRuntime(
            service=family,
            sessions=SessionStore(root / "sessions.sqlite3", clock=clock),
            settings=settings,
        )

        alice = family.bootstrap(
            username="alice",
            display_name="Alice",
            password="synthetic alice password",
            person_ids=("alice-person", "carol-person"),
            own_person_id="alice-person",
            confirm_full_owner_access=True,
        )
        bob = family.create_local_actor(
            alice.actor_id,
            username="bob",
            display_name="Bob",
            password="synthetic bob password",
        )
        legacy = family.create_local_actor(
            alice.actor_id,
            username="legacy-bob",
            display_name="LegacyBob",
            password="synthetic legacy password",
        )
        carol = family.create_local_actor(
            alice.actor_id,
            username="carol",
            display_name="Carol",
            password="synthetic carol password",
        )
        family.grant_assignment(
            alice.actor_id,
            "alice-person",
            bob.actor_id,
            role="caregiver",
            optional_scopes={"candidate.review", "medication.write"},
            confirm_full_owner_access=False,
        )
        legacy_assignment = family.grant_assignment(
            alice.actor_id,
            "alice-person",
            legacy.actor_id,
            role="caregiver",
            optional_scopes=set(),
            confirm_full_owner_access=False,
        )
        with database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            uow.connection.execute(
                "UPDATE person_access_assignments SET scopes_json = ?, scope_generation = ? "
                "WHERE assignment_id = ?",
                (
                    json.dumps(sorted(CAREGIVER_BASE_SCOPES_V2), separators=(",", ":")),
                    "family-access-v2",
                    legacy_assignment.assignment_id,
                ),
            )

        alice_access = _make_access(family, runtime, family_runtime, alice.actor_id)
        bob_access = _make_access(family, runtime, family_runtime, bob.actor_id)
        legacy_access = _make_access(family, runtime, family_runtime, legacy.actor_id)
        carol_access = _make_access(family, runtime, family_runtime, carol.actor_id)

        pdf_bytes = _pdf(
            (
                "Synthetic page one",
                "Aspirin evidence on synthetic page two",
                f"Synthetic page three {RAW_MARKER}",
            )
        )
        pdf_document = documents.register(
            "alice-person",
            pdf_bytes,
            "application/pdf",
            original_filename="C:\\private\\three-pages.pdf",
            authorize=alice_access.authorize_person_mutation(
                "alice-person", "source.write", "document.write", action="document.create"
            ),
        )
        text_bytes = b"\xef\xbb\xbfUnused export marker\r\nSecond line\rThird line"
        text_document = documents.register(
            "alice-person",
            text_bytes,
            "text/plain; charset=utf-8",
            original_filename="../unused.txt",
            authorize=alice_access.authorize_person_mutation(
                "alice-person", "source.write", "document.write", action="document.create"
            ),
        )
        carol_document = documents.register(
            "carol-person",
            b"Carol private document",
            "text/plain",
            authorize=alice_access.authorize_person_mutation(
                "carol-person", "source.write", "document.write", action="document.create"
            ),
        )

        checks.check(
            sources.store.read(pdf_document.source) == pdf_bytes
            and pdf_document.source.content_hash == hashlib.sha256(pdf_bytes).hexdigest()
            and pdf_document.source.original_filename == "three-pages.pdf",
            "raw PDF bytes or metadata changed",
        )
        checks.check(
            sources.store.read(text_document.source) == text_bytes
            and text_document.source.content_hash == hashlib.sha256(text_bytes).hexdigest()
            and text_document.source.original_filename == "unused.txt",
            "raw text bytes or filename changed",
        )

        pdf_pages = [
            documents.get_page(
                pdf_document.source.id, pdf_document.extraction.extraction_id, page_number
            )[1]
            for page_number in (1, 2, 3)
        ]
        text_page = documents.get_page(
            text_document.source.id, text_document.extraction.extraction_id, 1
        )[1]
        checks.check(
            pdf_document.extraction.page_count == 3
            and [page.page_number for page in pdf_pages] == [1, 2, 3]
            and "Aspirin" in pdf_pages[1].normalized_text
            and RAW_MARKER in pdf_pages[2].normalized_text,
            "three-page PDF extraction is not deterministic",
        )
        checks.check(
            text_page.normalized_text == "Unused export marker\nSecond line\nThird line"
            and text_document.extraction.page_count == 1,
            "plain-text normalization changed",
        )
        source_count = len(documents.list_for_person("alice-person")) + len(
            documents.list_for_person("carol-person")
        )
        blank_writer = PdfWriter()
        blank_writer.add_blank_page(width=100, height=100)
        blank_output = io.BytesIO()
        blank_writer.write(blank_output)
        invalid_documents = (
            (b"%PDF-broken", "application/pdf"),
            (_encrypted_pdf(), "application/pdf"),
            (blank_output.getvalue(), "application/pdf"),
            (b"\xff", "text/plain"),
            (("x" * 100_001).encode("utf-8"), "text/plain"),
        )
        checks.check(
            all(_document_rejected(documents, body, media) for body, media in invalid_documents)
            and source_count
            == len(documents.list_for_person("alice-person"))
            + len(documents.list_for_person("carol-person")),
            "invalid or bounded document was durably accepted",
        )

        checks.check(
            "document.read" in alice_access.effective_scopes("alice-person")
            and "document.write" in alice_access.effective_scopes("alice-person")
            and "document.read" in bob_access.effective_scopes("alice-person")
            and "document.write" not in bob_access.effective_scopes("alice-person"),
            "v3 owner/read-only document capability mismatch",
        )
        bob_access.require_source_for_person(
            pdf_document.source.id, "alice-person", "document.read"
        )
        checks.check(
            documents.get(pdf_document.source.id)[1] == pdf_document.extraction,
            "authorized v3 document read failed",
        )

        legacy_has_document = "document.read" in legacy_access.effective_scopes("alice-person")
        if legacy_has_document:
            counters["legacy_document_scope_expansions"] += 1
        checks.check(
            legacy_access.require_source(pdf_document.source.id, "source.read") == "alice-person",
            "legacy metadata access unexpectedly failed",
        )
        if not _rejected(
            lambda: legacy_access.require_source_for_person(
                pdf_document.source.id, "alice-person", "document.read"
            )
        ):
            counters["legacy_document_scope_expansions"] += 1

        unauthorized_attempts = (
            lambda: documents.register(
                "alice-person",
                b"Bob must not upload",
                "text/plain",
                authorize=bob_access.authorize_person_mutation(
                    "alice-person", "source.write", "document.write", action="document.create"
                ),
            ),
            lambda: documents.register(
                "alice-person",
                b"Legacy must not upload",
                "text/plain",
                authorize=legacy_access.authorize_person_mutation(
                    "alice-person", "source.write", "document.write", action="document.create"
                ),
            ),
        )
        counters["unauthorized_document_writes"] += sum(
            not _rejected(attempt) for attempt in unauthorized_attempts
        )

        selected = "Aspirin"
        locator = _locator(
            pdf_document.source.id,
            pdf_document.source.content_hash,
            pdf_document.extraction.extraction_id,
            2,
            pdf_pages[1].normalized_text,
            selected,
        )
        candidate_authorizer = bob_access.combine_mutation_authorizers(
            bob_access.authorize_person_mutation(
                "alice-person", "candidate.review", action="candidate.create"
            ),
            bob_access.authorize_source_mutation(
                pdf_document.source.id,
                "alice-person",
                "source.read",
                action="source.read",
            ),
        )
        bad_locator = {**locator, "selected_text_sha256": "0" * 64}
        if not _rejected(
            lambda: lifecycle.create_candidate(
                person_id="alice-person",
                source_id=pdf_document.source.id,
                display_name=selected,
                provenance_locator=bad_locator,
                authorize=candidate_authorizer,
            )
        ):
            counters["provenance_span_mismatches_accepted"] += 1

        candidate = lifecycle.create_candidate(
            person_id="alice-person",
            source_id=pdf_document.source.id,
            display_name=selected,
            provenance_locator=locator,
            authorize=candidate_authorizer,
        )
        before_review = lifecycle.list_canonical("alice-person")
        counters["unreviewed_document_canonicalizations"] += len(before_review)
        checks.check(
            candidate.status == "pending" and candidate.provenance_locator == locator,
            "exact span did not create a pending candidate",
        )
        canonical = lifecycle.confirm(
            candidate.id,
            authorize=bob_access.authorize_candidate_review_mutation(
                candidate.id, action="candidate.confirm"
            ),
        )
        checks.check(
            lifecycle.get_candidate(candidate.id).status == "confirmed"
            and canonical.candidate_id == candidate.id
            and canonical.provenance_locator == locator,
            "pending-to-confirm lifecycle failed",
        )

        wrong_person_attempts = (
            lambda: bob_access.require_source_for_person(
                pdf_document.source.id, "carol-person", "document.read"
            ),
            lambda: carol_access.require_source_for_person(
                pdf_document.source.id, "alice-person", "document.read"
            ),
            lambda: bob_access.require_source_for_person(
                carol_document.source.id, "alice-person", "document.read"
            ),
        )
        counters["cross_person_document_exposures"] += sum(
            not _rejected(attempt) for attempt in wrong_person_attempts
        )

        revoked_locator = _locator(
            pdf_document.source.id,
            pdf_document.source.content_hash,
            pdf_document.extraction.extraction_id,
            1,
            pdf_pages[0].normalized_text,
            "Synthetic",
        )
        revoked_candidate = lifecycle.create_candidate(
            person_id="alice-person",
            source_id=pdf_document.source.id,
            display_name="Synthetic",
            provenance_locator=revoked_locator,
            authorize=candidate_authorizer,
        )
        family.revoke_assignment(alice.actor_id, "alice-person", bob.actor_id)
        revoked_denied = _rejected(
            lambda: lifecycle.confirm(
                revoked_candidate.id,
                authorize=bob_access.authorize_candidate_review_mutation(
                    revoked_candidate.id, action="candidate.confirm"
                ),
            )
        )
        checks.check(
            revoked_denied
            and lifecycle.get_candidate(revoked_candidate.id).status == "pending"
            and len(lifecycle.list_canonical("alice-person")) == 1,
            "revocation did not fail closed before review mutation",
        )

        agent_context = build_product_core_agent_context(runtime, "alice-person")
        serialized_context = agent_context.model_dump_json()
        raw_disclosures = sum(
            marker in serialized_context
            for marker in (RAW_MARKER, "Unused export marker", pdf_bytes[:20].hex())
        )
        counters["raw_document_agent_disclosures"] += raw_disclosures

        exported = runtime.portable_vault_exports.export("alice-person")
        with zipfile.ZipFile(io.BytesIO(exported.zip_bytes)) as archive:
            exported_vault = json.loads(archive.read("vault.json"))
            exported_ids = {item["source_id"] for item in exported_vault["sources"]}
            checks.check(
                pdf_document.source.id in exported_ids
                and text_document.source.id in exported_ids
                and carol_document.source.id not in exported_ids
                and f"sources/{text_document.source.id}/payload.bin" in archive.namelist(),
                "person-scoped export omitted unused evidence or exposed Carol",
            )

        backup = root / "backup"
        InstallationBackupService(db_path, source_dir, clock=clock).backup(backup)
        recovered_root = root / "recovered"
        InstallationRecoveryService(clock=clock).recover(
            backup, recovered_root, confirm_maintenance=True
        )
        recovery_report = verify_recovered_installation(recovered_root)
        recovered_database = SQLiteDatabase(recovered_root / "database.sqlite3")
        with recovered_database.uow() as uow:
            recovered_extraction = uow.document_extractions.get(
                pdf_document.extraction.extraction_id
            )
            recovered_text = uow.document_extractions.get_page(
                text_document.extraction.extraction_id, 1
            )
        checks.check(
            recovery_report.valid
            and recovered_extraction == pdf_document.extraction
            and recovered_text == text_page,
            "backup/recovery changed document extraction identity",
        )

        text_path = source_dir / text_document.source.relative_path
        text_path.write_bytes(b"tampered source")
        if not _rejected(lambda: documents.get(text_document.source.id)):
            counters["corrupted_document_sources_accepted"] += 1

        with database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            uow.connection.execute("DROP TRIGGER document_extraction_pages_immutable_update")
            tampered_text = "tampered extraction"
            uow.connection.execute(
                "UPDATE document_extraction_pages "
                "SET normalized_text = ?, extracted_chars = ? "
                "WHERE extraction_id = ? AND page_number = 1",
                (
                    tampered_text,
                    len(tampered_text),
                    pdf_document.extraction.extraction_id,
                ),
            )
        if not _rejected(lambda: documents.get(pdf_document.source.id)):
            counters["corrupted_extractions_accepted"] += 1

    for name, value in counters.items():
        checks.check(value == 0, f"{name} = {value}")
    if checks.failures:
        lines[HEADINGS[0]] = "fail"
    return (1 if checks.failures else 0), lines, counters


def _print_summary(exit_code: int, lines: dict[str, str], counters: dict[str, int]) -> None:
    print("D1 REVIEW")
    for heading, status in lines.items():
        print(f"{heading}: {status}")
    for counter_name, count in counters.items():
        print(f"counter {counter_name}: {count}")
    print("result: PASS" if exit_code == 0 else f"result: FAIL (exit {exit_code})")


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="python -m evals.d1_review",
        description="OpenCare D1 deterministic offline reviewer.",
    )


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    exit_code, lines, counters = run_review()
    _print_summary(exit_code, lines, counters)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
