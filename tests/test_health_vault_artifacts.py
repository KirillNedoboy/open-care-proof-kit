import json
from pathlib import Path

import pytest

from app.demo_pipeline import build_demo_briefing
from app.health_vault.artifacts import (
    build_vault_artifacts,
)
from app.health_vault.loader import load_demo_family_vault


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_artifact_builder_writes_expected_files(tmp_path: Path) -> None:
    result = build_vault_artifacts(load_demo_family_vault(), tmp_path)

    assert [artifact.filename for artifact in result.files] == [
        "family-vault-read-model.json",
        "family-vault-summary.md",
        "family-vault-manifest.json",
    ]
    assert (tmp_path / "family-vault-read-model.json").is_file()
    assert (tmp_path / "family-vault-summary.md").is_file()
    assert (tmp_path / "family-vault-manifest.json").is_file()


def test_json_artifact_contains_demo_synthetic_provenance_and_safety(
    tmp_path: Path,
) -> None:
    build_vault_artifacts(load_demo_family_vault(), tmp_path)

    artifact = read_json(tmp_path / "family-vault-read-model.json")

    assert artifact["artifact_type"] == "health_family_vault_read_model"
    assert artifact["demo_only"] is True
    assert artifact["synthetic"] is True
    assert artifact["family"]["id"] == "family-demo-01"
    assert artifact["people"]
    assert artifact["relationships"]
    assert artifact["medications_by_person"]
    assert artifact["conditions_by_person"]
    assert artifact["labs_by_person"]
    assert artifact["visits_by_person"]
    assert artifact["timeline"]
    assert artifact["question_threads"]
    assert artifact["provenance_coverage"] == {
        "total_important_records": 14,
        "records_with_source": 14,
        "records_missing_source": 0,
        "missing_source_item_ids": [],
    }
    assert artifact["safety_boundary_notices"]
    assert artifact["generated_from"] == {
        "dataset_id": "demo-family-vault-v1a",
        "dataset_version": "0.1.0",
        "source_dataset": "validated VaultDataset",
        "deterministic_builder": "health_vault_artifact_builder",
        "deterministic_builder_version": "0.1.0",
    }


def test_markdown_artifact_contains_required_sections_and_boundaries(
    tmp_path: Path,
) -> None:
    build_vault_artifacts(load_demo_family_vault(), tmp_path)

    markdown = (tmp_path / "family-vault-summary.md").read_text(encoding="utf-8")

    for section in [
        "# Health/Family Vault Summary",
        "## Safety Boundary",
        "## Family Overview",
        "## People",
        "## Relationships",
        "## Recorded Medications",
        "## Recorded Conditions / Concerns",
        "## Recorded Labs",
        "## Visits / Encounters",
        "## Timeline",
        "## Question Workspace",
        "## Provenance Coverage",
        "## What This Artifact Does Not Do",
    ]:
        assert section in markdown

    assert "synthetic/demo-only" in markdown
    assert "deterministic summary of recorded context" in markdown
    assert "not diagnosis" in markdown
    assert "not treatment recommendation" in markdown
    assert "not dosage guidance" in markdown
    assert "not medication selection" in markdown
    assert "not start/stop medication advice" in markdown
    assert "no genetics in V1C" in markdown


def test_manifest_contains_safety_and_scope_flags(tmp_path: Path) -> None:
    build_vault_artifacts(load_demo_family_vault(), tmp_path)

    manifest = read_json(tmp_path / "family-vault-manifest.json")

    assert manifest["artifact_version"] == "0.1.0"
    assert manifest["demo_only"] is True
    assert manifest["synthetic"] is True
    assert manifest["builder_name"] == "health_vault_artifact_builder"
    assert manifest["builder_version"] == "0.1.0"
    assert manifest["no_llm_generation"] is True
    assert manifest["no_genetics"] is True
    assert manifest["no_medical_advice"] is True
    assert manifest["safety_boundary_notice_count"] >= 1
    assert manifest["provenance_coverage_summary"] == {
        "total_important_records": 14,
        "records_with_source": 14,
        "records_missing_source": 0,
        "missing_source_item_ids": [],
    }
    assert manifest["created_artifacts"] == [
        {
            "filename": "family-vault-read-model.json",
            "artifact_type": "health_family_vault_read_model",
        },
        {
            "filename": "family-vault-summary.md",
            "artifact_type": "health_family_vault_markdown_summary",
        },
        {
            "filename": "family-vault-manifest.json",
            "artifact_type": "health_family_vault_manifest",
        },
    ]


def test_incomplete_provenance_causes_artifact_failure(tmp_path: Path) -> None:
    dataset = load_demo_family_vault()
    lab_without_source = dataset.lab_results[0].model_copy(update={"evidence": []})
    invalid_dataset = dataset.model_copy(
        update={"lab_results": [lab_without_source, *dataset.lab_results[1:]]}
    )

    with pytest.raises(ValueError, match="provenance"):
        build_vault_artifacts(invalid_dataset, tmp_path)


def test_unsafe_surfaced_text_causes_artifact_failure(tmp_path: Path) -> None:
    dataset = load_demo_family_vault()
    unsafe_condition = dataset.conditions[0].model_copy(
        update={"description": "OpenCare diagnosis: insomnia."}
    )
    invalid_dataset = dataset.model_copy(
        update={"conditions": [unsafe_condition, *dataset.conditions[1:]]}
    )

    with pytest.raises(ValueError, match="unsafe"):
        build_vault_artifacts(invalid_dataset, tmp_path)


def test_existing_pgx_briefing_still_passes_unchanged() -> None:
    result = build_demo_briefing("sertraline")

    assert result.policy_passed is True
    assert result.findings_count == 1
    assert result.coverage["coverage_status"] == "matched_demo_rule"
