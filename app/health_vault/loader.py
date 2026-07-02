import json
from pathlib import Path

from app.config import get_settings
from app.health_vault.models import VaultDataset


def load_family_vault(path: Path) -> VaultDataset:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return VaultDataset.model_validate(raw)


def load_demo_family_vault() -> VaultDataset:
    settings = get_settings()
    return load_family_vault(settings.data_dir / "demo_patients" / "demo_family_vault.json")
