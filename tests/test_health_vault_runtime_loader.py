import json
from pathlib import Path

import pytest

from app.config import Settings
from app.health_vault.runtime_loader import load_active_vault
from tests.test_health_vault import valid_family_vault, write_vault


def local_file_payload() -> dict[str, object]:
    payload = valid_family_vault()
    payload["demo_only"] = False
    payload["synthetic"] = False

    family = payload["family"]
    assert isinstance(family, dict)
    family["synthetic"] = False
    family["display_name"] = "Local Family Vault"

    people = payload["people"]
    assert isinstance(people, list)
    for person in people:
        assert isinstance(person, dict)
        person["synthetic"] = False

    sources = payload["document_sources"]
    assert isinstance(sources, list)
    for source in sources:
        assert isinstance(source, dict)
        source["synthetic"] = False
        source["demo_only"] = False

    conditions = payload["conditions"]
    assert isinstance(conditions, list)
    for condition in conditions:
        assert isinstance(condition, dict)
        condition["description"] = "Recorded local context only; clinician review required."

    questions = payload["question_threads"]
    assert isinstance(questions, list)
    for question in questions:
        assert isinstance(question, dict)
        question["question"] = "Which recorded items should the family review next?"

    return payload


def development_settings() -> Settings:
    return Settings(
        env="development",
        demo_mode=True,
        data_dir=Path("data"),
        reports_dir=Path("reports"),
        allow_cloud_llm=False,
        secret_key=None,
        access_password=None,
    )


def test_load_active_vault_uses_demo_source_by_default() -> None:
    active_vault = load_active_vault(development_settings())

    assert active_vault.source_kind == "demo"
    assert active_vault.source_label == "demo"
    assert active_vault.source_basename is None
    assert active_vault.dataset.demo_only is True
    assert active_vault.read_model.family.demo_only is True


def test_load_active_vault_uses_local_file_source(tmp_path: Path) -> None:
    vault_path = write_vault(tmp_path, local_file_payload())

    active_vault = load_active_vault(
        Settings(
            env="development",
            demo_mode=True,
            data_dir=Path("data"),
            reports_dir=Path("reports"),
            allow_cloud_llm=False,
            secret_key=None,
            access_password=None,
            vault_source="local_file",
            vault_file=vault_path,
        )
    )

    assert active_vault.source_kind == "local_file"
    assert active_vault.source_label == "local file"
    assert active_vault.source_basename == vault_path.name
    assert active_vault.dataset.demo_only is False
    assert active_vault.dataset.synthetic is False
    assert active_vault.read_model.family.display_name == "Local Family Vault"


def test_load_active_vault_fails_closed_on_invalid_json(tmp_path: Path) -> None:
    vault_path = tmp_path / "invalid-vault.json"
    vault_path.write_text("{not-json}", encoding="utf-8")

    with pytest.raises(ValueError):
        load_active_vault(
            Settings(
                env="development",
                demo_mode=True,
                data_dir=Path("data"),
                reports_dir=Path("reports"),
                allow_cloud_llm=False,
                secret_key=None,
                access_password=None,
                vault_source="local_file",
                vault_file=vault_path,
            )
        )


def test_load_active_vault_fails_closed_on_invalid_schema(tmp_path: Path) -> None:
    vault_path = tmp_path / "invalid-schema-vault.json"
    vault_path.write_text(json.dumps({"dataset_id": "missing-fields"}), encoding="utf-8")

    with pytest.raises(ValueError):
        load_active_vault(
            Settings(
                env="development",
                demo_mode=True,
                data_dir=Path("data"),
                reports_dir=Path("reports"),
                allow_cloud_llm=False,
                secret_key=None,
                access_password=None,
                vault_source="local_file",
                vault_file=vault_path,
            )
        )
