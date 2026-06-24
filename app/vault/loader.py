import json
from pathlib import Path

from app.vault.schema import HealthVault


def load_health_vault(path: Path) -> HealthVault:
    raw = json.loads(path.read_text(encoding="utf-8"))
    vault = HealthVault.model_validate(raw)
    vault.assert_demo_only()
    return vault
