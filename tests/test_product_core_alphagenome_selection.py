"""Service-level tests for AlphaGenome stage C observation authorization.

The ``ScientificObservationAuthorizer`` seam is exercised against a real
``ProductCoreAccess`` boundary (``require_genetics`` → ``require_person`` +
genetics grant), built service-level via the production runtime factories —
no parallel authorization path is tested.
"""

from __future__ import annotations

import hashlib
import inspect
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
    _alphagenome_contig,
)
from app.product_core.sqlite import SQLiteDatabase

SENTINEL = "alpha-secret-SENTINEL-do-not-leak"

SYNTHETIC_GENOTYPE = (
    b"# rsid chromosome position genotype\n"
    b"rsDemoPGX 10 1001 AG\n"
    b"rsDemoNoCall 11 1101 --\n"
    b"rsDemoAmbiguous 12 1201 AT\n"
    b"unique-raw-marker 20 2001 CC\n"
)

OWNER_SCOPES_LIST = sorted(OWNER_SCOPES)

_SEQ = 0


def _now() -> datetime:
    global _SEQ
    _SEQ += 1
    return datetime(2026, 9, 10, 12, 0, _SEQ % 60, tzinfo=UTC)


def _now_iso() -> str:
    return _now().isoformat()


# ── socket guard (pattern: tests/test_scientific_evidence_alphagenome_config.py) ──


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
    """Actor + active Person + consent event + active owner assignment.

    Raw INSERTs follow the existing service-level precedent
    (tests/test_product_core_genetics.py inserts actors directly).
    """
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
    """Real service-level ProductCoreAccess via the production factories
    (pattern: tests/test_product_core_access_enforcement.py:66-93)."""
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
) -> Harness:
    settings = _settings(tmp_path)
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
    """Genetics grant via the service API (GeneticsService.grant_access)."""
    return h.pc.genetics.grant_access(
        actor_id=actor_id or h.actor_id,
        person_id=person_id or h.person_id,
        scopes=scopes,
        granted_by_actor_id=actor_id or h.actor_id,
        consent_confirmed=True,
    )


# ── direct observation seeding for the eligibility matrix ────────────────


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
    """One full observation→dataset→source chain via direct INSERTs
    (style mirrors tests/test_product_core_genetics.py)."""
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


# ── main fixture ──────────────────────────────────────────────────────────


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    """DB + actor + person + assignment + research grant + one clean row."""
    h = _world(tmp_path)
    _grant(h, ["genetics.research"])
    h.observation_id = _row(h, rsid="rsDemoClean")
    return h


# ── A. config gate ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"OPENCARE_ALPHAGENOME_ENABLED": "false"}, "alphagenome_disabled"),
        ({"ALPHAGENOME_API_KEY": None}, "alphagenome_missing_api_key"),
    ],
)
def test_config_gate_blocks_before_any_db_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, str | None],
    reason: str,
) -> None:
    """Gate tripwire: any database session (uow) before the gate is a hard
    failure — proves ZERO SELECTs, including against observations."""
    h = _world(tmp_path)
    _grant(h, ["genetics.research"])
    oid = _row(h)

    def _no_db(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("database must not be queried before the config gate")

    monkeypatch.setattr(SQLiteDatabase, "uow", _no_db)
    gated = ScientificObservationAuthorizer(
        settings=_settings(tmp_path, **overrides),
        database=h.database,
        access=h.authorizer.access,
    )
    with pytest.raises(AlphaGenomeSelectionUnavailableError) as exc_info:
        gated.authorize(h.person_id, oid)
    assert exc_info.value.reason == reason


def test_configured_state_proceeds_past_gate(
    harness: Harness,
) -> None:
    result = harness.authorizer.authorize(harness.person_id, harness.observation_id)
    assert isinstance(result, AuthorizedGeneticsObservation)


def test_api_key_never_surfaces(
    tmp_path: Path,
) -> None:
    """Sentinel key must not appear in any selection, error, or reason."""
    h = _world(tmp_path)
    _grant(h, ["genetics.research"])
    oid = _row(h)
    result = h.authorizer.authorize(h.person_id, oid)
    blob = str(result) + repr(result) + result.model_dump_json()
    assert SENTINEL not in blob

    disabled = ScientificObservationAuthorizer(
        settings=_settings(tmp_path, OPENCARE_ALPHAGENOME_ENABLED="false"),
        database=h.database,
        access=h.authorizer.access,
    )
    with pytest.raises(AlphaGenomeSelectionUnavailableError) as exc_info:
        disabled.authorize(h.person_id, oid)
    assert SENTINEL not in repr(exc_info.value)
    assert SENTINEL not in str(exc_info.value)
    assert exc_info.value.reason == "alphagenome_disabled"


# ── B. authority via ProductCoreAccess.require_genetics ──────────────────


def test_delegation_to_require_genetics_is_literal() -> None:
    """The module delegates; it does not re-implement the boundary."""
    source = inspect.getsource(ScientificObservationAuthorizer)
    assert 'require_genetics(person_id, "genetics.research")' in source
    assert "_require_person_read" not in source
    assert "person_access_assignments" not in source
    assert "genetic_access_grants" not in source


def test_own_person_with_research_grant_authorized(
    harness: Harness,
) -> None:
    h = harness
    result = h.authorizer.authorize(h.person_id, h.observation_id)
    assert isinstance(result, AuthorizedGeneticsObservation)
    assert result.person_id == h.person_id
    assert result.observation_id == h.observation_id
    assert result.actor_id == h.actor_id
    assert result.connector_id
    assert result.query_eligible is False
    assert result.ineligibility_reasons == ("reference_allele_unresolved",)


@pytest.mark.parametrize(
    "grant_scope",
    ["genetics.read", "genetics.write", "genetics.export", "genetics.compare"],
)
def test_non_research_grants_raise_person_not_found(
    tmp_path: Path,
    grant_scope: str,
) -> None:
    suffix = grant_scope.split(".")[-1]
    h = _world(tmp_path, actor_id=f"a-{suffix}", person_id=f"p-{suffix}")
    _grant(h, [grant_scope])
    oid = _row(h)
    with pytest.raises(PersonNotFoundError, match="^Person was not found\\.$"):
        h.authorizer.authorize(h.person_id, oid)


def test_grant_revocation_blocks_fresh_call(
    harness: Harness,
) -> None:
    h = harness
    assert h.authorizer.authorize(h.person_id, h.observation_id).person_id == h.person_id
    # A revoked grant leaves no active non-revoked row → fresh call denied.
    with h.database.connect() as conn:
        conn.execute(
            "UPDATE genetic_access_grants SET revoked_at = ? WHERE revoked_at IS NULL",
            (_now_iso(),),
        )
    with pytest.raises(PersonNotFoundError, match="^Person was not found\\.$"):
        h.authorizer.authorize(h.person_id, h.observation_id)


def test_assignment_revocation_raises_person_not_found(
    tmp_path: Path,
) -> None:
    h = _world(tmp_path)
    _grant(h, ["genetics.research"])
    oid = _row(h)
    # A second active owner keeps the last-owner trigger satisfied while the
    # current actor's own assignment is revoked.
    with h.database.connect() as conn:
        conn.execute(
            "INSERT INTO actors(actor_id, username_normalized, display_name, status,"
            " created_at) VALUES ('actor-2', 'user-actor-2', 'Second', 'active', ?)",
            (_now_iso(),),
        )
        conn.execute(
            "INSERT INTO person_access_consent_history(consent_event_id, event_type,"
            " acting_owner_actor_id, recipient_actor_id, person_id, role, scopes_json,"
            " reason_code, created_at) VALUES ('ce-2', 'grant', 'actor-1', 'actor-2',"
            " ?, 'owner', ?, 'grant', ?)",
            (h.person_id, json.dumps(OWNER_SCOPES_LIST), _now_iso()),
        )
        conn.execute(
            "INSERT INTO person_access_assignments(assignment_id, actor_id,"
            " person_id, role, scopes_json, consent_event_id, granted_by_actor_id,"
            " is_active, granted_at) VALUES ('asgn-2', 'actor-2', ?, 'owner', ?,"
            " 'ce-2', 'actor-1', 1, ?)",
            (h.person_id, json.dumps(OWNER_SCOPES_LIST), _now_iso()),
        )
        conn.execute(
            "UPDATE person_access_assignments SET is_active = 0, revoked_at = ?,"
            " revoked_by_actor_id = 'actor-2' WHERE assignment_id = 'asgn-actor-1'",
            (_now_iso(),),
        )
    with pytest.raises(PersonNotFoundError, match="not found"):
        h.authorizer.authorize(h.person_id, oid)


def test_hidden_person_raises_person_not_found(
    harness: Harness,
) -> None:
    h = harness
    with h.database.connect() as conn:
        conn.execute(
            "UPDATE people SET is_active = 0, updated_at = ? WHERE person_id = ?",
            (_now_iso(), h.person_id),
        )
    with pytest.raises(PersonNotFoundError, match="not found"):
        h.authorizer.authorize(h.person_id, h.observation_id)


def test_nonexistent_person_raises_person_not_found(
    harness: Harness,
) -> None:
    h = harness
    with pytest.raises(PersonNotFoundError, match="not found"):
        h.authorizer.authorize("nonexistent-person", h.observation_id)


def test_nonexistent_observation_raises_person_not_found(
    harness: Harness,
) -> None:
    h = harness
    with pytest.raises(PersonNotFoundError, match="^Person was not found\\.$"):
        h.authorizer.authorize(h.person_id, "guessed-obs-12345")


def test_foreign_observation_under_own_person_raises_person_not_found(
    tmp_path: Path,
) -> None:
    h = _world(tmp_path)
    _grant(h, ["genetics.research"])
    person_b = "person-b"
    with h.database.connect() as conn:
        conn.execute(
            "INSERT INTO people(person_id, display_name, created_at, updated_at,"
            " is_active) VALUES (?, 'Person B', ?, ?, 1)",
            (person_b, _now_iso(), _now_iso()),
        )
    obs_b = _row(h, person_id=person_b, rsid="rsForeignSecret")
    with pytest.raises(PersonNotFoundError) as exc_info:
        h.authorizer.authorize(h.person_id, obs_b)
    message = str(exc_info.value)
    assert message == "Person was not found."
    for leak in ("rsForeignSecret", "obs-", "ds-", "GRCh38", "AG"):
        assert leak not in message


# ── C. ownership JOIN chain ──────────────────────────────────────────────


def test_query_is_person_gated_join_chain() -> None:
    """The dataset/source JOIN predicates are structural, with
    person_id consistency enforced in both JOINs.  Dirty lineage is
    unconstructible (observation/dataset FK is composite on
    (dataset_id, person_id); datasets are immutable by trigger), so the
    query text plus the happy-path resolution below is the honest proof."""
    source = inspect.getsource(ScientificObservationAuthorizer.authorize)
    assert "JOIN genetic_datasets d" in source
    assert "d.dataset_id = o.dataset_id" in source
    assert "d.person_id   = o.person_id" in source
    assert "JOIN sources s" in source
    assert "s.id        = d.source_id" in source
    assert "s.person_id = o.person_id" in source
    assert "WHERE o.observation_id = ?" in source
    assert "AND o.person_id      = ?" in source
    assert "reported_genotype" not in source
    assert "source_locator_json" not in source


def test_dirty_lineage_is_unconstructible(
    harness: Harness,
) -> None:
    """Attempted dataset-person divergence is rejected by the schema itself."""
    h = harness
    with h.database.connect() as conn, pytest.raises(Exception, match="immutable"):
            conn.execute(
                "UPDATE genetic_datasets SET person_id = 'someone-else'"
                " WHERE dataset_id = (SELECT dataset_id FROM"
                " genetic_variant_observations WHERE observation_id = ?)",
                (h.observation_id,),
            )


def test_join_resolves_real_happy_path_row(
    harness: Harness,
) -> None:
    h = harness
    result = h.authorizer.authorize(h.person_id, h.observation_id)
    with h.database.connect() as conn:
        row = conn.execute(
            "SELECT dataset_id, rsid, genome_build, chromosome, position,"
            " normalized_genotype, no_call, orientation_state, coverage_state"
            " FROM genetic_variant_observations WHERE observation_id = ?",
            (h.observation_id,),
        ).fetchone()
    assert row is not None
    assert result.dataset_id == row["dataset_id"]
    assert result.rsid == row["rsid"]
    assert result.genome_build == row["genome_build"]
    assert result.chromosome == row["chromosome"]
    assert result.position == row["position"]
    assert result.normalized_genotype == row["normalized_genotype"]
    assert result.no_call == bool(row["no_call"])
    assert result.orientation_state == row["orientation_state"]
    assert result.coverage_state == row["coverage_state"]


# ── D. eligibility matrix ────────────────────────────────────────────────


@pytest.fixture
def matrix(tmp_path: Path) -> Harness:
    h = _world(tmp_path, actor_id="actor-mx", person_id="person-mx")
    _grant(h, ["genetics.research"])
    return h


def test_clean_row_only_reference_reason(matrix: Harness) -> None:
    h = matrix
    oid = _row(h, chrom="7", build="GRCh38/hg38", cov="present", orient="resolved")
    r = h.authorizer.authorize(h.person_id, oid)
    assert r.ineligibility_reasons == ("reference_allele_unresolved",)
    assert r.query_eligible is False


@pytest.mark.parametrize(
    ("build", "chrom", "genotype", "nc", "orient", "cov", "expected"),
    [
        ("GRCh37/hg19", "7", "AG", False, "resolved", "present",
         ["unsupported_genome_build"]),
        ("unknown", "7", "AG", False, "resolved", "present",
         ["unsupported_genome_build"]),
        ("GRCh38/hg38", "MT", "A", False, "resolved", "present",
         ["unsupported_chromosome"]),
        ("GRCh38/hg38", "7", "--", True, "not_applicable", "no_call",
         ["observation_no_call", "orientation_not_applicable"]),
        ("GRCh38/hg38", "7", "AT", False, "ambiguous", "present",
         ["orientation_ambiguous"]),
        ("GRCh38/hg38", "7", "AT", False, "unresolved", "present",
         ["orientation_unresolved"]),
        ("GRCh37/hg19", "MT", "CC", True, "ambiguous", "indexed",
         ["observation_no_call", "unsupported_genome_build",
          "unsupported_chromosome", "orientation_ambiguous"]),
    ],
)
def test_reason_order_and_permanent_reference(
    matrix: Harness,
    build: str,
    chrom: str,
    genotype: str,
    nc: bool,
    orient: str,
    cov: str,
    expected: list[str],
) -> None:
    h = matrix
    oid = _row(h, build=build, chrom=chrom, genotype=genotype,
               no_call=nc, orient=orient, cov=cov)
    r = h.authorizer.authorize(h.person_id, oid)
    assert list(r.ineligibility_reasons) == expected + ["reference_allele_unresolved"]
    assert r.query_eligible is False


# ── import-pipeline integration (real importer, not just direct rows) ────


def test_real_import_pipeline_row_authorized_and_matches_db(
    tmp_path: Path,
) -> None:
    h = _world(tmp_path, actor_id="actor-imp", person_id="person-imp")
    _grant(h, ["genetics.research"])
    h.pc.genetics.import_consumer_genotype(
        person_id=h.person_id,
        payload=SYNTHETIC_GENOTYPE,
        original_filename="synthetic.txt",
        genome_build="GRCh37/hg19",
        confirmation=True,
    )
    overview = h.pc.genetics.overview(person_id=h.person_id)
    src = next(o for o in overview["observations"] if o["rsid"] == "rsDemoPGX")
    result = h.authorizer.authorize(h.person_id, src["observation_id"])
    assert result.observation_id == src["observation_id"]
    assert result.dataset_id == src["dataset_id"]
    assert result.rsid == "rsDemoPGX"
    assert result.genome_build == "GRCh37/hg19"
    assert result.normalized_genotype == src["normalized_genotype"]
    assert "unsupported_genome_build" in result.ineligibility_reasons


def test_import_pipeline_denied_without_research_grant(
    tmp_path: Path,
) -> None:
    h = _world(tmp_path, actor_id="actor-imp2", person_id="person-imp2")
    _grant(h, ["genetics.read"])
    h.pc.genetics.import_consumer_genotype(
        person_id=h.person_id,
        payload=SYNTHETIC_GENOTYPE,
        original_filename="synthetic.txt",
        genome_build="GRCh37/hg19",
        confirmation=True,
    )
    overview = h.pc.genetics.overview(person_id=h.person_id)
    src = next(o for o in overview["observations"] if o["rsid"] == "rsDemoPGX")
    with pytest.raises(PersonNotFoundError, match="^Person was not found\\.$"):
        h.authorizer.authorize(h.person_id, src["observation_id"])


def test_denial_message_carries_no_variant_data(
    tmp_path: Path,
) -> None:
    h = _world(tmp_path, actor_id="actor-dm", person_id="person-dm")
    _grant(h, ["genetics.research"])
    oid = _row(h, rsid="rsLeakCheck", genotype="CT", chrom="3", build="GRCh38/hg38")
    with h.database.connect() as conn:
        conn.execute("UPDATE genetic_access_grants SET revoked_at = ?", (_now_iso(),))
    with pytest.raises(PersonNotFoundError) as exc_info:
        h.authorizer.authorize(h.person_id, oid)
    message = str(exc_info.value)
    assert message == "Person was not found."


# ── E. REF/ALT non-constructibility ──────────────────────────────────────


def test_selection_has_no_reference_or_alternate_fields(
    harness: Harness,
) -> None:
    fields = set(AuthorizedGeneticsObservation.model_fields.keys())
    assert fields & {"reference", "alternate"} == set()
    assert "reported_genotype" not in fields
    assert "source_locator_json" not in fields
    assert fields == {
        "connector_id", "actor_id", "person_id", "observation_id", "dataset_id",
        "rsid", "genome_build", "chromosome", "position", "normalized_genotype",
        "no_call", "orientation_state", "coverage_state", "query_eligible",
        "ineligibility_reasons",
    }


def test_selected_variant_query_not_constructible_from_selection(
    harness: Harness,
) -> None:
    from pydantic import ValidationError

    from app.scientific_evidence.contracts import SelectedVariantQuery

    result = harness.authorizer.authorize(
        harness.person_id, harness.observation_id
    )
    payload = result.model_dump()
    with pytest.raises((ValidationError, TypeError)):
        SelectedVariantQuery(
            genome_build=payload["genome_build"],
            chromosome=payload["chromosome"],
            position=payload["position"],
        )
    with pytest.raises((ValidationError, TypeError, KeyError)):
        SelectedVariantQuery(**payload)


def test_module_source_mentions_no_query_model() -> None:
    import app.product_core.scientific_observation as mod

    source = inspect.getsource(mod)
    assert "SelectedVariantQuery" not in source
    assert "GeneticsService" not in source


# ── F. raw source bytes never touched ────────────────────────────────────


def test_source_store_read_never_called(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_read(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("SourceStore.read must never be called")

    monkeypatch.setattr(pc_services.ImmutableSourceStore, "read", _fail_read)
    h = harness
    for _ in range(2):
        result = h.authorizer.authorize(h.person_id, h.observation_id)
        assert isinstance(result, AuthorizedGeneticsObservation)


# ── G. no mutation, audit discipline ────────────────────────────────────


GUARDED_TABLES = (
    "genetic_variant_observations",
    "genetic_datasets",
    "sources",
    "genetic_findings",
    "genetics_research_sessions",
    "people",
)


def _table_state(database: SQLiteDatabase) -> dict[str, str]:
    state = {}
    with database.connect() as conn:
        for table in GUARDED_TABLES:
            rows = conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            digest = hashlib.sha256(
                "\n".join(str(tuple(r)) for r in rows).encode("utf-8")
            ).hexdigest()
            state[table] = f"{len(rows)}:{digest}"
    return state


def test_authorize_is_read_only(
    harness: Harness,
) -> None:
    h = harness
    before = _table_state(h.database)
    for _ in range(3):
        h.authorizer.authorize(h.person_id, h.observation_id)
    assert _table_state(h.database) == before


def test_audit_events_follow_inherited_pattern_only(
    harness: Harness,
) -> None:
    """Happy path grows access_audit_events only with the inherited
    'person.read' success rows; denials only with 'person_access.check'.
    No observation/dataset identifier ever appears in audit targets."""
    h = harness

    def _rows() -> list[Any]:
        with h.database.connect() as conn:
            return conn.execute(
                "SELECT action_code, target_class, target_id FROM access_audit_events"
            ).fetchall()

    def _codes(rows: list[Any]) -> set[str]:
        return {str(r["action_code"]) for r in rows}

    before = _rows()
    result = h.authorizer.authorize(h.person_id, h.observation_id)
    after_ok = _rows()
    grown = after_ok[len(before):]
    assert _codes(grown) == {"person.read"}
    for row in grown:
        assert row["target_class"] == "person"
        assert row["target_id"] == h.person_id
    # Second call is cache-backed (no duplicate audit) and returns the same view.
    assert h.authorizer.authorize(h.person_id, h.observation_id) == result
    assert len(_rows()) == len(after_ok)
    blob = json.dumps([dict(r) for r in _rows()])
    assert result.observation_id not in blob
    assert result.dataset_id not in blob

    with pytest.raises(PersonNotFoundError):
        h.authorizer.authorize("ghost-person", h.observation_id)
    denial_rows = _rows()[len(after_ok):]
    assert _codes(denial_rows) <= {"person_access.check"}
    assert not _codes(after_ok + denial_rows) - {
        "person.read", "person_access.check"
    }


# ── I/J. isolation + no HTTP wiring ──────────────────────────────────────


def test_no_sdk_modules_imported() -> None:
    for name in list(sys.modules):
        low = name.lower()
        assert not low.startswith("alphagenome"), name
        assert not low.startswith("grpc"), name
        assert low != "anndata", name


def test_authorize_signature_exact() -> None:
    params = list(
        inspect.signature(ScientificObservationAuthorizer.authorize).parameters
    )
    assert params == ["self", "person_id", "observation_id"]


def test_no_http_route_added() -> None:
    """The authorizer is unwired: no file outside the module itself or the
    stage C.1 projection module references it, so no route can exist."""
    offenders = []
    root = Path(__file__).resolve().parent.parent
    for path in (root / "app").rglob("*.py"):
        if path.name in ("scientific_observation.py", "scientific_projection.py"):
            continue
        if "ScientificObservationAuthorizer" in path.read_text(encoding="utf-8"):
            offenders.append(str(path))
    assert offenders == []


# ── misc preserved coverage ──────────────────────────────────────────────


def test_contig_helper() -> None:
    assert _alphagenome_contig("1") == "1"
    assert _alphagenome_contig("22") == "22"
    assert _alphagenome_contig("X") == "X"
    assert _alphagenome_contig("Y") == "Y"
    assert _alphagenome_contig("MT") is None
    assert _alphagenome_contig("chr1") is None
    assert _alphagenome_contig("23") is None


def test_selection_is_frozen() -> None:
    assert AuthorizedGeneticsObservation.model_config.get("frozen") is True
    assert AuthorizedGeneticsObservation.model_config.get("extra") == "forbid"


def test_all_exports() -> None:
    import app.product_core.scientific_observation as mod

    assert set(mod.__all__) == {
        "AlphaGenomeSelectionUnavailableError",
        "AuthorizedGeneticsObservation",
        "ScientificObservationAuthorizer",
    }
