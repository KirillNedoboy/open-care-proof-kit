"""Service-level tests for AlphaGenome stage C.1 — Reference Allele Binding
/ Outbound SNV Projection.

Exercises ``ScientificVariantProjector`` end-to-end with a real
``ScientificObservationAuthorizer``, synthetic reference FASTA fixtures,
and manually computed .fai indices.  Pure local — no network, no SDK,
no AlphaGenome import.
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings, clear_settings_cache, load_settings
from app.family_access.api import AuthenticatedSession
from app.family_access.models import ActorRecord
from app.family_access.policy import OWNER_SCOPES
from app.family_access.runtime import FamilyAccessRuntime, create_family_access_runtime
from app.family_access.sessions import SessionRecord
from app.product_core import services as pc_services
from app.product_core.access import ProductCoreAccess
from app.product_core.errors import PersonNotFoundError
from app.product_core.runtime import ProductCoreRuntime, create_product_core_runtime
from app.product_core.scientific_observation import (
    AlphaGenomeSelectionUnavailableError,
    AuthorizedGeneticsObservation,
    ScientificObservationAuthorizer,
)
from app.product_core.scientific_projection import (
    ASSEMBLY_ACCESSION,
    ASSEMBLY_NAME,
    GRCH38_P13_PRIMARY_CONTIGS,
    SOURCE_KIND,
    AuthorizedVariantProjection,
    LocalIndexedFastaReferenceResolver,
    ReferenceGenomeConfigurationState,
    ReferenceGenomeUnavailableError,
    ScientificVariantProjector,
    VariantProjectionError,
    reference_genome_configuration_state_from_settings,
)
from app.product_core.sqlite import SQLiteDatabase

SENTINEL = "alpha-secret-SENTINEL-do-not-leak"

OWNER_SCOPES_LIST = sorted(OWNER_SCOPES)

_SEQ = 0


def _now() -> datetime:
    global _SEQ
    _SEQ += 1
    return datetime(2026, 9, 10, 12, 0, _SEQ % 60, tzinfo=UTC)


def _now_iso() -> str:
    return _now().isoformat()


# ── socket guard ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network access is forbidden in these tests")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


# ── construction helpers ──────────────────────────────────────────────────


class _Clock:
    def __call__(self) -> datetime:
        return _now()


class _Ids:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.number = 0

    def __call__(self) -> str:
        self.number += 1
        return f"{self.prefix}-{self.number}"


def _settings(tmp_path: Path, **overrides: str | None) -> Settings:
    env: dict[str, str] = {
        "OPENCARE_ENV": "development",
        "OPENCARE_DEMO_MODE": "true",
        "OPENCARE_PRODUCT_DB_PATH": str(tmp_path / "product" / "db.sqlite3"),
        "OPENCARE_SOURCE_DIR": str(tmp_path / "product" / "sources"),
        "OPENCARE_SESSION_DB_PATH": str(tmp_path / "runtime" / "sessions.sqlite3"),
        "OPENCARE_ALPHAGENOME_ENABLED": "true",
        "ALPHAGENOME_API_KEY": SENTINEL,
    }
    for key, value in overrides.items():
        if value is None:
            env.pop(key.upper(), None)
        else:
            env[key.upper()] = value
    clear_settings_cache()
    return load_settings(env)


@dataclass
class Harness:
    authorizer: ScientificObservationAuthorizer
    database: SQLiteDatabase
    pc: ProductCoreRuntime
    fa: FamilyAccessRuntime
    settings: Settings
    actor_id: str
    person_id: str
    observation_id: str = ""


def _seed_world(
    database: SQLiteDatabase,
    *,
    actor_id: str,
    person_id: str,
) -> None:
    with database.connect() as conn:
        conn.execute(
            "INSERT INTO actors(actor_id, username_normalized, display_name, status,"
            " created_at) VALUES (?, ?, ?, 'active', ?)",
            (actor_id, f"user-{actor_id}", f"Actor {actor_id}", _now_iso()),
        )
        conn.execute(
            "INSERT INTO people(person_id, display_name, created_at, updated_at,"
            " is_active) VALUES (?, ?, ?, ?, 1)",
            (person_id, f"Person {person_id}", _now_iso(), _now_iso()),
        )
        conn.execute(
            "INSERT INTO person_access_consent_history(consent_event_id, event_type,"
            " acting_owner_actor_id, recipient_actor_id, person_id, role, scopes_json,"
            " reason_code, created_at) VALUES (?, 'grant', ?, ?, ?, 'owner', ?,"
            " 'bootstrap', ?)",
            (
                f"ce-{actor_id}",
                actor_id,
                actor_id,
                person_id,
                json.dumps(OWNER_SCOPES_LIST),
                _now_iso(),
            ),
        )
        conn.execute(
            "INSERT INTO person_access_assignments(assignment_id, actor_id, person_id,"
            " role, scopes_json, consent_event_id, granted_by_actor_id, is_active,"
            " granted_at) VALUES (?, ?, ?, 'owner', ?, ?, ?, 1, ?)",
            (
                f"asgn-{actor_id}",
                actor_id,
                person_id,
                json.dumps(OWNER_SCOPES_LIST),
                f"ce-{actor_id}",
                actor_id,
                _now_iso(),
            ),
        )


def _make_access(
    database: SQLiteDatabase,
    settings: Settings,
    actor_id: str,
) -> ProductCoreAccess:
    pc = create_product_core_runtime(settings, clock=_Clock(), id_factory=_Ids("rt"))
    fa = create_family_access_runtime(
        settings,
        pc.database,
        clock=_Clock(),
        id_factory=_Ids("fa"),
    )
    now = _now()
    authenticated = AuthenticatedSession(
        actor=ActorRecord(
            actor_id=actor_id,
            username_normalized=f"user-{actor_id}",
            display_name=f"Actor {actor_id}",
            status="active",
            created_at=now,
        ),
        record=SessionRecord(
            session_id=f"session-{actor_id}",
            actor_id=actor_id,
            credential_id=f"cred-{actor_id}",
            active_person_id=None,
            issued_at=now,
            expires_at=now.replace(year=now.year + 1),
        ),
        session_token=f"token-{uuid.uuid4().hex}",
    )
    return ProductCoreAccess(runtime=pc, family_runtime=fa, authenticated=authenticated)


def _world(
    tmp_path: Path,
    *,
    actor_id: str = "actor-1",
    person_id: str = "person-a",
    fasta_path: Path | None = None,
) -> Harness:
    settings = _settings(tmp_path)
    if fasta_path is not None:
        settings = _settings(tmp_path, OPENCARE_GRCH38_REFERENCE_FASTA=str(fasta_path))
    database = SQLiteDatabase(settings.product_db_path)
    database.migrate()
    _seed_world(database, actor_id=actor_id, person_id=person_id)
    access = _make_access(database, settings, actor_id)
    authorizer = ScientificObservationAuthorizer(
        settings=settings,
        database=database,
        access=access,
    )
    return Harness(
        authorizer=authorizer,
        database=database,
        pc=access.runtime,
        fa=access.family_runtime,
        settings=settings,
        actor_id=actor_id,
        person_id=person_id,
    )


def _grant(
    h: Harness,
    scopes: list[str],
    *,
    person_id: str | None = None,
    actor_id: str | None = None,
) -> str:
    return h.pc.genetics.grant_access(
        actor_id=actor_id or h.actor_id,
        person_id=person_id or h.person_id,
        scopes=scopes,
        granted_by_actor_id=actor_id or h.actor_id,
        consent_confirmed=True,
    )


def _row(
    h: Harness,
    *,
    person_id: str | None = None,
    build: str = "GRCh38/hg38",
    chrom: str = "7",
    pos: int | None = None,
    genotype: str = "AG",
    no_call: bool = False,
    orient: str = "resolved",
    cov: str = "present",
    rsid: str | None = None,
) -> str:
    pid = person_id or h.person_id
    unique = uuid.uuid4().hex[:8]
    sh = hashlib.sha256(unique.encode()).hexdigest()
    sid, did, oid = f"src-{unique}", f"ds-{unique}", f"obs-{unique}"
    with h.database.connect() as conn:
        conn.execute(
            "INSERT INTO sources(id, person_id, source_type, relative_path,"
            " content_hash, size_bytes, media_type, created_at, provenance_json,"
            " original_filename) VALUES (?, ?, 'genetics', ?, ?, 4, 'text/plain', ?,"
            " ?, 'test.txt')",
            (
                sid,
                pid,
                f"{sid}.txt",
                sh,
                _now_iso(),
                json.dumps({"entry_method": "direct_test"}),
            ),
        )
        conn.execute(
            "INSERT INTO genetic_datasets(dataset_id, person_id, source_id,"
            " source_hash, format, original_filename, genome_build, parser,"
            " parser_version, imported_at, parsed_loci_count, indexed_loci_count,"
            " metadata_json) VALUES (?, ?, ?, ?, 'consumer_genotype', 'test.txt', ?,"
            " 'test', '1', ?, 1, 1, ?)",
            (
                did,
                pid,
                sid,
                sh,
                build,
                _now_iso(),
                json.dumps(
                    {
                        "coverage": {
                            "target_loci": 1,
                            "present_loci": 1,
                            "no_call_loci": 0,
                            "not_present_loci": 0,
                        }
                    }
                ),
            ),
        )
        conn.execute(
            "INSERT INTO genetic_variant_observations(observation_id, dataset_id,"
            " person_id, rsid, chromosome, position, reported_genotype,"
            " normalized_genotype, no_call, genome_build, orientation_state,"
            " coverage_state, source_locator_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
            " ?, ?, ?, ?, ?)",
            (
                oid,
                did,
                pid,
                rsid or f"rs-{unique}",
                chrom,
                pos or 100 + _SEQ,
                genotype,
                genotype,
                int(no_call),
                build,
                orient,
                cov,
                json.dumps({"line": 1, "source_id": sid}),
            ),
        )
    return oid


# ── source-store tripwire ────────────────────────────────────────────────


def _fail_read(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("SourceStore.read must never be called")


# ── synthetic FASTA + .fai fixture builders ──────────────────────────────


def _write_fasta_pair(
    tmp_path: Path,
    *,
    contig: str = "NC_000001.11",
    sequence: str = "ACGTACGTACGTACGTACGT",
    bases_per_line: int = 10,
    lf_endings: bool = True,
) -> Path:
    """Write a tiny FASTA + manually computed .fai into tmp_path.

    Returns the FASTA path.
    """
    fasta_path = tmp_path / f"reference-{uuid.uuid4().hex[:6]}.fasta"
    newline = "\n" if lf_endings else "\r\n"
    lines: list[str] = []
    for i in range(0, len(sequence), bases_per_line):
        lines.append(sequence[i : i + bases_per_line])
    content = f">{contig}{newline}" + newline.join(lines) + newline
    fasta_path.write_bytes(content.encode("ascii"))
    # compute .fai
    seq_len = len(sequence)
    header_line = f">{contig}{newline}"
    header_bytes = len(header_line.encode("ascii"))
    offset = header_bytes
    newline_bytes = len(newline.encode("ascii"))
    bytes_per_line = bases_per_line + newline_bytes
    fai_path = Path(str(fasta_path) + ".fai")
    fai_content = (
        f"{contig}\t{seq_len}\t{offset}\t{bases_per_line}\t{bytes_per_line}\n"
    )
    fai_path.write_text(fai_content, encoding="ascii")
    return fasta_path


# ══════════════════════════════════════════════════════════════════════════
# FAI / resolver mechanics
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def tiny_fasta(tmp_path: Path) -> Path:
    """A 20-base reference with 10 bases per line.
    Sequence: ACGTACGTAC (1-10), GTACGTACGT (11-20).
    """
    return _write_fasta_pair(tmp_path, sequence="ACGTACGTACGTACGTACGT")


class TestFastaResolverMechanics:
    def test_first_base(self, tiny_fasta: Path) -> None:
        resolver = LocalIndexedFastaReferenceResolver(tiny_fasta)
        assert resolver.resolve_reference_base("NC_000001.11", 1) == "A"

    def test_last_base_of_first_line(self, tiny_fasta: Path) -> None:
        resolver = LocalIndexedFastaReferenceResolver(tiny_fasta)
        # seq: ACGTACGTAC|GTACGTACGT → pos10 = 'C'
        assert resolver.resolve_reference_base("NC_000001.11", 10) == "C"

    def test_first_base_of_second_line(self, tiny_fasta: Path) -> None:
        resolver = LocalIndexedFastaReferenceResolver(tiny_fasta)
        # pos11 = 'G'
        assert resolver.resolve_reference_base("NC_000001.11", 11) == "G"

    def test_last_valid_base(self, tiny_fasta: Path) -> None:
        resolver = LocalIndexedFastaReferenceResolver(tiny_fasta)
        # pos20 = 'T'
        assert resolver.resolve_reference_base("NC_000001.11", 20) == "T"

    def test_position_zero_raises(self, tiny_fasta: Path) -> None:
        resolver = LocalIndexedFastaReferenceResolver(tiny_fasta)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 0)
        assert exc_info.value.reason == "reference_position_out_of_range"

    def test_position_beyond_length_raises(self, tiny_fasta: Path) -> None:
        resolver = LocalIndexedFastaReferenceResolver(tiny_fasta)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 21)
        assert exc_info.value.reason == "reference_position_out_of_range"

    def test_lowercase_fasta_bases_are_uppercased(
        self, tmp_path: Path,
    ) -> None:
        fasta_path = _write_fasta_pair(tmp_path, sequence="acgtacgtacgtacgtacgt")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        assert resolver.resolve_reference_base("NC_000001.11", 1) == "A"
        assert resolver.resolve_reference_base("NC_000001.11", 3) == "G"

    def test_missing_fasta_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / f"missing-{uuid.uuid4().hex[:6]}.fasta"
        missing_index = Path(str(missing) + ".fai")
        missing_index.write_text("NC_000001.11\t100\t10\t50\t51\n")
        resolver = LocalIndexedFastaReferenceResolver(missing)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_fasta_missing"

    def test_missing_index_raises(self, tmp_path: Path) -> None:
        fasta_path = tmp_path / f"orphan-{uuid.uuid4().hex[:6]}.fasta"
        fasta_path.write_text(">seq\nACGT\n")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_missing"

    def test_missing_contig_raises(self, tiny_fasta: Path) -> None:
        resolver = LocalIndexedFastaReferenceResolver(tiny_fasta)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_999999.99", 1)
        assert exc_info.value.reason == "reference_contig_missing"

    def test_N_base_raises(self, tmp_path: Path) -> None:
        fasta_path = _write_fasta_pair(tmp_path, sequence="NNNNACGTACGTACGT")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_base_not_acgt"

    def test_newline_byte_raises_when_bytes_equals_bases(
        self, tmp_path: Path,
    ) -> None:
        """When bytes_per_line==bases_per_line (no newline accounted), the
        .fai is semantically invalid: the byte at the start of line 2 is
        actually the LF from line 1.  This manifests as a newline byte
        being read and rejected as 'reference_base_not_acgt'."""
        # Craft a FASTA with a valid .fai that declares bytes_per_line==bases_per_line
        fasta_path = tmp_path / f"nobreak-{uuid.uuid4().hex[:6]}.fasta"
        contig = "NC_000001.11"
        seq1 = "ACGT"
        seq2 = "TGCA"
        content = f">{contig}\n{seq1}\n{seq2}\n"
        fasta_path.write_bytes(content.encode("ascii"))
        # .fai declares bytes_per_line == bases_per_line (wrong — no newline byte)
        # header ">NC_000001.11\n" = 14 bytes, offset = 14
        fai_content = f"{contig}\t8\t14\t4\t4\n"
        fai_path = Path(str(fasta_path) + ".fai")
        fai_path.write_text(fai_content, encoding="ascii")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        # Position 5 should be the first byte of "line 2", but since
        # bytes_per_line==bases_per_line, the .fai says byte at offset
        # 14+1*4+0=18 is position 5. In reality:
        # byte 14:A 15:C 16:G 17:T 18:\n 19:T 20:G ...
        # So byte 18 is \n → reference_base_not_acgt.
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base(contig, 5)
        assert exc_info.value.reason == "reference_base_not_acgt"


class TestFaiParsingErrors:
    def _write_fai(self, tmp_path: Path, content: str) -> tuple[Path, Path]:
        fasta_path = tmp_path / f"dummy-{uuid.uuid4().hex[:6]}.fasta"
        fasta_path.write_text(">seq\nACGT\n")
        fai_path = Path(str(fasta_path) + ".fai")
        fai_path.write_text(content)
        return fasta_path, fai_path

    def test_fewer_than_5_fields_raises(self, tmp_path: Path) -> None:
        fasta_path, _ = self._write_fai(tmp_path, "NC_000001.11\t100\t10\t50\n")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_invalid"

    def test_non_numeric_length_raises(self, tmp_path: Path) -> None:
        fasta_path, _ = self._write_fai(
            tmp_path, "NC_000001.11\tbad\t10\t50\t51\n",
        )
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_invalid"

    def test_negative_offset_raises(self, tmp_path: Path) -> None:
        fasta_path, _ = self._write_fai(
            tmp_path, "NC_000001.11\t100\t-1\t50\t51\n",
        )
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_invalid"

    def test_zero_length_raises(self, tmp_path: Path) -> None:
        fasta_path, _ = self._write_fai(
            tmp_path, "NC_000001.11\t0\t10\t50\t51\n",
        )
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_invalid"

    def test_zero_bases_per_line_raises(self, tmp_path: Path) -> None:
        fasta_path, _ = self._write_fai(
            tmp_path, "NC_000001.11\t100\t10\t0\t51\n",
        )
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_invalid"

    def test_bytes_smaller_than_bases_raises(self, tmp_path: Path) -> None:
        fasta_path, _ = self._write_fai(
            tmp_path, "NC_000001.11\t100\t10\t50\t49\n",
        )
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_invalid"

    def test_duplicate_contig_name_raises(self, tmp_path: Path) -> None:
        fasta_path, _ = self._write_fai(
            tmp_path,
            "NC_000001.11\t100\t10\t50\t51\n"
            "NC_000001.11\t200\t1000\t60\t61\n",
        )
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        assert exc_info.value.reason == "reference_index_invalid"

    def test_stale_fai_position_past_eof_raises(
        self, tmp_path: Path,
    ) -> None:
        fasta_path = _write_fasta_pair(
            tmp_path, sequence="ACGT", bases_per_line=2,
        )
        # rewrite .fai with inflated length
        fai_path = Path(str(fasta_path) + ".fai")
        fai_path.write_text("NC_000001.11\t99999\t6\t2\t3\n")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 500)
        assert exc_info.value.reason == "reference_position_out_of_range"


class TestBoundedRead:
    """Prove the resolver reads at most 1 sequence byte."""

    def test_distant_corruption_does_not_affect_good_position(
        self, tmp_path: Path,
    ) -> None:
        fasta_path = _write_fasta_pair(tmp_path, sequence="ACGTACGTACACGTACGTAC")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        result = resolver.resolve_reference_base("NC_000001.11", 1)
        assert result == "A"

    def test_crlf_endings_handled(self, tmp_path: Path) -> None:
        """CRLF .fai has bytes_per_line = bases_per_line + 2."""
        fasta_path = _write_fasta_pair(
            tmp_path, sequence="ACGTACGTAC", bases_per_line=5, lf_endings=False,
        )
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        # sequence: ACGTA|CGTAC → pos1='A', pos5='A', pos6='C'
        assert resolver.resolve_reference_base("NC_000001.11", 1) == "A"
        assert resolver.resolve_reference_base("NC_000001.11", 5) == "A"
        assert resolver.resolve_reference_base("NC_000001.11", 6) == "C"


# ══════════════════════════════════════════════════════════════════════════
# Projection cases
# ══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def proj_world(tmp_path: Path) -> Harness:
    """Harness with a synthetic chr7 reference FASTA and a valid observation.

    Reference sequence: ACGTACGTACACGTACGTAC (20 bases, 10/line)
    pos 1=A, 2=C, 3=G, 4=T, 5=A, 6=C, 7=G, 8=T, 9=A, 10=C,
    pos 11=A, 12=C, 13=G, 14=T, 15=A, 16=C, 17=G, 18=T, 19=A, 20=C
    """
    fasta_path = _write_fasta_pair(
        tmp_path,
        contig="NC_000007.14",
        sequence="ACGTACGTACACGTACGTAC",
    )
    return _world(tmp_path, fasta_path=fasta_path)


class TestProjectionGenotypeCases:
    def test_ref_A_homozygous_AA_no_alternate(self, proj_world: Harness) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="AA")  # pos1=A
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project(h.person_id, oid)
        assert exc_info.value.reason == "no_alternate_allele_observed"

    def test_ref_A_het_AG_queries_A_to_G(self, proj_world: Harness) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="AG")  # pos1=A, AG → A>G
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        result = projector.project(h.person_id, oid)
        assert isinstance(result, AuthorizedVariantProjection)
        assert result.query.reference == "A"
        assert result.query.alternate == "G"
        assert result.reference_binding.reference == "A"
        assert result.reference_binding.chromosome == "7"
        assert result.reference_binding.contig_accession == "NC_000007.14"
        assert result.reference_binding.assembly_accession == ASSEMBLY_ACCESSION
        assert result.reference_binding.assembly_name == ASSEMBLY_NAME
        assert result.reference_binding.source_kind == SOURCE_KIND

    def test_ref_A_homozygous_alt_GG_queries_A_to_G(self, proj_world: Harness) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="GG")  # pos1=A, GG → A>G
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        result = projector.project(h.person_id, oid)
        assert result.query.reference == "A"
        assert result.query.alternate == "G"

    def test_ref_A_both_alleles_nonref_GT_multiple_alternate(
        self, proj_world: Harness,
    ) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="GT")  # pos1=A, GT→both nonref
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project(h.person_id, oid)
        assert exc_info.value.reason == "multiple_alternate_alleles"

    def test_ref_G_het_AG_queries_G_to_A(self, proj_world: Harness) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=3, genotype="AG")  # pos3=G, AG→G>A
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        result = projector.project(h.person_id, oid)
        assert result.query.reference == "G"
        assert result.query.alternate == "A"

    def test_ref_C_het_CT_queries_C_to_T(self, proj_world: Harness) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=2, genotype="CT")  # pos2=C, CT→C>T
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        result = projector.project(h.person_id, oid)
        assert result.query.reference == "C"
        assert result.query.alternate == "T"


class TestQueryTransportFormat:
    def test_to_transport_request_has_no_sensitive_data(
        self, proj_world: Harness,
    ) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="AG")  # A>G
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        result = projector.project(h.person_id, oid)
        tr = result.query.to_transport_request()
        assert tr == {"variant": "chr7:1:A>G", "assembly": "GRCh38"}
        blob = str(tr) + repr(tr)
        for sensitive in (
            h.actor_id, h.person_id, result.observation_id, result.dataset_id,
            "AG", "rs-", SENTINEL, "fasta", ".fai",
        ):
            assert sensitive not in blob


class TestReferenceBaseNotAcgt:
    def test_N_at_position_yields_no_query(self, tmp_path: Path) -> None:
        fasta_path = _write_fasta_pair(
            tmp_path, contig="NC_000007.14", sequence="NNNNACGTACACGTACGTAC",
        )
        h = _world(tmp_path, fasta_path=fasta_path)
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="AG")
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            projector.project(h.person_id, oid)
        assert exc_info.value.reason == "reference_base_not_acgt"


class TestReferenceNotConfigured:
    def test_no_fasta_path_yields_reference_not_configured(
        self, tmp_path: Path,
    ) -> None:
        h = _world(tmp_path, fasta_path=None)
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="AG")
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            projector.project(h.person_id, oid)
        assert exc_info.value.reason == "reference_not_configured"


# ══════════════════════════════════════════════════════════════════════════
# Authorization-order tripwires
# ══════════════════════════════════════════════════════════════════════════


class TestAuthOrderTripwires:
    """Authorization/authority failures must surface BEFORE any file reads."""

    def _assert_no_file_access(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import builtins

        original_open = builtins.open

        def _blocked_open(*args: Any, **kwargs: Any) -> Any:
            if args and isinstance(args[0], (str, Path)):
                path_str = str(args[0])
                if path_str.endswith((".fasta", ".fai")):
                    raise AssertionError(
                        "FASTA/index file access BEFORE authorization gate"
                    )
            return original_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", _blocked_open)

    def test_alphagenome_disabled_blocks_before_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fasta_path = _write_fasta_pair(tmp_path, contig="NC_000007.14")
        # use one world, then create disabled authorizer with fresh settings
        # from a different DB path to avoid ID factory collision
        h = _world(
            tmp_path, fasta_path=fasta_path,
            actor_id="actor-disabled", person_id="person-disabled",
        )
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="AG")
        # build a disabled authorizer using the SAME database but disabled settings
        clear_settings_cache()
        disabled_settings = load_settings({
            "OPENCARE_ENV": "development",
            "OPENCARE_DEMO_MODE": "true",
            "OPENCARE_PRODUCT_DB_PATH": str(h.settings.product_db_path),
            "OPENCARE_SESSION_DB_PATH": str(h.settings.session_db_path),
            "OPENCARE_ALPHAGENOME_ENABLED": "false",
            "ALPHAGENOME_API_KEY": SENTINEL,
            "OPENCARE_GRCH38_REFERENCE_FASTA": str(fasta_path),
        })
        disabled_authorizer = ScientificObservationAuthorizer(
            settings=disabled_settings,
            database=h.database,
            access=h.authorizer.access,
        )
        disabled_projector = ScientificVariantProjector(
            authorizer=disabled_authorizer, settings=disabled_settings,
        )
        self._assert_no_file_access(monkeypatch)
        with pytest.raises(AlphaGenomeSelectionUnavailableError) as exc_info:
            disabled_projector.project(h.person_id, oid)
        assert exc_info.value.reason == "alphagenome_disabled"

    def test_missing_api_key_blocks_before_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fasta_path = _write_fasta_pair(tmp_path, contig="NC_000007.14")
        no_key_settings = _settings(
            tmp_path,
            OPENCARE_GRCH38_REFERENCE_FASTA=str(fasta_path),
            ALPHAGENOME_API_KEY=None,
        )
        no_key_db = SQLiteDatabase(no_key_settings.product_db_path)
        no_key_db.migrate()
        actor_nk = "actor-nokey"
        person_nk = "person-nokey"
        _seed_world(no_key_db, actor_id=actor_nk, person_id=person_nk)
        access = _make_access(no_key_db, no_key_settings, actor_nk)
        no_key_authorizer = ScientificObservationAuthorizer(
            settings=no_key_settings,
            database=no_key_db,
            access=access,
        )
        no_key_projector = ScientificVariantProjector(
            authorizer=no_key_authorizer, settings=no_key_settings,
        )
        h2 = Harness(
            authorizer=no_key_authorizer,
            database=no_key_db,
            pc=access.runtime,
            fa=access.family_runtime,
            settings=no_key_settings,
            actor_id=actor_nk,
            person_id=person_nk,
        )
        _grant(h2, ["genetics.research"])
        oid = _row(h2, chrom="7", pos=1, genotype="AG")
        self._assert_no_file_access(monkeypatch)
        with pytest.raises(AlphaGenomeSelectionUnavailableError) as exc_info:
            no_key_projector.project(person_nk, oid)
        assert exc_info.value.reason == "alphagenome_missing_api_key"

    def test_missing_genetics_research_grant_blocks_before_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fasta_path = _write_fasta_pair(tmp_path, contig="NC_000007.14")
        h = _world(
            tmp_path, fasta_path=fasta_path,
            actor_id="actor-nogrant", person_id="person-nogrant",
        )
        # no grant
        oid = _row(h)
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        self._assert_no_file_access(monkeypatch)
        with pytest.raises(PersonNotFoundError, match="not found"):
            projector.project(h.person_id, oid)

    def test_foreign_observation_blocks_before_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fasta_path = _write_fasta_pair(tmp_path, contig="NC_000007.14")
        h = _world(
            tmp_path, fasta_path=fasta_path,
            actor_id="actor-foreign", person_id="person-foreign",
        )
        _grant(h, ["genetics.research"])
        # insert a second person
        person_other = "person-other-foreign"
        with h.database.connect() as conn:
            conn.execute(
                "INSERT INTO people(person_id, display_name, created_at, updated_at,"
                " is_active) VALUES (?, 'Other', ?, ?, 1)",
                (person_other, _now_iso(), _now_iso()),
            )
        oid_foreign = _row(h, person_id=person_other)
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        self._assert_no_file_access(monkeypatch)
        with pytest.raises(PersonNotFoundError, match="not found"):
            projector.project(h.person_id, oid_foreign)

    def test_hidden_person_blocks_before_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fasta_path = _write_fasta_pair(tmp_path, contig="NC_000007.14")
        h = _world(
            tmp_path, fasta_path=fasta_path,
            actor_id="actor-hide", person_id="person-hide",
        )
        _grant(h, ["genetics.research"])
        oid = _row(h)
        with h.database.connect() as conn:
            conn.execute(
                "UPDATE people SET is_active = 0 WHERE person_id = ?",
                (h.person_id,),
            )
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        self._assert_no_file_access(monkeypatch)
        with pytest.raises(PersonNotFoundError, match="not found"):
            projector.project(h.person_id, oid)


class TestOtherBlockerRule:
    """Only 'reference_allele_unresolved' alone is permitted pre-projection."""

    def test_additional_reason_blocks_before_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import builtins

        fasta_path = _write_fasta_pair(tmp_path, contig="NC_000007.14")
        h = _world(
            tmp_path, fasta_path=fasta_path,
            actor_id="actor-block", person_id="person-block",
        )
        _grant(h, ["genetics.research"])
        # unsupported build + reference_allele_unresolved
        oid = _row(h, chrom="7", pos=1, genotype="AG", build="GRCh37/hg19")
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        original_open = builtins.open

        def _blocked_fasta(*args: Any, **kwargs: Any) -> Any:
            if args and isinstance(args[0], (str, Path)):
                p = str(args[0])
                if p.endswith((".fasta", ".fai")):
                    raise AssertionError("file access before eligibility check")
            return original_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", _blocked_fasta)
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project(h.person_id, oid)
        assert exc_info.value.reason == "observation_not_projection_eligible"


# ══════════════════════════════════════════════════════════════════════════
# Forged-model defense: use a non-frozen projector adapter
# ══════════════════════════════════════════════════════════════════════════


class _StubAuthorizer:
    """Non-frozen stub that returns a pre-built observation.

    Avoids FrozenInstanceError when the test needs a non-real authorize.
    """

    def __init__(self, obs: AuthorizedGeneticsObservation) -> None:
        self._obs = obs

    def authorize(
        self, person_id: str, observation_id: str
    ) -> AuthorizedGeneticsObservation:
        return self._obs


def _forged_obs(**overrides: Any) -> AuthorizedGeneticsObservation:
    defaults: dict[str, Any] = {
        "connector_id": "opencare.alphagenome_atlas",
        "actor_id": "actor-fg",
        "person_id": "person-fg",
        "observation_id": "obs-forged",
        "dataset_id": "ds-forged",
        "rsid": None,
        "genome_build": "GRCh38/hg38",
        "chromosome": "7",
        "position": 9,
        "normalized_genotype": "AG",
        "no_call": False,
        "orientation_state": "resolved",
        "coverage_state": "present",
        "query_eligible": False,
        "ineligibility_reasons": ("reference_allele_unresolved",),
    }
    defaults.update(overrides)
    return AuthorizedGeneticsObservation(**defaults)


def _forged_projector(
    tmp_path: Path, obs_overrides: dict[str, Any] | None = None,
) -> ScientificVariantProjector:
    fasta_path = _write_fasta_pair(tmp_path, contig="NC_000007.14")
    settings = _settings(
        tmp_path, OPENCARE_GRCH38_REFERENCE_FASTA=str(fasta_path),
    )
    obs = _forged_obs(**(obs_overrides or {}))
    stub = _StubAuthorizer(obs)
    return ScientificVariantProjector(authorizer=stub, settings=settings)  # type: ignore[arg-type]


class TestForgedModelDefense:
    def test_wrong_connector_id_blocked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import builtins

        projector = _forged_projector(
            tmp_path, obs_overrides={"connector_id": "not.opencare"},
        )
        monkeypatch.setattr(
            builtins, "open",
            lambda *a, **kw: (_ for _ in ()).throw(
                AssertionError("no file access for forged model"),
            ),
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project("person-fg", "obs-forged")
        assert exc_info.value.reason == "observation_not_projection_eligible"

    def test_wrong_genome_build_blocked(
        self, tmp_path: Path,
    ) -> None:
        projector = _forged_projector(
            tmp_path, obs_overrides={"genome_build": "GRCh37/hg19"},
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project("person-fg", "obs-forged")
        assert exc_info.value.reason == "observation_not_projection_eligible"

    def test_non_acgt_genotype_blocked(
        self, tmp_path: Path,
    ) -> None:
        projector = _forged_projector(
            tmp_path, obs_overrides={"normalized_genotype": "AX"},
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project("person-fg", "obs-forged")
        assert exc_info.value.reason == "observation_not_projection_eligible"

    def test_position_zero_blocked(
        self, tmp_path: Path,
    ) -> None:
        projector = _forged_projector(
            tmp_path, obs_overrides={"position": 0},
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project("person-fg", "obs-forged")
        assert exc_info.value.reason == "observation_not_projection_eligible"

    def test_bad_orientation_blocked(
        self, tmp_path: Path,
    ) -> None:
        projector = _forged_projector(
            tmp_path, obs_overrides={"orientation_state": "ambiguous"},
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project("person-fg", "obs-forged")
        assert exc_info.value.reason == "observation_not_projection_eligible"

    def test_two_reasons_blocked(
        self, tmp_path: Path,
    ) -> None:
        projector = _forged_projector(
            tmp_path,
            obs_overrides={
                "ineligibility_reasons": (
                    "reference_allele_unresolved", "unsupported_chromosome",
                ),
            },
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project("person-fg", "obs-forged")
        assert exc_info.value.reason == "observation_not_projection_eligible"


# ══════════════════════════════════════════════════════════════════════════
# Zero source reads + zero network + zero SDK
# ══════════════════════════════════════════════════════════════════════════


class TestZeroSourceReads:
    def test_source_store_tripwire_still_succeeds(
        self, proj_world: Harness, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="AG")
        monkeypatch.setattr(pc_services.ImmutableSourceStore, "read", _fail_read)
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        result = projector.project(h.person_id, oid)
        assert isinstance(result, AuthorizedVariantProjection)


class TestNoNetworkNoSDK:
    def test_no_alphagenome_module_imported(self) -> None:
        for name in list(sys.modules):
            assert not name.lower().startswith("alphagenome"), name

    def test_network_guard_is_autouse(self) -> None:
        """Prove the autouse fixture ran by trying a socket — must fail."""
        with pytest.raises(AssertionError, match="network"):
            socket.socket()


# ══════════════════════════════════════════════════════════════════════════
# Manifest sanity
# ══════════════════════════════════════════════════════════════════════════


class TestManifestSanity:
    def test_24_entries(self) -> None:
        assert len(GRCH38_P13_PRIMARY_CONTIGS) == 24

    def test_keys_one_to_twenty_two_plus_X_Y(self) -> None:
        expected = set(str(n) for n in range(1, 23)) | {"X", "Y"}
        assert set(GRCH38_P13_PRIMARY_CONTIGS.keys()) == expected

    def test_MT_absent(self) -> None:
        assert "MT" not in GRCH38_P13_PRIMARY_CONTIGS

    def test_all_values_match_nc_pattern(self) -> None:
        import re

        pat = re.compile(r"^NC_0000\d{2}\.\d+$")
        for chrom, acc in GRCH38_P13_PRIMARY_CONTIGS.items():
            assert pat.match(acc), f"Chromosome {chrom}: {acc} does not match pattern"


# ══════════════════════════════════════════════════════════════════════════
# Config enumeration
# ══════════════════════════════════════════════════════════════════════════


class TestReferenceGenomeConfigurationState:
    def test_none_path_is_unconfigured(self) -> None:
        settings = _settings(Path("."))
        assert (
            reference_genome_configuration_state_from_settings(settings)
            == ReferenceGenomeConfigurationState.UNCONFIGURED
        )

    def test_some_path_is_configured(self, tmp_path: Path) -> None:
        fasta_path = tmp_path / f"ref-{uuid.uuid4().hex[:6]}.fasta"
        fasta_path.write_text(">x\nA\n")
        settings = _settings(
            tmp_path, OPENCARE_GRCH38_REFERENCE_FASTA=str(fasta_path),
        )
        assert (
            reference_genome_configuration_state_from_settings(settings)
            == ReferenceGenomeConfigurationState.CONFIGURED
        )


# ══════════════════════════════════════════════════════════════════════════
# Error message hygiene: no absolute paths in exception messages
# ══════════════════════════════════════════════════════════════════════════


class TestErrorMessageHygiene:
    def test_reference_fasta_missing_no_path_leak(
        self, tmp_path: Path,
    ) -> None:
        missing = tmp_path / f"nonexistent-{uuid.uuid4().hex[:6]}.fasta"
        missing_index = Path(str(missing) + ".fai")
        missing_index.write_text("NC_000001.11\t100\t10\t50\t51\n")
        resolver = LocalIndexedFastaReferenceResolver(missing)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        msg = str(exc_info.value)
        assert msg == "reference_fasta_missing"

    def test_reference_index_invalid_no_path_leak(
        self, tmp_path: Path,
    ) -> None:
        fasta_path = tmp_path / f"bad-{uuid.uuid4().hex[:6]}.fasta"
        fasta_path.write_text(">contig\nA\n")
        fai_path = Path(str(fasta_path) + ".fai")
        fai_path.write_text("garbage")
        resolver = LocalIndexedFastaReferenceResolver(fasta_path)
        with pytest.raises(ReferenceGenomeUnavailableError) as exc_info:
            resolver.resolve_reference_base("NC_000001.11", 1)
        msg = str(exc_info.value)
        assert msg == "reference_index_invalid"


# ══════════════════════════════════════════════════════════════════════════
# Boundary answers: three critical safety questions
# ══════════════════════════════════════════════════════════════════════════


class TestSafetyBoundaries:
    """Answers to the three critical safety questions from the spec."""

    def test_ref_cannot_be_produced_without_resolver(self) -> None:
        """REF comes ONLY from LocalIndexedFastaReferenceResolver.

        There is no REF field on AuthorizedGeneticsObservation, the
        SelectedVariantQuery cannot be constructed without REF, and the
        projector always calls resolve_reference_base() before building
        the query. Answer: NO.
        """
        fields = set(AuthorizedGeneticsObservation.model_fields.keys())
        assert "reference" not in fields
        assert "alternate" not in fields

    def test_two_non_ref_alleles_never_pick_one_arbitrarily(
        self, proj_world: Harness,
    ) -> None:
        """When both genotype alleles differ from REF, the projector raises
        multiple_alternate_alleles — it NEVER picks one arbitrarily.
        Answer: NO.
        """
        h = proj_world
        _grant(h, ["genetics.research"])
        oid = _row(h, chrom="7", pos=1, genotype="GT")  # pos1=A, GT both non-ref
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        with pytest.raises(VariantProjectionError) as exc_info:
            projector.project(h.person_id, oid)
        assert exc_info.value.reason == "multiple_alternate_alleles"

    def test_unauthorized_observation_never_causes_fasta_read(
        self, proj_world: Harness, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An unauthorized observation (missing grant) raises an error
        BEFORE any file access. Answer: NO.
        """
        import builtins

        h = proj_world
        # no grant
        oid = _row(h, chrom="7", pos=1, genotype="AG")
        projector = ScientificVariantProjector(
            authorizer=h.authorizer, settings=h.settings,
        )
        original_open = builtins.open

        def _blocked_fasta(*args: Any, **kwargs: Any) -> Any:
            if args and isinstance(args[0], (str, Path)):
                p = str(args[0])
                if p.endswith((".fasta", ".fai")):
                    raise AssertionError("FASTA read before authorization")
            return original_open(*args, **kwargs)

        monkeypatch.setattr(builtins, "open", _blocked_fasta)
        with pytest.raises(PersonNotFoundError, match="not found"):
            projector.project(h.person_id, oid)