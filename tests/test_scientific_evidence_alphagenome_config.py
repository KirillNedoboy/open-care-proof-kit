"""Offline, network-forbidden tests for the AlphaGenome operator configuration stage B.

Tests that operator-controlled runtime configuration (enabled/disabled,
API key presence, derived status) works correctly without any network,
SDK, persistence, or Product Core dependency. "Configured" means only
that runtime configuration is sufficient for FUTURE transport; it never
implies API reachability, key validity, or live verification.
"""

from __future__ import annotations

import ast
import json
import socket
import sys
from typing import Any

import pytest
from pydantic import SecretStr
from pydantic import ValidationError as PydanticValidationError

from app.config import ConfigError, load_settings
from app.scientific_evidence.alphagenome_atlas import ATLAS_CONNECTOR_DESCRIPTOR
from app.scientific_evidence.contracts import CommercialUseClass
from app.scientific_evidence.operator_config import (
    AlphaGenomeConfigurationState,
    AlphaGenomeOperatorConfig,
    AlphaGenomeRuntimeStatus,
    alphagenome_runtime_status_from_settings,
    build_alphagenome_operator_config,
    derive_alphagenome_runtime_status,
)

SENTINEL = "alpha-secret-SENTINEL-do-not-leak"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Socket guard: any network use in this suite is a hard failure."""

    def _blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network access is forbidden in these tests")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


# ---------------------------------------------------------------------------
# 1–6: config loading + derived status
# ---------------------------------------------------------------------------


def test_default_settings_disabled_no_key() -> None:
    settings = load_settings({})

    assert settings.alphagenome_enabled is False
    assert settings.alphagenome_api_key is None

    status = alphagenome_runtime_status_from_settings(settings)
    assert status.enabled is False
    assert status.api_key_configured is False
    assert status.configuration_state == AlphaGenomeConfigurationState.DISABLED


def test_disabled_with_key_present_stays_disabled() -> None:
    settings = load_settings({
        "OPENCARE_ALPHAGENOME_ENABLED": "false",
        "ALPHAGENOME_API_KEY": SENTINEL,
    })

    assert settings.alphagenome_enabled is False
    assert settings.alphagenome_api_key == SENTINEL

    status = alphagenome_runtime_status_from_settings(settings)
    assert status.configuration_state == AlphaGenomeConfigurationState.DISABLED
    # key IS present, so api_key_configured truthfully reflects that
    assert status.api_key_configured is True


def test_enabled_missing_key() -> None:
    settings = load_settings({"OPENCARE_ALPHAGENOME_ENABLED": "true"})

    assert settings.alphagenome_enabled is True
    assert settings.alphagenome_api_key is None

    status = alphagenome_runtime_status_from_settings(settings)
    assert status.configuration_state == AlphaGenomeConfigurationState.MISSING_API_KEY
    assert status.api_key_configured is False


@pytest.mark.parametrize("key_value", ["", "   ", "\t "])
def test_enabled_blank_whitespace_key_is_missing(key_value: str) -> None:
    settings = load_settings({
        "OPENCARE_ALPHAGENOME_ENABLED": "true",
        "ALPHAGENOME_API_KEY": key_value,
    })

    assert settings.alphagenome_api_key is None  # _read_optional_secret collapses

    status = alphagenome_runtime_status_from_settings(settings)
    assert status.configuration_state == AlphaGenomeConfigurationState.MISSING_API_KEY
    assert status.api_key_configured is False


def test_enabled_with_key_configured() -> None:
    settings = load_settings({
        "OPENCARE_ALPHAGENOME_ENABLED": "true",
        "ALPHAGENOME_API_KEY": SENTINEL,
    })

    assert settings.alphagenome_enabled is True
    assert settings.alphagenome_api_key == SENTINEL

    config = build_alphagenome_operator_config(settings)
    assert config.enabled is True
    assert config.api_key is not None
    assert config.api_key.get_secret_value() == SENTINEL

    status = derive_alphagenome_runtime_status(config)
    assert status.configuration_state == AlphaGenomeConfigurationState.CONFIGURED
    assert status.api_key_configured is True


@pytest.mark.parametrize("malformed", ["1", "yes", "ture"])
def test_malformed_enabled_raises_configerror(malformed: str) -> None:
    env: dict[str, str] = {"OPENCARE_ALPHAGENOME_ENABLED": malformed}
    # even when a sentinel key is also present, the error message must
    # name the env var, not the sentinel value
    env["ALPHAGENOME_API_KEY"] = SENTINEL
    try:
        load_settings(env)
    except ConfigError as exc:
        msg = str(exc)
        assert "OPENCARE_ALPHAGENOME_ENABLED" in msg
        assert SENTINEL not in msg
    else:
        pytest.fail(f"expected ConfigError for malformed value {malformed!r}")


# ---------------------------------------------------------------------------
# 7: live_verified always False
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "enabled,key,expected_state",
    [
        (False, None, AlphaGenomeConfigurationState.DISABLED),
        (True, None, AlphaGenomeConfigurationState.MISSING_API_KEY),
        (True, SENTINEL, AlphaGenomeConfigurationState.CONFIGURED),
    ],
)
def test_live_verified_always_false(
    enabled: bool, key: str | None, expected_state: AlphaGenomeConfigurationState
) -> None:
    env: dict[str, str] = {"OPENCARE_ALPHAGENOME_ENABLED": str(enabled).lower()}
    if key is not None:
        env["ALPHAGENOME_API_KEY"] = key

    settings = load_settings(env)
    status = alphagenome_runtime_status_from_settings(settings)

    assert status.configuration_state == expected_state
    assert status.live_verified is False
    assert status.live_verified == False  # noqa: E712  (explicit Literal check)


# ---------------------------------------------------------------------------
# 8: static descriptor truth derived from ATLAS_CONNECTOR_DESCRIPTOR
# ---------------------------------------------------------------------------


def test_static_descriptor_truth_derived_from_atlas() -> None:
    settings = load_settings({
        "OPENCARE_ALPHAGENOME_ENABLED": "true",
        "ALPHAGENOME_API_KEY": SENTINEL,
    })
    status = alphagenome_runtime_status_from_settings(settings)

    assert status.connector_id == ATLAS_CONNECTOR_DESCRIPTOR.connector_id
    assert status.connector_id == "opencare.alphagenome_atlas"
    assert status.source_name == ATLAS_CONNECTOR_DESCRIPTOR.source_name
    assert status.external is True
    assert status.research_only is True
    assert status.clinical_use_allowed is False
    assert status.commercial_use_class == CommercialUseClass.PARTIAL_AVI_SCORE_ONLY


# ---------------------------------------------------------------------------
# 9: status never leaks a raw api_key field
# ---------------------------------------------------------------------------


def test_status_never_exposes_raw_api_key_field() -> None:
    fields = AlphaGenomeRuntimeStatus.model_fields
    assert "api_key" not in fields
    assert "api_key_configured" in fields


# ---------------------------------------------------------------------------
# 10: sentinel absent from all serialization surfaces
# ---------------------------------------------------------------------------


def test_sentinel_absent_from_all_surfaces() -> None:
    settings = load_settings({
        "OPENCARE_ALPHAGENOME_ENABLED": "true",
        "ALPHAGENOME_API_KEY": SENTINEL,
    })
    config = build_alphagenome_operator_config(settings)
    status = derive_alphagenome_runtime_status(config)

    # repr
    for obj in (config, status):
        assert SENTINEL not in repr(obj)

    # status model_dump (dict) + json
    status_dump = status.model_dump()
    assert SENTINEL not in json.dumps(status_dump)
    assert SENTINEL not in status.model_dump_json()

    # config model_dump_json
    assert SENTINEL not in config.model_dump_json()


# ---------------------------------------------------------------------------
# 11: operator config frozen; blank key rejected at construction
# ---------------------------------------------------------------------------


def test_operator_config_is_frozen() -> None:
    config = AlphaGenomeOperatorConfig(enabled=True, api_key=SecretStr(SENTINEL))

    with pytest.raises(PydanticValidationError):
        config.enabled = False  # type: ignore[misc]


def test_direct_construction_rejects_blank_api_key() -> None:
    with pytest.raises(ValueError, match="api_key_blank"):
        AlphaGenomeOperatorConfig(enabled=True, api_key=SecretStr("   "))


# ---------------------------------------------------------------------------
# 12: configuration_state enum values
# ---------------------------------------------------------------------------


def test_configuration_state_values() -> None:
    values = {s.value for s in AlphaGenomeConfigurationState}
    assert values == {"disabled", "missing_api_key", "configured"}

    # should be StrEnum (string-backed)
    assert isinstance(AlphaGenomeConfigurationState.DISABLED, str)


# ---------------------------------------------------------------------------
# 13: no SDK/runtime modules leak
# ---------------------------------------------------------------------------


def test_no_sdk_modules_leak_into_sys_modules() -> None:
    # Exercise the full pipeline to ensure nothing smuggles in external deps.
    settings = load_settings({
        "OPENCARE_ALPHAGENOME_ENABLED": "true",
        "ALPHAGENOME_API_KEY": SENTINEL,
    })
    alphagenome_runtime_status_from_settings(settings)

    forbidden = frozenset({"alphagenome", "grpc", "anndata", "alphagenome_atlas"})
    leaked = set(sys.modules) & forbidden
    assert not leaked, f"external modules leaked: {leaked}"


# ---------------------------------------------------------------------------
# 14: AST import boundary — operator_config.py never imports forbidden layers
# ---------------------------------------------------------------------------


def test_operator_config_never_imports_forbidden_layers() -> None:
    from pathlib import Path

    import app.scientific_evidence.operator_config as _oc_mod

    source_path = Path(_oc_mod.__file__).resolve()
    source = source_path.read_text(encoding="utf-8")

    tree = ast.parse(source, filename="operator_config.py")
    allowed = frozenset({
        "app.config",
        "app.config.Settings",
        "app.scientific_evidence.alphagenome_atlas",
        "app.scientific_evidence.contracts",
        "app.scientific_evidence.contracts.CommercialUseClass",
        "app.scientific_evidence.contracts.FrozenModel",
        "app.scientific_evidence.operator_config",
        "__future__",
        "enum",
        "typing",
        "pydantic",
    })

    for node in ast.walk(tree):
        modules: list[str] = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        for module in modules:
            # skip relative
            if module.startswith("."):
                continue
            assert module in allowed, (
                f"operator_config.py imports forbidden module {module}"
            )


# ---------------------------------------------------------------------------
# 15: socket guard proof
# ---------------------------------------------------------------------------


def test_socket_guard_active() -> None:
    with pytest.raises(AssertionError, match="network access is forbidden"):
        socket.socket()


# ---------------------------------------------------------------------------
# 16: build preserves exact key recoverable via get_secret_value
# ---------------------------------------------------------------------------


def test_build_preserves_exact_key() -> None:
    settings = load_settings({
        "OPENCARE_ALPHAGENOME_ENABLED": "true",
        "ALPHAGENOME_API_KEY": SENTINEL,
    })
    config = build_alphagenome_operator_config(settings)
    assert config.api_key is not None
    assert config.api_key.get_secret_value() == SENTINEL