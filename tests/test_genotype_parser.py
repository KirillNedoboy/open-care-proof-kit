from pathlib import Path

import pytest

from app.genetics.genotype_parser import parse_23andme_file
from app.genetics.vcf_parser import parse_demo_vcf


def test_parse_demo_23andme_file() -> None:
    variants = parse_23andme_file(Path("data/demo_patients/demo_patient_a_23andme.txt"))
    assert len(variants) == 3
    assert variants[0].rsid == "rs4244285"
    assert variants[0].genotype == "AG"
    assert not variants[0].no_call


def test_parse_23andme_file_rejects_invalid_genotype(tmp_path: Path) -> None:
    genotype_path = tmp_path / "invalid_23andme.txt"
    genotype_path.write_text("rs1\t1\t12345\tAGT\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid genotype at line 1"):
        parse_23andme_file(genotype_path)


def test_parse_23andme_file_rejects_non_positive_position(tmp_path: Path) -> None:
    genotype_path = tmp_path / "invalid_position.txt"
    genotype_path.write_text("rs1\t1\t0\tAG\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid position at line 1"):
        parse_23andme_file(genotype_path)


def test_parse_demo_vcf_rejects_invalid_chromosome(tmp_path: Path) -> None:
    vcf_path = tmp_path / "invalid.vcf"
    vcf_path.write_text("chrUn\t12345\trs1\tA\tG\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid VCF chromosome at line 1"):
        parse_demo_vcf(vcf_path)
