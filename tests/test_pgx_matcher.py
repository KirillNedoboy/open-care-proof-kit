from pathlib import Path

from app.evidence.loader import load_evidence_pack
from app.genetics.genotype_parser import parse_23andme_file
from app.pgx.matcher import match_pgx_rules


def test_match_sertraline_demo_rule() -> None:
    variants = parse_23andme_file(Path("data/demo_patients/demo_patient_a_23andme.txt"))
    pack = load_evidence_pack(Path("data/evidence_packs/pgx_demo_pack.json"))
    findings = match_pgx_rules(drug="sertraline", variants=variants, evidence_pack=pack)
    assert len(findings) == 1
    assert findings[0].gene == "CYP2C19"
    assert not findings[0].clinical_action_allowed
