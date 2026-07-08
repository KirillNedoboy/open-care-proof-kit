from dataclasses import dataclass

from app.config import Settings
from app.health_vault.loader import load_demo_family_vault, load_family_vault
from app.health_vault.models import VaultDataset
from app.health_vault.read_model import VaultReadModel, build_vault_read_model


@dataclass(frozen=True)
class ActiveVault:
    dataset: VaultDataset
    read_model: VaultReadModel
    source_kind: str
    source_label: str
    source_basename: str | None


def load_active_vault(settings: Settings) -> ActiveVault:
    if settings.vault_source == "demo":
        dataset = load_demo_family_vault()
        return ActiveVault(
            dataset=dataset,
            read_model=build_vault_read_model(dataset),
            source_kind="demo",
            source_label="demo",
            source_basename=None,
        )

    if settings.vault_file is None:
        raise ValueError("OPENCARE_VAULT_FILE is required for local_file source.")

    dataset = load_family_vault(
        settings.vault_file,
        require_demo_constraints=False,
    )
    return ActiveVault(
        dataset=dataset,
        read_model=build_vault_read_model(dataset),
        source_kind="local_file",
        source_label="local file",
        source_basename=settings.vault_file.name,
    )
