from __future__ import annotations

# ruff: noqa: E501
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any, Literal

from app.product_core.errors import PersonNotFoundError, ProductCoreError, SourceNotFoundError
from app.product_core.services import (
    Clock,
    IdFactory,
    SourceService,
    default_clock,
    default_id_factory,
)
from app.product_core.sqlite import SQLiteDatabase

MAX_GENETICS_UPLOAD_BYTES = 32_000_000

PARSER_NAME = "opencare-consumer-genotype"
PARSER_VERSION = "1"
GENOME_BUILDS = frozenset({"GRCh37/hg19", "GRCh38/hg38", "unknown"})
GENETICS_SCOPES = frozenset(
    {"genetics.read", "genetics.write", "genetics.research", "genetics.compare", "genetics.export"}
)
EVIDENCE_LEVELS = frozenset({"Clinical", "High", "Moderate", "Low", "Exploratory", "Conflicting"})
FINDING_STATUSES = frozenset({"pending", "reviewed", "dismissed", "unsupported", "conflicting"})


class GeneticsValidationError(ProductCoreError, ValueError):
    pass


@dataclass(frozen=True)
class ParsedObservation:
    rsid: str | None
    chromosome: str
    position: int
    reported_genotype: str
    normalized_genotype: str
    no_call: bool
    orientation_state: str
    line_number: int


@dataclass(frozen=True)
class EvidenceEntry:
    evidence_id: str
    pack_id: str
    pack_version: str
    rsid: str | None
    chromosome: str | None
    position: int | None
    gene: str | None
    genome_build: str
    genotype_condition: str
    category: str
    title: str
    association: str
    evidence_level: str
    source_name: str
    source_citation: str
    source_url: str | None
    limitations: tuple[str, ...]
    orientation_metadata: str
    tags: tuple[str, ...] = ()
    medication_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportResult:
    dataset_id: str
    source_id: str
    parsed_loci_count: int
    indexed_loci_count: int
    findings_count: int


@dataclass(frozen=True)
class GeneticsService:
    database: SQLiteDatabase
    sources: SourceService
    data_dir: Path
    clock: Clock = default_clock
    id_factory: IdFactory = default_id_factory

    def grant_access(
        self,
        *,
        actor_id: str,
        person_id: str,
        scopes: Iterable[str],
        granted_by_actor_id: str,
        consent_confirmed: bool,
    ) -> str:
        normalized = sorted(set(scopes))
        if not consent_confirmed or not normalized or not set(normalized) <= GENETICS_SCOPES:
            raise GeneticsValidationError("explicit genetics consent and valid scopes are required")
        grant_id = self.id_factory()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            if uow.people.get(person_id) is None:
                raise PersonNotFoundError("person not found")
            uow.connection.execute(
                """
                INSERT INTO genetic_access_grants(
                    grant_id, actor_id, person_id, scopes_json, consent_confirmed,
                    granted_by_actor_id, created_at, revoked_at
                ) VALUES (?, ?, ?, ?, 1, ?, ?, NULL)
                """,
                (
                    grant_id,
                    actor_id,
                    person_id,
                    json.dumps(normalized, separators=(",", ":")),
                    granted_by_actor_id,
                    self._now(),
                ),
            )
        return grant_id

    def revoke_access(self, *, grant_id: str, person_id: str) -> None:
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            uow.connection.execute(
                """
                UPDATE genetic_access_grants
                SET revoked_at = ?
                WHERE grant_id = ? AND person_id = ? AND revoked_at IS NULL
                """,
                (self._now(), grant_id, person_id),
            )

    def has_scope(self, *, actor_id: str, person_id: str, scope: str) -> bool:
        if scope not in GENETICS_SCOPES:
            return False
        with self.database.uow() as uow:
            assert uow.connection is not None
            row = uow.connection.execute(
                """
                SELECT scopes_json FROM genetic_access_grants
                WHERE actor_id = ? AND person_id = ? AND consent_confirmed = 1 AND revoked_at IS NULL
                ORDER BY created_at DESC, grant_id DESC LIMIT 1
                """,
                (actor_id, person_id),
            ).fetchone()
            return row is not None and scope in json.loads(row["scopes_json"])

    def import_consumer_genotype(
        self,
        *,
        person_id: str,
        payload: bytes,
        original_filename: str,
        genome_build: str = "unknown",
        confirmation: bool,
        selected_loci: Iterable[str] = (),
    ) -> ImportResult:
        if not confirmation:
            raise GeneticsValidationError("genetics_import_confirmation_required")
        if genome_build not in GENOME_BUILDS:
            raise GeneticsValidationError("unsupported_genome_build")
        if not payload or len(payload) > MAX_GENETICS_UPLOAD_BYTES:
            raise GeneticsValidationError("genetics_upload_bytes_limit_exceeded")
        variants = parse_consumer_genotype(payload)
        entries = self._load_evidence_entries()
        self.seed_evidence_pack(entries)
        targets = {entry.rsid for entry in entries if entry.rsid}
        targets.update(value.strip() for value in selected_loci if value.strip())
        indexed = [variant for variant in variants if variant.rsid in targets]
        source = self.sources.register_genetics_payload(
            person_id,
            payload,
            original_filename=original_filename,
            media_type="text/plain",
            provenance={
                "entry_method": "local_genetics_import",
                "format": "consumer_genotype",
                "parser": PARSER_NAME,
                "parser_version": PARSER_VERSION,
            },
        )
        dataset_id = self.id_factory()
        metadata = {
            "coverage": {
                "target_loci": len(targets),
                "present_loci": sum(1 for item in indexed if not item.no_call),
                "no_call_loci": sum(1 for item in indexed if item.no_call),
                "not_present_loci": max(0, len(targets) - len({item.rsid for item in indexed})),
            },
            "selective_indexing": True,
        }
        try:
            with self.database.uow(begin_mode="IMMEDIATE") as uow:
                assert uow.connection is not None
                uow.connection.execute(
                    """
                    INSERT INTO genetic_datasets(
                        dataset_id, person_id, source_id, source_hash, format, original_filename,
                        genome_build, parser, parser_version, imported_at, parsed_loci_count,
                        indexed_loci_count, metadata_json
                    ) VALUES (?, ?, ?, ?, 'consumer_genotype', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dataset_id,
                        person_id,
                        source.id,
                        source.content_hash,
                        original_filename.strip(),
                        genome_build,
                        PARSER_NAME,
                        PARSER_VERSION,
                        self._now(),
                        len(variants),
                        len(indexed),
                        json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                    ),
                )
                for item in indexed:
                    observation_id = self.id_factory()
                    uow.connection.execute(
                        """
                        INSERT INTO genetic_variant_observations(
                            observation_id, dataset_id, person_id, rsid, chromosome, position,
                            reported_genotype, normalized_genotype, no_call, genome_build,
                            orientation_state, coverage_state, source_locator_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            observation_id,
                            dataset_id,
                            person_id,
                            item.rsid,
                            item.chromosome,
                            item.position,
                            item.reported_genotype,
                            item.normalized_genotype,
                            int(item.no_call),
                            genome_build,
                            item.orientation_state,
                            "no_call" if item.no_call else "present",
                            json.dumps({"line": item.line_number, "source_id": source.id}),
                        ),
                    )
                    for entry in entries:
                        if _entry_matches(entry, item, genome_build):
                            finding_id = self.id_factory()
                            uow.connection.execute(
                                """
                                INSERT OR IGNORE INTO genetic_findings(
                                    finding_id, person_id, observation_id, evidence_entry_id, status,
                                    category, evidence_level, title, gene, association,
                                    provenance_json, created_at, reviewed_at
                                )
                                SELECT ?, ?, ?, evidence_entry_id, 'pending', ?, ?, ?, ?, ?, ?, ?, NULL
                                FROM genetic_evidence_entries
                                WHERE pack_id = ? AND pack_version = ? AND evidence_id = ?
                                """,
                                (
                                    finding_id,
                                    person_id,
                                    observation_id,
                                    entry.category,
                                    entry.evidence_level,
                                    entry.title,
                                    entry.gene,
                                    entry.association,
                                    json.dumps(
                                        {
                                            "source_id": source.id,
                                            "source_hash": source.content_hash,
                                            "dataset_id": dataset_id,
                                            "observation_id": observation_id,
                                            "evidence_id": entry.evidence_id,
                                            "parser": PARSER_NAME,
                                            "parser_version": PARSER_VERSION,
                                        },
                                        sort_keys=True,
                                        separators=(",", ":"),
                                    ),
                                    self._now(),
                                    entry.pack_id,
                                    entry.pack_version,
                                    entry.evidence_id,
                                ),
                            )
            return ImportResult(
                dataset_id, source.id, len(variants), len(indexed), self._finding_count(dataset_id)
            )
        except BaseException:
            self._remove_unreferenced_source(source.id)
            raise

    def seed_evidence_pack(self, entries: Iterable[EvidenceEntry]) -> int:
        inserted = 0
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            for entry in entries:
                cursor = uow.connection.execute(
                    """
                    INSERT OR IGNORE INTO genetic_evidence_entries(
                        evidence_entry_id, pack_id, pack_version, evidence_id, rsid, chromosome,
                        position, gene, genome_build, genotype_condition, category, title,
                        association, effect_direction, evidence_level, source_name, source_citation,
                        source_url, source_version_date, limitations_json, orientation_metadata, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        f"{entry.pack_id}:{entry.pack_version}:{entry.evidence_id}",
                        entry.pack_id,
                        entry.pack_version,
                        entry.evidence_id,
                        entry.rsid,
                        entry.chromosome,
                        entry.position,
                        entry.gene,
                        entry.genome_build,
                        entry.genotype_condition,
                        entry.category,
                        entry.title,
                        entry.association,
                        entry.evidence_level,
                        entry.source_name,
                        entry.source_citation,
                        entry.source_url,
                        json.dumps(list(entry.limitations), separators=(",", ":")),
                        entry.orientation_metadata,
                        json.dumps(list(entry.tags), separators=(",", ":")),
                    ),
                )
                inserted += cursor.rowcount
        return inserted

    def overview(self, *, person_id: str) -> dict[str, Any]:
        with self.database.uow() as uow:
            assert uow.connection is not None
            dataset = uow.connection.execute(
                "SELECT * FROM genetic_datasets WHERE person_id = ? ORDER BY imported_at DESC, dataset_id DESC LIMIT 1",
                (person_id,),
            ).fetchone()
            if dataset is None:
                return {"person_id": person_id, "dataset": None, "findings": [], "observations": []}
            observations = uow.connection.execute(
                "SELECT * FROM genetic_variant_observations WHERE dataset_id = ? ORDER BY chromosome, position, observation_id",
                (dataset["dataset_id"],),
            ).fetchall()
            findings = uow.connection.execute(
                """
                SELECT f.*, e.evidence_id, e.pack_id, e.pack_version, e.source_name,
                       e.source_citation, e.source_url, e.limitations_json
                FROM genetic_findings f
                JOIN genetic_evidence_entries e ON e.evidence_entry_id = f.evidence_entry_id
                WHERE f.person_id = ? ORDER BY f.created_at, f.finding_id
                """,
                (person_id,),
            ).fetchall()
            levels = Counter(row["evidence_level"] for row in findings)
            categories = Counter(row["category"] for row in findings)
            medications = {
                str(row["normalized_name"])
                for row in uow.connection.execute(
                    """
                    SELECT d.normalized_name
                    FROM canonical_records r
                    JOIN canonical_medication_details d ON d.record_id = r.id
                    WHERE r.person_id = ? AND r.fact_type = 'medication' AND r.is_active = 1
                    """,
                    (person_id,),
                ).fetchall()
            }
            entries = {entry.evidence_id: entry for entry in self._load_evidence_entries()}
            pgx_intersections = []
            for row in findings:
                if row["status"] != "reviewed":
                    continue
                entry = entries.get(str(row["evidence_id"]))
                if entry is None or entry.category != "pgx":
                    continue
                matches = sorted(
                    medication
                    for medication in entry.medication_names
                    if medication.casefold() in medications
                )
                for medication in matches:
                    pgx_intersections.append(
                        {
                            "finding_id": row["finding_id"],
                            "gene": row["gene"],
                            "medication_name": medication,
                            "association": row["association"],
                            "evidence_level": row["evidence_level"],
                            "source_citation": row["source_citation"],
                            "limitations": json.loads(row["limitations_json"]),
                            "action": "association_only",
                        }
                    )
            return {
                "person_id": person_id,
                "dataset": dict(dataset),
                "coverage": json.loads(dataset["metadata_json"])["coverage"],
                "observations": [dict(row) for row in observations],
                "findings": [dict(row) for row in findings],
                "evidence_level_distribution": dict(levels),
                "category_distribution": dict(categories),
                "pgx_intersections": pgx_intersections,
            }

    def review_finding(
        self, *, finding_id: str, person_id: str, actor_id: str, status: str, reason: str | None
    ) -> dict[str, Any]:
        if status not in FINDING_STATUSES or status == "pending":
            raise GeneticsValidationError("invalid_finding_review_status")
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            row = uow.connection.execute(
                "SELECT status FROM genetic_findings WHERE finding_id = ? AND person_id = ?",
                (finding_id, person_id),
            ).fetchone()
            if row is None:
                raise SourceNotFoundError("genetics finding not found")
            prior = str(row["status"])
            now = self._now()
            uow.connection.execute(
                "UPDATE genetic_findings SET status = ?, reviewed_at = ? WHERE finding_id = ? AND person_id = ?",
                (status, now, finding_id, person_id),
            )
            uow.connection.execute(
                """
                INSERT INTO genetic_finding_reviews(
                    review_id, finding_id, person_id, actor_id, prior_status, new_status, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.id_factory(), finding_id, person_id, actor_id, prior, status, reason, now),
            )
        return {
            "finding_id": finding_id,
            "person_id": person_id,
            "status": status,
            "reviewed_at": now,
        }

    def build_research_packet(
        self,
        *,
        person_id: str,
        finding_ids: Iterable[str],
        canonical_records: Iterable[dict[str, Any]] = (),
        second_person_id: str | None = None,
    ) -> dict[str, Any]:
        ids = list(dict.fromkeys(finding_ids))
        records = [dict(item) for item in canonical_records]
        for record in records:
            if record.get("person_id", person_id) != person_id:
                raise GeneticsValidationError("cross_person_record_selection_rejected")
        with self.database.uow() as uow:
            assert uow.connection is not None
            findings = []
            for finding_id in ids:
                row = uow.connection.execute(
                    """
                    SELECT f.*, o.rsid, o.chromosome, o.position, o.reported_genotype,
                           o.normalized_genotype, o.genome_build, e.evidence_id, e.source_name,
                           e.source_citation, e.limitations_json
                    FROM genetic_findings f
                    JOIN genetic_variant_observations o ON o.observation_id = f.observation_id
                    JOIN genetic_evidence_entries e ON e.evidence_entry_id = f.evidence_entry_id
                    WHERE f.finding_id = ? AND f.person_id = ? AND f.status = 'reviewed'
                    """,
                    (finding_id, person_id),
                ).fetchone()
                if row is None:
                    raise GeneticsValidationError("research_selection_not_authorized_or_reviewed")
                findings.append(dict(row))
        packet = {
            "person_id": person_id,
            "findings": findings,
            "canonical_records": records,
            "second_person_id": second_person_id,
            "raw_genome_included": False,
        }
        packet["context_hash"] = hashlib.sha256(
            json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return packet

    def validate_research_output(
        self, output: dict[str, Any], packet: dict[str, Any], *, mode: str
    ) -> None:
        if mode not in {"evidence", "explore"}:
            raise GeneticsValidationError("invalid_research_mode")
        required = {
            "what_may_be_happening",
            "evidence_supporting",
            "evidence_against",
            "alternative_explanations",
            "missing_information",
            "confidence",
            "questions_worth_investigating",
            "claims",
        }
        if not required <= set(output):
            raise GeneticsValidationError("research_sections_incomplete")
        allowed_findings = {str(row["finding_id"]) for row in packet["findings"]}
        allowed_records = {str(row.get("id")) for row in packet["canonical_records"]}
        for claim in output["claims"]:
            status = claim.get("epistemic_status")
            if status not in {
                "observed",
                "supported",
                "plausible",
                "speculative",
                "unsupported/conflicting",
            }:
                raise GeneticsValidationError("claim_epistemic_status_required")
            if mode == "evidence" and status in {"plausible", "speculative"}:
                raise GeneticsValidationError("evidence_mode_rejects_speculation")
            if status in {"plausible", "speculative"} and not claim.get("reasoning_summary"):
                raise GeneticsValidationError("speculative_claim_requires_reasoning_summary")
            if not set(claim.get("supporting_evidence_ids", ())) <= allowed_findings:
                raise GeneticsValidationError("invalid_genetics_citation")
            if not set(claim.get("contradicting_evidence_ids", ())) <= allowed_findings:
                raise GeneticsValidationError("invalid_genetics_citation")
            if not set(claim.get("person_record_ids", ())) <= allowed_records:
                raise GeneticsValidationError("invalid_person_record_citation")
            if re.search(
                r"\b(start|stop|increase|decrease|change)\b.{0,60}\b(dose|mg|medication)\b",
                str(claim.get("claim", "")),
                re.I,
            ):
                raise GeneticsValidationError("autonomous_clinical_action_rejected")
        if packet.get("raw_genome_included"):
            raise GeneticsValidationError("raw_genome_not_allowed")

    def run_deterministic_research(
        self,
        *,
        person_id: str,
        actor_id: str,
        mode: Literal["evidence", "explore"],
        question: str,
        packet: dict[str, Any],
        provider_class: str = "deterministic_fake",
    ) -> dict[str, Any]:
        findings = packet["findings"]
        ids = [str(row["finding_id"]) for row in findings]
        status = "supported" if mode == "evidence" else "plausible"
        output: dict[str, Any] = {
            "what_may_be_happening": "Selected reviewed findings may be relevant to the question; this is not a diagnosis.",
            "evidence_supporting": ids,
            "evidence_against": [],
            "alternative_explanations": [
                "The observed relationship may be coincidental or explained by non-genetic factors."
            ],
            "missing_information": [
                "Independent clinical context and confirmatory testing may be needed."
            ],
            "confidence": "supported" if mode == "evidence" else "plausible",
            "questions_worth_investigating": [question],
            "claims": [
                {
                    "claim": "A reviewed genetics association exists in the selected context.",
                    "epistemic_status": status,
                    "supporting_evidence_ids": ids,
                    "contradicting_evidence_ids": [],
                    "person_record_ids": [],
                    "reasoning_summary": "The claim is limited to the reviewed evidence supplied in this session.",
                    "limitations": ["This is not a clinical recommendation."],
                    "missing_information": ["Clinical confirmation may be appropriate."],
                }
            ],
        }
        self.validate_research_output(output, packet, mode=mode)
        session_id = self.id_factory()
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            uow.connection.execute(
                """
                INSERT INTO genetics_research_sessions(
                    session_id, person_id, actor_id, mode, question, selected_context_json,
                    provider_class, disclosure_consent_id, context_hash, validation_result,
                    output_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, 'accepted', ?, ?)
                """,
                (
                    session_id,
                    person_id,
                    actor_id,
                    mode,
                    question,
                    json.dumps(packet, sort_keys=True, separators=(",", ":")),
                    provider_class,
                    packet["context_hash"],
                    json.dumps(output, sort_keys=True, separators=(",", ":")),
                    self._now(),
                ),
            )
            for claim in output["claims"]:
                uow.connection.execute(
                    """
                    INSERT INTO genetics_research_claims(
                        claim_id, session_id, person_id, claim_text, epistemic_status,
                        supporting_evidence_json, contradicting_evidence_json, person_record_ids_json,
                        reasoning_summary, limitations_json, missing_information_json, lifecycle, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'kept', ?)
                    """,
                    (
                        self.id_factory(),
                        session_id,
                        person_id,
                        claim["claim"],
                        claim["epistemic_status"],
                        json.dumps(claim["supporting_evidence_ids"], separators=(",", ":")),
                        json.dumps(claim["contradicting_evidence_ids"], separators=(",", ":")),
                        json.dumps(claim["person_record_ids"], separators=(",", ":")),
                        claim["reasoning_summary"],
                        json.dumps(claim["limitations"], separators=(",", ":")),
                        json.dumps(claim["missing_information"], separators=(",", ":")),
                        self._now(),
                    ),
                )
        return {
            "session_id": session_id,
            "output": output,
            "packet": {"context_hash": packet["context_hash"], "raw_genome_included": False},
        }

    def compare(self, *, person_a: str, person_b: str) -> dict[str, Any]:
        with self.database.uow() as uow:
            assert uow.connection is not None
            rows_a = uow.connection.execute(
                "SELECT rsid, normalized_genotype, no_call FROM genetic_variant_observations WHERE person_id = ? AND rsid IS NOT NULL",
                (person_a,),
            ).fetchall()
            rows_b = uow.connection.execute(
                "SELECT rsid, normalized_genotype, no_call FROM genetic_variant_observations WHERE person_id = ? AND rsid IS NOT NULL",
                (person_b,),
            ).fetchall()
        a = {
            str(row["rsid"]): str(row["normalized_genotype"])
            for row in rows_a
            if not row["no_call"]
        }
        b = {
            str(row["rsid"]): str(row["normalized_genotype"])
            for row in rows_b
            if not row["no_call"]
        }
        common = sorted(set(a) & set(b))
        ibs = Counter(_ibs(a[key], b[key]) for key in common)
        return {
            "person_a": person_a,
            "person_b": person_b,
            "common_covered_loci": len(common),
            "shared_loci": sorted(key for key in common if a[key] == b[key]),
            "differing_loci": sorted(key for key in common if a[key] != b[key]),
            "ibs0": ibs[0],
            "ibs1": ibs[1],
            "ibs2": ibs[2],
            "interpretation": "compatibility/similarity evidence only; not kinship or forensic proof",
        }

    def export_package(self, *, person_id: str, include_research: bool = False) -> bytes:
        overview = self.overview(person_id=person_id)
        dataset = overview.get("dataset")
        if dataset is None:
            raise SourceNotFoundError("genetics dataset not found")
        source = self.sources.get(str(dataset["source_id"]))
        payload = self.sources.store.read(source)
        manifest = {
            "format": "OpenCare Genetics Package v1",
            "person_id": person_id,
            "source_hash": source.content_hash,
            "dataset_id": dataset["dataset_id"],
            "raw_genome_included": True,
        }
        with io.BytesIO() as buffer:
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
                archive.writestr("source/payload.txt", payload)
                archive.writestr("dataset.json", json.dumps(dataset, indent=2, sort_keys=True))
                archive.writestr(
                    "indexed-observations.json",
                    json.dumps(overview["observations"], indent=2, sort_keys=True),
                )
                archive.writestr(
                    "reviewed-findings.json",
                    json.dumps(overview["findings"], indent=2, sort_keys=True),
                )
                if include_research:
                    archive.writestr(
                        "research-note.json", json.dumps({"included": True}, sort_keys=True)
                    )
            return buffer.getvalue()

    def _load_evidence_entries(self) -> list[EvidenceEntry]:
        path = self.data_dir / "evidence_packs" / "genetics_demo_pack.json"
        if not path.exists():
            path = Path("data") / "evidence_packs" / "genetics_demo_pack.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries: list[EvidenceEntry] = []
        for item in raw.get("entries", []):
            build = item.get("genome_build", "unknown")
            build = {"GRCh37": "GRCh37/hg19", "GRCh38": "GRCh38/hg38"}.get(build, build)
            genotypes = item.get("matching_genotypes", ())
            if not genotypes:
                continue
            entries.append(
                EvidenceEntry(
                    evidence_id=item["evidence_id"],
                    pack_id=raw["pack_id"],
                    pack_version=raw["version"],
                    rsid=item.get("rsid"),
                    chromosome=item.get("chromosome"),
                    position=item.get("position"),
                    gene=item.get("gene"),
                    genome_build=build,
                    genotype_condition=str(genotypes[0]),
                    category=item["category"],
                    title=item["title"],
                    association=item["association"],
                    evidence_level=item["evidence_level"],
                    source_name=item["source_name"],
                    source_citation=item.get("citation", item["evidence_id"]),
                    source_url=item.get("source_url"),
                    limitations=tuple(item.get("limitations", ())),
                    orientation_metadata=item.get("orientation_required", "resolved"),
                    tags=tuple(item.get("tags", ())),
                    medication_names=tuple(item.get("medication_names", ())),
                )
            )
        return entries

    def _finding_count(self, dataset_id: str) -> int:
        with self.database.uow() as uow:
            assert uow.connection is not None
            row = uow.connection.execute(
                "SELECT count(*) AS count FROM genetic_findings f JOIN genetic_variant_observations o ON o.observation_id = f.observation_id WHERE o.dataset_id = ?",
                (dataset_id,),
            ).fetchone()
            return int(row["count"])

    def _remove_unreferenced_source(self, source_id: str) -> None:
        # SourceService's store is immutable; an uncommitted dataset must not leave bytes behind.
        with self.database.uow() as uow:
            row = uow.sources.get(source_id)
            referenced = (
                uow.connection.execute(
                    "SELECT 1 FROM genetic_datasets WHERE source_id = ?",
                    (source_id,),
                ).fetchone()
                if uow.connection
                else None
            )
        if row is not None and referenced is None:
            self.sources.store._resolve_relative_path(row.relative_path).unlink(missing_ok=True)

    def _now(self) -> str:
        return self.clock().astimezone(UTC).isoformat()


def parse_consumer_genotype(payload: bytes) -> list[ParsedObservation]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GeneticsValidationError("genetics_file_must_be_utf8") from exc
    variants: list[ParsedObservation] = []
    seen: set[tuple[str | None, str, int]] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 4:
            raise GeneticsValidationError(f"invalid_consumer_genotype_row:{line_number}")
        rsid_raw, chromosome_raw, position_raw, genotype_raw = parts
        chromosome = chromosome_raw.upper().removeprefix("CHR")
        if chromosome not in {str(value) for value in range(1, 23)} | {"X", "Y", "MT"}:
            raise GeneticsValidationError(f"invalid_chromosome:{line_number}")
        try:
            position = int(position_raw)
        except ValueError as exc:
            raise GeneticsValidationError(f"invalid_position:{line_number}") from exc
        if position <= 0:
            raise GeneticsValidationError(f"invalid_position:{line_number}")
        genotype = genotype_raw.upper()
        no_call = genotype in {"--", "", "NN"}
        if not no_call and (len(genotype) != 2 or any(allele not in "ACGT" for allele in genotype)):
            raise GeneticsValidationError(f"invalid_genotype:{line_number}")
        normalized = "--" if no_call else "".join(sorted(genotype))
        rsid = None if rsid_raw in {"", ".", "-"} else rsid_raw
        key = (rsid, chromosome, position)
        if key in seen:
            raise GeneticsValidationError(f"duplicate_locus:{line_number}")
        seen.add(key)
        orientation_state = (
            "not_applicable"
            if no_call
            else ("ambiguous" if set(normalized) in ({"A", "T"}, {"C", "G"}) else "resolved")
        )
        variants.append(
            ParsedObservation(
                rsid,
                chromosome,
                position,
                genotype,
                normalized,
                no_call,
                orientation_state,
                line_number,
            )
        )
    if not variants:
        raise GeneticsValidationError("genetics_file_has_no_rows")
    return variants


def _entry_matches(entry: EvidenceEntry, variant: ParsedObservation, genome_build: str) -> bool:
    if variant.no_call or variant.orientation_state in {"ambiguous", "unresolved"}:
        return False
    if entry.rsid is not None and entry.rsid != variant.rsid:
        return False
    if entry.rsid is None and (
        entry.chromosome != variant.chromosome or entry.position != variant.position
    ):
        return False
    if entry.genome_build not in {"unknown", genome_build}:
        return False
    return entry.genotype_condition.casefold() in {
        variant.reported_genotype.casefold(),
        variant.normalized_genotype.casefold(),
    }


def _ibs(genotype_a: str, genotype_b: str) -> int:
    remaining = list(genotype_b)
    shared = 0
    for allele in genotype_a:
        if allele in remaining:
            remaining.remove(allele)
            shared += 1
    return shared
