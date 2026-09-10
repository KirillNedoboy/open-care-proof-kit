"""Stage C.1 — Reference Allele Binding / Outbound SNV Projection.

Pinned from official NCBI assembly report GCF_000001405.39 (GRCh38.p13),
development-time lookup date 2026-09-10.
Report URL: https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/001/405/GCF_000001405.39_GRCh38.p13/GCF_000001405.39_GRCh38.p13_assembly_report.txt

Binds authorized genetics observations to a local GRCh38 reference FASTA to
derive a single REF→ALT SNV query.  Pure stdlib, read-only; no network,
no SDK, no persistence, no disclosure (D), no transport (E).
"""

from __future__ import annotations

import enum
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.config import Settings
from app.product_core.scientific_observation import (
    AuthorizedGeneticsObservation,
    ScientificObservationAuthorizer,
)
from app.scientific_evidence.alphagenome_atlas import ATLAS_CONNECTOR_DESCRIPTOR
from app.scientific_evidence.contracts import (
    AtlasGenomeBuild,
    FrozenModel,
    SelectedVariantQuery,
)

# ── pinned GRCh38.p13 primary contig → RefSeq accession.version manifest ──
# Extracted from the official NCBI FTP assembly report
# GCF_000001405.39_GRCh38.p13_assembly_report.txt, header
# "Assembly name: GRCh38.p13", "RefSeq assembly accession: GCF_000001405.39".
# Development-time lookup 2026-09-10.  MT excluded by contract.
GRCH38_P13_PRIMARY_CONTIGS: Final[Mapping[str, str]] = {
    "1": "NC_000001.11",
    "2": "NC_000002.12",
    "3": "NC_000003.12",
    "4": "NC_000004.12",
    "5": "NC_000005.10",
    "6": "NC_000006.12",
    "7": "NC_000007.14",
    "8": "NC_000008.11",
    "9": "NC_000009.12",
    "10": "NC_000010.11",
    "11": "NC_000011.10",
    "12": "NC_000012.12",
    "13": "NC_000013.11",
    "14": "NC_000014.9",
    "15": "NC_000015.10",
    "16": "NC_000016.10",
    "17": "NC_000017.11",
    "18": "NC_000018.10",
    "19": "NC_000019.10",
    "20": "NC_000020.11",
    "21": "NC_000021.9",
    "22": "NC_000022.11",
    "X": "NC_000023.11",
    "Y": "NC_000024.10",
}

ASSEMBLY_ACCESSION: Final[str] = "GCF_000001405.39"
ASSEMBLY_NAME: Final[str] = "GRCh38.p13"
SOURCE_KIND: Final[str] = "local_operator_reference_fasta"


# ── configuration enumeration ────────────────────────────────────────────


class ReferenceGenomeConfigurationState(enum.StrEnum):
    UNCONFIGURED = "unconfigured"
    CONFIGURED = "configured"


def reference_genome_configuration_state_from_settings(
    settings: Settings,
) -> ReferenceGenomeConfigurationState:
    if settings.grch38_reference_fasta is None:
        return ReferenceGenomeConfigurationState.UNCONFIGURED
    return ReferenceGenomeConfigurationState.CONFIGURED


# ── models ────────────────────────────────────────────────────────────────


class ReferenceAlleleBinding(FrozenModel):
    """One base resolved from the local GRCh38 reference at a pinned position.

    Never stores the FASTA path, API key, actor/person ids, or genotype.
    """

    assembly_accession: str
    assembly_name: str
    chromosome: str
    contig_accession: str
    position: int
    reference: str
    source_kind: str


class AuthorizedVariantProjection(FrozenModel):
    """One authorized, reference-bound SNV ready for outbound transport.

    Not persisted anywhere.
    """

    connector_id: str
    actor_id: str
    person_id: str
    observation_id: str
    dataset_id: str
    reference_binding: ReferenceAlleleBinding
    query: SelectedVariantQuery


# ── exceptions ────────────────────────────────────────────────────────────


class ReferenceGenomeUnavailableError(Exception):
    """Local reference cannot service the projection request.

    ``reason`` is a stable, bounded, machine-readable snake_case code.
    Messages contain no absolute paths, usernames, file contents, or raw
    index lines.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason: str = reason


class VariantProjectionError(Exception):
    """Projection cannot produce an outbound SNV query.

    ``reason`` is a stable, bounded, machine-readable snake_case code.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason: str = reason


# ── resolver ──────────────────────────────────────────────────────────────


class LocalIndexedFastaReferenceResolver:
    """Pure-stdlib, read-only resolver over a local FASTA + .fai index.

    No network, no subprocess, no writes, no index generation.
    Length bounds come from the .fai sidecar as-is (self-declared).
    No cryptographic or content verification of the reference FASTA.
    """

    def __init__(
        self,
        fasta_path: Path,
        index_path: Path | None = None,
    ) -> None:
        self._fasta_path = fasta_path
        self._index_path = index_path or Path(str(fasta_path) + ".fai")
        self._contigs: dict[str, _FaiRow] = {}
        self._loaded: bool = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self._fasta_path.is_file():
            raise ReferenceGenomeUnavailableError("reference_fasta_missing")
        if not self._index_path.is_file():
            raise ReferenceGenomeUnavailableError("reference_index_missing")
        contigs = _parse_fai(self._index_path)
        self._contigs = contigs
        self._loaded = True

    def resolve_reference_base(self, contig_accession: str, position: int) -> str:
        self._ensure_loaded()
        row = self._contigs.get(contig_accession)
        if row is None:
            raise ReferenceGenomeUnavailableError("reference_contig_missing")
        if position < 1 or position > row.length:
            raise ReferenceGenomeUnavailableError("reference_position_out_of_range")
        # one-base random access
        line_index = (position - 1) // row.bases_per_line
        within = (position - 1) % row.bases_per_line
        byte_offset = row.offset + line_index * row.bytes_per_line + within
        fasta_size = self._fasta_path.stat().st_size
        if byte_offset >= fasta_size:
            raise ReferenceGenomeUnavailableError("reference_position_out_of_range")
        try:
            with self._fasta_path.open("rb") as fh:
                fh.seek(byte_offset)
                raw = fh.read(1)
        except OSError:
            raise ReferenceGenomeUnavailableError("reference_read_failed") from None
        if not raw:
            raise ReferenceGenomeUnavailableError("reference_read_failed")
        base = raw.decode("ascii", errors="replace").upper()
        if base not in ("A", "C", "G", "T"):
            raise ReferenceGenomeUnavailableError("reference_base_not_acgt")
        return base


class _FaiRow:
    __slots__ = ("name", "length", "offset", "bases_per_line", "bytes_per_line")

    def __init__(
        self,
        name: str,
        length: int,
        offset: int,
        bases_per_line: int,
        bytes_per_line: int,
    ) -> None:
        self.name = name
        self.length = length
        self.offset = offset
        self.bases_per_line = bases_per_line
        self.bytes_per_line = bytes_per_line


def _parse_fai(index_path: Path) -> dict[str, _FaiRow]:
    """Parse a standard FASTA index (.fai) file.

    Raises ReferenceGenomeUnavailableError('reference_index_invalid') on
    any structural or semantic violation.
    """
    try:
        text = index_path.read_text(encoding="utf-8")
    except OSError:
        raise ReferenceGenomeUnavailableError("reference_index_invalid") from None
    contigs: dict[str, _FaiRow] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        fields = stripped.split("\t")
        if len(fields) < 5:
            raise ReferenceGenomeUnavailableError("reference_index_invalid")
        name = fields[0]
        try:
            length = int(fields[1])
            offset = int(fields[2])
            bases_per_line = int(fields[3])
            bytes_per_line = int(fields[4])
        except ValueError:
            raise ReferenceGenomeUnavailableError("reference_index_invalid") from None
        if offset < 0:
            raise ReferenceGenomeUnavailableError("reference_index_invalid")
        if length <= 0:
            raise ReferenceGenomeUnavailableError("reference_index_invalid")
        if bases_per_line <= 0:
            raise ReferenceGenomeUnavailableError("reference_index_invalid")
        if bytes_per_line < bases_per_line:
            raise ReferenceGenomeUnavailableError("reference_index_invalid")
        if name in contigs:
            raise ReferenceGenomeUnavailableError("reference_index_invalid")
        contigs[name] = _FaiRow(
            name=name,
            length=length,
            offset=offset,
            bases_per_line=bases_per_line,
            bytes_per_line=bytes_per_line,
        )
    return contigs


# ── projector ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScientificVariantProjector:
    """Composes Stage C authorization with local reference binding.

    Reuses Stage C wholesale — no re-implementation of the B gate,
    require_genetics, or observation SQL.
    """

    authorizer: ScientificObservationAuthorizer
    settings: Settings

    def project(
        self, person_id: str, observation_id: str
    ) -> AuthorizedVariantProjection:
        # 1. authorize via Stage C (B gate, genetics.research, resolution, eligibility)
        obs = self.authorizer.authorize(person_id, observation_id)

        # 2. internal-state defense — must be BEFORE any file access
        if not _is_projection_eligible(obs):
            raise VariantProjectionError("observation_not_projection_eligible")

        # 3. reference not configured
        if self.settings.grch38_reference_fasta is None:
            raise ReferenceGenomeUnavailableError("reference_not_configured")

        # 4. resolve reference base
        assert obs.chromosome in GRCH38_P13_PRIMARY_CONTIGS  # guaranteed by step 2
        contig = GRCH38_P13_PRIMARY_CONTIGS[obs.chromosome]
        resolver = LocalIndexedFastaReferenceResolver(
            self.settings.grch38_reference_fasta
        )
        ref_base = resolver.resolve_reference_base(contig, obs.position)

        # 5. derive ALT from genotype alleles
        normalized = obs.normalized_genotype
        assert normalized is not None  # guaranteed by step 2
        alleles = set(normalized)

        if ref_base in alleles:
            if len(alleles) == 2:
                alt = (alleles - {ref_base}).pop()
            else:
                raise VariantProjectionError("no_alternate_allele_observed")
        else:
            if len(alleles) == 1:
                alt = alleles.pop()
            else:
                raise VariantProjectionError("multiple_alternate_alleles")

        # 6. build canonical SelectedVariantQuery — Foundation owns outbound validation
        query = SelectedVariantQuery(
            genome_build=AtlasGenomeBuild.GRCH38,
            chromosome="chr" + obs.chromosome,
            position=obs.position,
            reference=ref_base,
            alternate=alt,
        )

        # 7. return projection
        return AuthorizedVariantProjection(
            connector_id=obs.connector_id,
            actor_id=obs.actor_id,
            person_id=obs.person_id,
            observation_id=obs.observation_id,
            dataset_id=obs.dataset_id,
            reference_binding=ReferenceAlleleBinding(
                assembly_accession=ASSEMBLY_ACCESSION,
                assembly_name=ASSEMBLY_NAME,
                chromosome=obs.chromosome,
                contig_accession=contig,
                position=obs.position,
                reference=ref_base,
                source_kind=SOURCE_KIND,
            ),
            query=query,
        )


def _is_projection_eligible(obs: AuthorizedGeneticsObservation) -> bool:
    """Checks that the authorized observation is eligible for reference projection.

    Returns False unless:
      - ineligibility_reasons contains 'reference_allele_unresolved' AND no other reason
      - connector_id matches ATLAS_CONNECTOR_DESCRIPTOR
      - genome_build is GRCh38/hg38
      - chromosome is in GRCH38_P13_PRIMARY_CONTIGS
      - coverage_state is 'present'
      - no_call is False
      - orientation_state is 'resolved'
      - normalized_genotype is 2 chars, each in {A,C,G,T}
      - position >= 1
    """
    reasons = obs.ineligibility_reasons
    if len(reasons) != 1 or reasons[0] != "reference_allele_unresolved":
        return False
    if obs.connector_id != ATLAS_CONNECTOR_DESCRIPTOR.connector_id:
        return False
    if obs.genome_build != "GRCh38/hg38":
        return False
    if obs.chromosome not in GRCH38_P13_PRIMARY_CONTIGS:
        return False
    if obs.coverage_state != "present":
        return False
    if obs.no_call is not False:
        return False
    if obs.orientation_state != "resolved":
        return False
    if obs.normalized_genotype is None:
        return False
    if len(obs.normalized_genotype) != 2:
        return False
    if not all(c in "ACGT" for c in obs.normalized_genotype):
        return False
    return not obs.position < 1


__all__ = [
    "ASSEMBLY_ACCESSION",
    "ASSEMBLY_NAME",
    "AuthorizedVariantProjection",
    "GRCH38_P13_PRIMARY_CONTIGS",
    "LocalIndexedFastaReferenceResolver",
    "ReferenceAlleleBinding",
    "ReferenceGenomeConfigurationState",
    "ReferenceGenomeUnavailableError",
    "ScientificVariantProjector",
    "SOURCE_KIND",
    "VariantProjectionError",
    "reference_genome_configuration_state_from_settings",
]