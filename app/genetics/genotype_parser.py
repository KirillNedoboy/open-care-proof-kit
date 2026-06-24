from pathlib import Path

from app.genetics.normalizer import NormalizedVariant

VALID_CHROMOSOMES = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
VALID_23ANDME_GENOTYPE_ALLELES = frozenset("ACGTDI")


def parse_positive_position(position_raw: str, *, line_number: int) -> int:
    try:
        position = int(position_raw)
    except ValueError as exc:
        raise ValueError(f"Invalid position at line {line_number}: {position_raw}") from exc

    if position <= 0:
        raise ValueError(f"Invalid position at line {line_number}: {position_raw}")

    return position


def normalize_23andme_genotype(genotype_raw: str, *, line_number: int) -> str:
    genotype = genotype_raw.upper()
    if genotype == "--":
        return genotype

    if not 1 <= len(genotype) <= 2:
        raise ValueError(f"Invalid genotype at line {line_number}: {genotype_raw}")

    if any(allele not in VALID_23ANDME_GENOTYPE_ALLELES for allele in genotype):
        raise ValueError(f"Invalid genotype at line {line_number}: {genotype_raw}")

    return genotype


def parse_23andme_file(path: Path, *, genome_build: str | None = None) -> list[NormalizedVariant]:
    variants: list[NormalizedVariant] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        if len(parts) != 4:
            raise ValueError(f"Invalid 23andMe row at line {line_number}: expected 4 columns.")

        rsid, chromosome, position_raw, genotype = parts
        chromosome = chromosome.upper()

        if chromosome not in VALID_CHROMOSOMES:
            raise ValueError(f"Invalid chromosome at line {line_number}: {chromosome}")

        position = parse_positive_position(position_raw, line_number=line_number)
        genotype = normalize_23andme_genotype(genotype, line_number=line_number)

        variants.append(
            NormalizedVariant(
                rsid=rsid,
                chromosome=chromosome,
                position=position,
                genotype=genotype,
                source="23andme_demo",
                genome_build=genome_build,
                no_call=genotype == "--",
            )
        )

    return variants
