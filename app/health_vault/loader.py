import json
from pathlib import Path

from app.config import get_settings
from app.health_vault.models import VaultDataset, validate_demo_dataset


def load_family_vault(path: Path, *, require_demo_constraints: bool = True) -> VaultDataset:
    raw = json.loads(path.read_text(encoding="utf-8"))
    dataset = VaultDataset.model_validate(raw)
    if require_demo_constraints:
        return validate_demo_dataset(dataset)
    return dataset


def load_demo_family_vault() -> VaultDataset:
    settings = get_settings()
    return load_family_vault(settings.data_dir / "demo_patients" / "demo_family_vault.json")
