from __future__ import annotations

import hashlib
import io
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.product_core.errors import DocumentValidationError, IntegrityStorageError
from app.product_core.models import Person
from app.product_core.services import DocumentService, SourceService
from app.product_core.sqlite import SQLiteDatabase


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"document-id-{self.value}"


def _service(tmp_path: Path) -> tuple[SQLiteDatabase, DocumentService]:
    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()

    def clock() -> datetime:
        return datetime(2026, 8, 20, tzinfo=UTC)

    ids = SequenceIds()
    sources = SourceService(database, tmp_path / "sources", clock=clock, id_factory=ids)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Ada",
                created_at=clock(),
                updated_at=clock(),
                is_active=True,
            )
        )
    return database, DocumentService(database, sources.store, clock=clock, id_factory=ids)


def _text_pdf(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
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


def test_text_document_preserves_raw_bytes_and_minimally_normalizes(tmp_path: Path) -> None:
    database, documents = _service(tmp_path)
    payload = b"\xef\xbb\xbfFirst\r\nSecond\rThird"

    result = documents.register(
        "person-1", payload, "text/plain", original_filename="C:\\private\\note.txt"
    )

    assert result.created is True
    assert result.source.content_hash == hashlib.sha256(payload).hexdigest()
    assert result.source.original_filename == "note.txt"
    assert result.extraction.page_count == 1
    snapshot, page = documents.get_page(result.source.id, result.extraction.extraction_id, 1)
    assert snapshot.extractor == "opencare-text"
    assert page.normalized_text == "First\nSecond\nThird"
    assert page.page_hash == hashlib.sha256(page.normalized_text.encode()).hexdigest()
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_pdf_embedded_text_is_accepted_and_blank_pdf_is_rejected(tmp_path: Path) -> None:
    _, documents = _service(tmp_path)

    accepted = documents.register("person-1", _text_pdf("Embedded evidence"), "application/pdf")
    _, page = documents.get_page(accepted.source.id, accepted.extraction.extraction_id, 1)
    assert "Embedded evidence" in page.normalized_text
    assert accepted.extraction.extractor == "pypdf"
    assert accepted.extraction.extractor_version == "6.13.0"

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(DocumentValidationError, match="no_usable_text"):
        documents.register("person-1", output.getvalue(), "application/pdf")


def test_validation_failures_leave_no_durable_source(tmp_path: Path) -> None:
    database, documents = _service(tmp_path)

    for payload, media_type, reason in (
        (b"\xff", "text/plain", "invalid_utf8"),
        (b"not-pdf", "application/pdf", "pdf_signature_invalid"),
        (b"%PDF-broken", "application/pdf", "malformed_pdf"),
        (("x" * 100_001).encode(), "text/plain", "page_chars_limit_exceeded"),
    ):
        with pytest.raises(DocumentValidationError, match=reason):
            documents.register("person-1", payload, media_type)

    with database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM sources").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM document_extractions").fetchone()[0] == 0


def test_extractions_are_database_immutable_and_dedup_verifies_them(tmp_path: Path) -> None:
    database, documents = _service(tmp_path)
    first = documents.register("person-1", b"evidence", "text/plain")

    duplicate = documents.register("person-1", b"evidence", "text/plain")
    assert duplicate.created is False
    assert duplicate.source.id == first.source.id
    with database.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE document_extractions SET text_hash = ? WHERE extraction_id = ?",
                ("0" * 64, first.extraction.extraction_id),
            )
        connection.execute("DROP TRIGGER document_extractions_immutable_delete")
        connection.execute("DROP TRIGGER document_extraction_pages_immutable_delete")
        connection.execute(
            "DELETE FROM document_extraction_pages WHERE extraction_id = ?",
            (first.extraction.extraction_id,),
        )
        connection.execute(
            "DELETE FROM document_extractions WHERE extraction_id = ?",
            (first.extraction.extraction_id,),
        )
    with pytest.raises(IntegrityStorageError, match="missing"):
        documents.register("person-1", b"evidence", "text/plain")
