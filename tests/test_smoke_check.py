import pytest

from scripts.smoke_check import (
    CheckError,
    HttpResult,
    normalize_base_url,
    validate_private_vault_flow,
    validate_vault_without_password,
)


def test_normalize_base_url_trims_trailing_slash() -> None:
    assert normalize_base_url("https://opencare.example.com/") == (
        "https://opencare.example.com"
    )


def test_validate_vault_without_password_accepts_public_vault() -> None:
    result = validate_vault_without_password(HttpResult(status=200, location=None))

    assert result == "public"


def test_validate_vault_without_password_accepts_private_redirect() -> None:
    result = validate_vault_without_password(
        HttpResult(status=307, location="/access?next=%2Fvault")
    )

    assert result == "private_redirect"


def test_validate_vault_without_password_rejects_unexpected_status() -> None:
    with pytest.raises(CheckError, match="Unexpected /vault response"):
        validate_vault_without_password(HttpResult(status=503, location=None))


def test_validate_private_vault_flow_accepts_redirect_login_and_unlocked_page() -> None:
    validate_private_vault_flow(
        initial=HttpResult(status=307, location="/access?next=%2Fvault"),
        login=HttpResult(status=303, location="/vault"),
        unlocked=HttpResult(status=200, location=None),
    )


def test_validate_private_vault_flow_rejects_missing_initial_redirect() -> None:
    with pytest.raises(CheckError, match="Expected /vault to redirect to /access"):
        validate_private_vault_flow(
            initial=HttpResult(status=200, location=None),
            login=HttpResult(status=303, location="/vault"),
            unlocked=HttpResult(status=200, location=None),
        )


def test_validate_private_vault_flow_rejects_failed_login() -> None:
    with pytest.raises(CheckError, match="Expected successful login redirect"):
        validate_private_vault_flow(
            initial=HttpResult(status=307, location="/access?next=%2Fvault"),
            login=HttpResult(status=401, location=None),
            unlocked=HttpResult(status=200, location=None),
        )


def test_validate_private_vault_flow_rejects_locked_final_vault() -> None:
    with pytest.raises(CheckError, match="Expected unlocked /vault"):
        validate_private_vault_flow(
            initial=HttpResult(status=307, location="/access?next=%2Fvault"),
            login=HttpResult(status=303, location="/vault"),
            unlocked=HttpResult(status=307, location="/access?next=%2Fvault"),
        )
