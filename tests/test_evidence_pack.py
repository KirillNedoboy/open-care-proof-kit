import json
from pathlib import Path

import pytest

from app.evidence.loader import load_evidence_pack


def write_pack(tmp_path: Path, rule_overrides: dict[str, object]) -> Path:
    rule = {
        "rule_id": "demo-rule",
        "drug": "sertraline",
        "gene": "CYP2C19",
        "variant_rsid": "rs4244285",
        "matching_genotypes": ["AG"],
        "source_name": "CPIC demo source",
        "source_url": "https://cpicpgx.org/guidelines/",
        "evidence_level": "demo",
        "clinical_action_allowed": False,
        "clinician_review_required": True,
        "summary": "Demo summary.",
        "limitations": "Demo limitations.",
    }
    rule.update(rule_overrides)
    pack = {
        "pack_id": "demo-pack",
        "version": "0.1.0",
        "description": "Demo pack",
        "demo_only": True,
        "rules": [rule],
    }
    pack_path = tmp_path / "pack.json"
    pack_path.write_text(json.dumps(pack), encoding="utf-8")
    return pack_path


def test_load_evidence_pack_rejects_non_https_source_url(tmp_path: Path) -> None:
    pack_path = write_pack(tmp_path, {"source_url": "http://cpicpgx.org/guidelines/"})

    with pytest.raises(ValueError, match="https"):
        load_evidence_pack(pack_path)


def test_load_evidence_pack_rejects_invalid_source_domain(tmp_path: Path) -> None:
    pack_path = write_pack(tmp_path, {"source_url": "https://example.com/source"})

    with pytest.raises(ValueError, match="allowed source domain"):
        load_evidence_pack(pack_path)


def test_load_evidence_pack_rejects_clinical_action_allowed_rule(tmp_path: Path) -> None:
    pack_path = write_pack(tmp_path, {"clinical_action_allowed": True})

    with pytest.raises(ValueError, match="clinical_action_allowed"):
        load_evidence_pack(pack_path)


def test_load_evidence_pack_rejects_missing_limitations(tmp_path: Path) -> None:
    pack_path = write_pack(tmp_path, {"limitations": ""})

    with pytest.raises(ValueError, match="limitations"):
        load_evidence_pack(pack_path)
