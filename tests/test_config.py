from pathlib import Path

import pytest

from app.config import ConfigError, load_settings


def test_load_settings_defaults_to_easy_development_mode() -> None:
    settings = load_settings({})

    assert settings.env == "development"
    assert settings.demo_mode is True
    assert settings.data_dir == Path("data")
    assert settings.reports_dir == Path("reports")
    assert settings.allow_cloud_llm is False
    assert settings.secret_key is None
    assert settings.access_password is None


def test_load_settings_rejects_unknown_environment() -> None:
    with pytest.raises(ConfigError, match="OPENCARE_ENV"):
        load_settings({"OPENCARE_ENV": "local"})


def test_load_settings_requires_secret_key_in_production() -> None:
    with pytest.raises(ConfigError, match="OPENCARE_SECRET_KEY"):
        load_settings({"OPENCARE_ENV": "production"})


def test_load_settings_rejects_weak_secret_key_in_production() -> None:
    with pytest.raises(ConfigError, match="OPENCARE_SECRET_KEY"):
        load_settings(
            {
                "OPENCARE_ENV": "production",
                "OPENCARE_SECRET_KEY": "short-secret",
            }
        )


def test_load_settings_requires_access_password_for_private_production() -> None:
    with pytest.raises(ConfigError, match="OPENCARE_ACCESS_PASSWORD"):
        load_settings(
            {
                "OPENCARE_ENV": "production",
                "OPENCARE_SECRET_KEY": "x" * 32,
                "OPENCARE_DEMO_MODE": "false",
            }
        )


def test_load_settings_accepts_private_production_with_required_secrets() -> None:
    settings = load_settings(
        {
            "OPENCARE_ENV": "production",
            "OPENCARE_SECRET_KEY": "x" * 32,
            "OPENCARE_DEMO_MODE": "false",
            "OPENCARE_ACCESS_PASSWORD": "vault-password",
        }
    )

    assert settings.env == "production"
    assert settings.demo_mode is False
    assert settings.secret_key == "x" * 32
    assert settings.access_password == "vault-password"
