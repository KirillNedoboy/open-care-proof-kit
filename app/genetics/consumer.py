"""Bounded parsing and selective normalization of consumer genotype text."""

from __future__ import annotations

from hashlib import sha256
from typing import Collection, Mapping

from app.genetics.models import (
    ConsumerGenotypeImport,
    GenomeBuild,
    GenotypeObservation,
    OrientationState,
)

MAX_CONSUMER_GENOTYPE_BYTES = 32 * 1024 * 1024
_VALID_CHROMOSOMES = frozenset({str(number) for number in range(1, 23)} | {"X", "Y", "MT"})
_NO_CALLS = frozenset({"", "--", "00", "NC", "NO_CALL", "NOCALL"})


def normalize_genome_build(value: GenomeBuild | str | None) -> GenomeBuild:
    """Normalize supported build aliases without performing liftover."""

    if isinstance(value, GenomeBuild):
        return value
    normalized = (value or "unknown").strip().lower()
    aliases = {
        "grch37": GenomeBuild.GRCH37,
        "hg19": GenomeBuild.GRCH37,
        "grch38": GenomeBuild.GRCH38,
        "hg38": GenomeBuild.GRCH38,
        "unknown": GenomeBuild.UNKNOWN,
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported genome build: {value}") from exc


def parse_consumer_genotypes(
    content: bytes,
    *,
    genome_build: GenomeBuild | str | None,
    selected_rsids: Collection[str] = (),
    selected_loci: Collection[tuple[str, int]] = (),
    orientation_by_rsid: Mapping[str, OrientationState] | None = None,
    max_bytes: int = MAX_CONSUMER_GENOTYPE_BYTES,
) -> ConsumerGenotypeImport:
    """Parse bounded 23andMe-style bytes and retain only explicitly selected targets.

    The return value contains normalized observations and counts, never the input bytes.
    Empty, ``--``, ``00``, ``NC``, and ``NO_CALL`` are treated as no-calls.
    """

    if len(content) > max_bytes:
        raise ValueError(f"consumer genotype input exceeds {max_bytes} bytes")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("consumer genotype input must be UTF-8 text") from exc

    build = normalize_genome_build(genome_build)
    rsid_targets = frozenset(selected_rsids)
    locus_targets = frozenset((chromosome.upper().removeprefix("CHR"), position) for chromosome, position in selected_loci)
    orientations = orientation_by_rsid or {}
    parsed_count = 0
    observations: list[GenotypeObservation] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\r\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        columns = line.split("\t")
        if len(columns) != 4:
            columns = line.split()
        if len(columns) != 4:
            raise ValueError(f"invalid consumer genotype row at line {line_number}: expected 4 columns")

        rsid, chromosome_raw, position_raw, reported_raw = (column.strip() for column in columns)
        if not rsid:
            raise ValueError(f"missing rsID at line {line_number}")
        chromosome = chromosome_raw.upper().removeprefix("CHR")
        if chromosome == "M":
            chromosome = "MT"
        if chromosome not in _VALID_CHROMOSOMES:
            raise ValueError(f"invalid chromosome at line {line_number}: {chromosome_raw}")
        try:
            position = int(position_raw)
        except ValueError as exc:
            raise ValueError(f"invalid position at line {line_number}: {position_raw}") from exc
        if position <= 0:
            raise ValueError(f"invalid position at line {line_number}: {position_raw}")

        reported = reported_raw.upper()
        no_call = reported in _NO_CALLS
        if no_call:
            normalized = None
        else:
            if len(reported) != 2 or any(allele not in "ACGT" for allele in reported):
                raise ValueError(f"invalid diploid genotype at line {line_number}: {reported_raw}")
            normalized = "".join(sorted(reported))
        parsed_count += 1

        if rsid not in rsid_targets and (chromosome, position) not in locus_targets:
            continue
        inferred_orientation = (
            OrientationState.NOT_APPLICABLE
            if no_call
            else OrientationState.AMBIGUOUS
            if normalized in {"AT", "CG"}
            else OrientationState.RESOLVED
        )
        orientation = orientations.get(rsid, inferred_orientation)
        identity = f"{rsid}|{chromosome}|{position}|{build.value}|{normalized or 'NO_CALL'}"
        observations.append(
            GenotypeObservation(
                observation_id=f"obs-{sha256(identity.encode('utf-8')).hexdigest()[:20]}",
                rsid=rsid,
                chromosome=chromosome,
                position=position,
                reported_genotype=reported,
                normalized_genotype=normalized,
                no_call=no_call,
                genome_build=build,
                orientation=orientation,
                source_locator=f"line:{line_number}",
            )
        )

    return ConsumerGenotypeImport(
        genome_build=build,
        parsed_locus_count=parsed_count,
        observations=tuple(observations),
    )
