"""Operator configuration seam for AlphaGenome stage B.

No network, no SDK, no persistence, no Person authorization.
"Configured" means only that runtime configuration is sufficient for
FUTURE transport construction (stage E).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import SecretStr, field_validator

from app.config import Settings
from app.scientific_evidence.alphagenome_atlas import ATLAS_CONNECTOR_DESCRIPTOR
from app.scientific_evidence.contracts import CommercialUseClass, FrozenModel


class AlphaGenomeConfigurationState(StrEnum):
    DISABLED = "disabled"
    MISSING_API_KEY = "missing_api_key"
    CONFIGURED = "configured"


class AlphaGenomeOperatorConfig(FrozenModel):
    enabled: bool = False
    api_key: SecretStr | None = None

    @field_validator("api_key")
    @classmethod
    def _reject_blank_api_key(cls, v: SecretStr | None) -> SecretStr | None:
        if v is not None and not v.get_secret_value().strip():
            raise ValueError("api_key_blank")
        return v


def build_alphagenome_operator_config(
    settings: Settings,
) -> AlphaGenomeOperatorConfig:
    key: SecretStr | None = None
    if settings.alphagenome_api_key is not None:
        key = SecretStr(settings.alphagenome_api_key)
    return AlphaGenomeOperatorConfig(
        enabled=settings.alphagenome_enabled,
        api_key=key,
    )


class AlphaGenomeRuntimeStatus(FrozenModel):
    connector_id: str
    source_name: str
    enabled: bool
    external: Literal[True]
    research_only: Literal[True]
    clinical_use_allowed: Literal[False]
    commercial_use_class: CommercialUseClass
    api_key_configured: bool
    configuration_state: AlphaGenomeConfigurationState
    live_verified: Literal[False] = False


def derive_alphagenome_runtime_status(
    config: AlphaGenomeOperatorConfig,
) -> AlphaGenomeRuntimeStatus:
    api_key_configured = config.api_key is not None
    if not config.enabled:
        state = AlphaGenomeConfigurationState.DISABLED
    elif config.api_key is None:
        state = AlphaGenomeConfigurationState.MISSING_API_KEY
    else:
        state = AlphaGenomeConfigurationState.CONFIGURED

    return AlphaGenomeRuntimeStatus(
        connector_id=ATLAS_CONNECTOR_DESCRIPTOR.connector_id,
        source_name=ATLAS_CONNECTOR_DESCRIPTOR.source_name,
        enabled=config.enabled,
        external=True,
        research_only=True,
        clinical_use_allowed=False,
        commercial_use_class=ATLAS_CONNECTOR_DESCRIPTOR.commercial_use_class,
        api_key_configured=api_key_configured,
        configuration_state=state,
        live_verified=False,
    )


def alphagenome_runtime_status_from_settings(
    settings: Settings,
) -> AlphaGenomeRuntimeStatus:
    config = build_alphagenome_operator_config(settings)
    return derive_alphagenome_runtime_status(config)