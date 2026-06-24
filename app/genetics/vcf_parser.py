from pathlib import Path

from app.genetics.normalizer import NormalizedVariant

VALID_DEMO_VCF_CHROMOSOMES = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}


def parse_demo_vcf(path: Path, *, genome_build: str | None = None) -> list[NormalizedVariant]:
    variants: list[NormalizedVariant] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("##"):
            continue
        if line.startswith("#CHROM"):
            continue

        parts = line.split("\t")
        if len(parts) < 5:
            raise ValueError(f"Invalid VCF row at line {line_number}: expected at least 5 columns.")

        chromosome_raw, position_raw, variant_id, ref, alt = parts[:5]
        chromosome = chromosome_raw.upper().removeprefix("CHR")
        if chromosome not in VALID_DEMO_VCF_CHROMOSOMES:
            raise ValueError(f"Invalid VCF chromosome at line {line_number}: {chromosome_raw}")

        try:
            position = int(position_raw)
        except ValueError as exc:
            raise ValueError(f"Invalid VCF position at line {line_number}: {position_raw}") from exc

        if position <= 0:
            raise ValueError(f"Invalid VCF position at line {line_number}: {position_raw}")

        genotype = f"{ref}>{alt}"

        variants.append(
            NormalizedVariant(
                rsid=None if variant_id == "." else variant_id,
                chromosome=chromosome,
                position=position,
                genotype=genotype,
                source="vcf_demo",
                genome_build=genome_build,
                no_call=False,
            )
        )

    return variants
