"""Stage C server-side authorization seam; read-only; no consent (D), no
transport (E), no persistence (F); config-gating and authority are separate.

Delegates Person authorization to the existing ``ProductCoreAccess`` boundary
(``require_genetics`` → ``require_person`` + ``has_scope``) — no parallel
authorization implementation.  The inherited ``person.read`` success audit
fires through that path; no new audit writes are added at stage C.

REF/ALT projection is NOT constructible from persisted consumer-genotype data
(C.1 prerequisite): the ``genetic_variant_observations`` table has no
reference or alternate allele columns, and the local consumer-genotype diploid
calls carry no authoritative forward-strand REF/ALT annotation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from app.config import Settings
from app.product_core.access import ProductCoreAccess
from app.product_core.errors import PersonNotFoundError
from app.product_core.sqlite import SQLiteDatabase
from app.scientific_evidence.alphagenome_atlas import ATLAS_CONNECTOR_DESCRIPTOR
from app.scientific_evidence.contracts import FrozenModel
from app.scientific_evidence.operator_config import (
    AlphaGenomeConfigurationState,
    alphagenome_runtime_status_from_settings,
)

# ── primary contigs accepted by AlphaGenome Atlas (chr-prefixed projection
#    is the D/E transport concern; C checks the bare persisted chromosome) ──
_ALPHAGENOME_CONTIGS: frozenset[str] = frozenset(
    [str(n) for n in range(1, 23)] + ["X", "Y"]
)


class _SelectionUnavailableReason(enum.StrEnum):
    DISABLED = "alphagenome_disabled"
    MISSING_API_KEY = "alphagenome_missing_api_key"


class AlphaGenomeSelectionUnavailableError(Exception):
    """Config gate: AlphaGenome is not available for observation selection."""

    def __init__(self, reason: _SelectionUnavailableReason) -> None:
        super().__init__(str(reason))
        self.reason: str = reason.value


class AuthorizedGeneticsObservation(FrozenModel):
    """One server-side resolved, read-only genetics observation authorized for
    future AlphaGenome research use.  No reported genotype, no source locator
    content, no API key, and no outbound query-model allele fields."""

    connector_id: str
    actor_id: str
    person_id: str
    observation_id: str
    dataset_id: str
    rsid: str | None
    genome_build: str
    chromosome: str
    position: int
    normalized_genotype: str | None
    no_call: bool
    orientation_state: str
    coverage_state: str
    query_eligible: bool
    ineligibility_reasons: tuple[str, ...]


def _alphagenome_contig(chromosome: str) -> str | None:
    """Return the bare persisted chromosome IF it is a documented AlphaGenome
    primary contig, else ``None``.  chr-prefix mapping is a FUTURE transport
    detail; this helper is internal only."""
    if chromosome in _ALPHAGENOME_CONTIGS:
        return chromosome
    return None


@dataclass(frozen=True)
class ScientificObservationAuthorizer:
    """Server-side read-only authorization seam for exactly one persisted P3
    genetics observation.

    Delegates authority to the existing ``ProductCoreAccess`` boundary.
    Stage D wiring is trivial — the access object is already the live
    per-request instance.
    """

    settings: Settings
    database: SQLiteDatabase
    access: ProductCoreAccess

    def authorize(
        self, person_id: str, observation_id: str
    ) -> AuthorizedGeneticsObservation:
        # ── 1. config gate (B seam, before ANY database query) ──
        status = alphagenome_runtime_status_from_settings(self.settings)
        if status.configuration_state == AlphaGenomeConfigurationState.DISABLED:
            raise AlphaGenomeSelectionUnavailableError(
                _SelectionUnavailableReason.DISABLED
            )
        if (
            status.configuration_state
            == AlphaGenomeConfigurationState.MISSING_API_KEY
        ):
            raise AlphaGenomeSelectionUnavailableError(
                _SelectionUnavailableReason.MISSING_API_KEY
            )

        # ── 2. authority: delegated to ProductCoreAccess.require_genetics
        #     (person.read assignment + active non-revoked genetics.research
        #      grant; inherited audit fires through that path — no new
        #      audit writes added at stage C). ──
        self.access.require_genetics(person_id, "genetics.research")

        # ── 3. server-side resolution — exactly one row, full JOIN chain ──
        with self.database.uow() as uow:
            assert uow.connection is not None
            row = uow.connection.execute(
                """
                SELECT
                    o.observation_id,
                    o.dataset_id,
                    o.person_id,
                    o.rsid,
                    o.chromosome,
                    o.position,
                    o.normalized_genotype,
                    o.no_call,
                    o.genome_build,
                    o.orientation_state,
                    o.coverage_state
                FROM genetic_variant_observations o
                JOIN genetic_datasets d
                  ON d.dataset_id = o.dataset_id
                 AND d.person_id   = o.person_id
                JOIN sources s
                  ON s.id        = d.source_id
                 AND s.person_id = o.person_id
                WHERE o.observation_id = ?
                  AND o.person_id      = ?
                """,
                (observation_id, person_id),
            ).fetchone()

        if row is None:
            raise PersonNotFoundError("Person was not found.")

        # ── 4. deterministic local eligibility ──
        reasons: list[str] = []
        coverage_state = str(row["coverage_state"])
        no_call = bool(row["no_call"])
        genome_build = str(row["genome_build"])
        chromosome = str(row["chromosome"])
        orientation_state = str(row["orientation_state"])

        if coverage_state != "present" or no_call:
            reasons.append("observation_no_call")

        if genome_build != "GRCh38/hg38":
            reasons.append("unsupported_genome_build")

        contig = _alphagenome_contig(chromosome)
        if contig is None:
            reasons.append("unsupported_chromosome")

        if orientation_state == "ambiguous":
            reasons.append("orientation_ambiguous")
        elif orientation_state == "unresolved":
            reasons.append("orientation_unresolved")
        elif orientation_state == "not_applicable":
            reasons.append("orientation_not_applicable")

        # Consumer-genotype diploid genotype is NOT REF/ALT; binding requires
        # stage C.1 + an authoritative local reference source; no inference
        # permitted here.
        reasons.append("reference_allele_unresolved")

        return AuthorizedGeneticsObservation(
            connector_id=ATLAS_CONNECTOR_DESCRIPTOR.connector_id,
            actor_id=self.access.actor_id,
            person_id=person_id,
            observation_id=str(row["observation_id"]),
            dataset_id=str(row["dataset_id"]),
            rsid=str(row["rsid"]) if row["rsid"] is not None else None,
            genome_build=genome_build,
            chromosome=chromosome,
            position=int(row["position"]),
            normalized_genotype=(
                str(row["normalized_genotype"])
                if row["normalized_genotype"] is not None
                else None
            ),
            no_call=no_call,
            orientation_state=orientation_state,
            coverage_state=coverage_state,
            query_eligible=len(reasons) == 0,
            ineligibility_reasons=tuple(reasons),
        )


__all__ = [
    "AlphaGenomeSelectionUnavailableError",
    "AuthorizedGeneticsObservation",
    "ScientificObservationAuthorizer",
]