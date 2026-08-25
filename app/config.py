import hashlib
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

SECRET_KEY_MIN_LENGTH = 32
PACKAGE_DIR = Path(__file__).resolve().parent
RUNTIME_ASSETS_DIR = PACKAGE_DIR / "assets"
DEFAULT_DATA_DIR = RUNTIME_ASSETS_DIR / "data"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    env: str
    demo_mode: bool
    data_dir: Path
    reports_dir: Path
    allow_cloud_llm: bool
    secret_key: str | None
    access_password: str | None
    public_registration: bool = False
    vault_source: str = "demo"
    vault_file: Path | None = None
    agent_mode: str = "demo"
    agent_allow_external_llm: bool = False
    llm_responses_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    ollama_endpoint: str | None = "http://127.0.0.1:11434"
    ollama_model: str | None = None
    ollama_timeout_seconds: float = 15.0
    ollama_max_response_bytes: int = 1_000_000
    product_db_path: Path = Path("data/opencare.sqlite3")
    source_dir: Path = Path("data/sources")
    session_db_path: Path = Path(tempfile.gettempdir()) / "opencare-default" / "sessions.sqlite3"
    bootstrap_secret: str | None = None

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def private_mode_enabled(self) -> bool:
        return self.is_production and not self.demo_mode


def _read_env(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    if env is None:
        return os.environ
    return env


def _parse_bool(raw: str, *, var_name: str) -> bool:
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ConfigError(f"{var_name} must be true or false.")


def _read_optional_secret(values: Mapping[str, str], key: str) -> str | None:
    raw = values.get(key)
    if raw is None:
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    return cleaned


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    values = _read_env(env)
    app_env = values.get("OPENCARE_ENV", "development").strip().lower()
    if app_env not in {"development", "production"}:
        raise ConfigError("OPENCARE_ENV must be development or production.")

    demo_mode = _parse_bool(
        values.get("OPENCARE_DEMO_MODE", "true"),
        var_name="OPENCARE_DEMO_MODE",
    )
    allow_cloud_llm = _parse_bool(
        values.get("OPENCARE_ALLOW_CLOUD_LLM", "false"),
        var_name="OPENCARE_ALLOW_CLOUD_LLM",
    )
    public_registration = _parse_bool(
        values.get("OPENCARE_PUBLIC_REGISTRATION", "false"),
        var_name="OPENCARE_PUBLIC_REGISTRATION",
    )
    agent_mode = values.get("OPENCARE_AGENT_MODE", "demo").strip().lower()
    if agent_mode not in {"demo", "openai_responses", "ollama"}:
        raise ConfigError(
            "OPENCARE_AGENT_MODE must be demo, openai_responses or ollama."
        )
    agent_allow_external_llm = _parse_bool(
        values.get("OPENCARE_AGENT_ALLOW_EXTERNAL_LLM", "false"),
        var_name="OPENCARE_AGENT_ALLOW_EXTERNAL_LLM",
    )
    ollama_endpoint_raw = values.get("OPENCARE_OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
    ollama_endpoint = (
        ollama_endpoint_raw.strip()
        if ollama_endpoint_raw is not None and ollama_endpoint_raw.strip()
        else None
    )
    try:
        ollama_timeout_seconds = float(
            values.get("OPENCARE_OLLAMA_TIMEOUT_SECONDS", "15.0")
        )
    except ValueError as exc:
        raise ConfigError("OPENCARE_OLLAMA_TIMEOUT_SECONDS must be a number.") from exc
    try:
        ollama_max_response_bytes = int(
            values.get("OPENCARE_OLLAMA_MAX_RESPONSE_BYTES", "1000000")
        )
    except ValueError as exc:
        raise ConfigError("OPENCARE_OLLAMA_MAX_RESPONSE_BYTES must be an integer.") from exc
    vault_source = values.get("OPENCARE_VAULT_SOURCE", "demo").strip().lower()
    if vault_source not in {"demo", "local_file"}:
        raise ConfigError("OPENCARE_VAULT_SOURCE must be demo or local_file.")
    secret_key = _read_optional_secret(values, "OPENCARE_SECRET_KEY")
    access_password = _read_optional_secret(values, "OPENCARE_ACCESS_PASSWORD")
    vault_file_raw = values.get("OPENCARE_VAULT_FILE")
    vault_file = (
        None
        if vault_file_raw is None or not vault_file_raw.strip()
        else Path(vault_file_raw)
    )
    responses_url_raw = values.get("OPENCARE_LLM_RESPONSES_URL")
    responses_url = (
        None if responses_url_raw is None or not responses_url_raw.strip() else responses_url_raw
    )

    product_db_path = Path(values.get("OPENCARE_PRODUCT_DB_PATH", "data/opencare.sqlite3"))
    source_dir = Path(values.get("OPENCARE_SOURCE_DIR", "data/sources"))
    session_path_raw = values.get("OPENCARE_SESSION_DB_PATH")
    session_db_path = (
        Path(session_path_raw)
        if session_path_raw is not None and session_path_raw.strip()
        else (
            Path("/run/opencare/sessions.sqlite3")
            if app_env == "production"
            else _default_session_db_path(product_db_path)
        )
    )
    settings = Settings(
        env=app_env,
        demo_mode=demo_mode,
        data_dir=Path(values["OPENCARE_DATA_DIR"])
        if "OPENCARE_DATA_DIR" in values
        else DEFAULT_DATA_DIR,
        product_db_path=product_db_path,
        source_dir=source_dir,
        session_db_path=session_db_path,
        reports_dir=Path(values.get("OPENCARE_REPORTS_DIR", "reports")),
        allow_cloud_llm=allow_cloud_llm,
        secret_key=secret_key,
        access_password=access_password,
        public_registration=public_registration,
        bootstrap_secret=_read_optional_secret(values, "OPENCARE_BOOTSTRAP_SECRET"),
        vault_source=vault_source,
        vault_file=vault_file,
        agent_mode=agent_mode,
        agent_allow_external_llm=agent_allow_external_llm,
        llm_responses_url=responses_url,
        llm_api_key=_read_optional_secret(values, "OPENCARE_LLM_API_KEY"),
        llm_model=_read_optional_secret(values, "OPENCARE_LLM_MODEL"),
        ollama_endpoint=ollama_endpoint,
        ollama_model=_read_optional_secret(values, "OPENCARE_OLLAMA_MODEL"),
        ollama_timeout_seconds=ollama_timeout_seconds,
        ollama_max_response_bytes=ollama_max_response_bytes,
    )
    _validate_settings(settings)
    return settings


def _validate_settings(settings: Settings) -> None:
    _validate_session_storage(settings)
    if settings.agent_mode == "openai_responses":
        if not settings.agent_allow_external_llm:
            raise ConfigError("OPENCARE_AGENT_ALLOW_EXTERNAL_LLM must be true for external mode.")
        if (
            settings.llm_responses_url is None
            or not _is_valid_responses_url(settings.llm_responses_url)
        ):
            raise ConfigError("OPENCARE_LLM_RESPONSES_URL must be a complete safe HTTP(S) URL.")
        if settings.llm_api_key is None or settings.llm_model is None:
            raise ConfigError(
                "OPENCARE_LLM_API_KEY and OPENCARE_LLM_MODEL are required for external mode."
            )
    if settings.agent_mode == "ollama":
        if settings.ollama_endpoint is None or not _is_valid_responses_url(
            settings.ollama_endpoint
        ):
            raise ConfigError("OPENCARE_OLLAMA_ENDPOINT must be a complete safe HTTP(S) URL.")
        if settings.ollama_model is None or not settings.ollama_model.strip():
            raise ConfigError("OPENCARE_OLLAMA_MODEL is required for ollama mode.")
    if settings.vault_source == "local_file":
        if settings.vault_file is None:
            raise ConfigError(
                "OPENCARE_VAULT_FILE is required when OPENCARE_VAULT_SOURCE=local_file."
            )
        if not settings.vault_file.is_file():
            raise ConfigError("OPENCARE_VAULT_FILE must point to an existing file.")
        try:
            with settings.vault_file.open("r", encoding="utf-8") as vault_file_handle:
                vault_file_handle.read(1)
        except OSError as exc:
            raise ConfigError(
                f"OPENCARE_VAULT_FILE is not readable: {settings.vault_file.name}"
            ) from exc

    if not settings.is_production:
        return

    if settings.secret_key is None:
        raise ConfigError("OPENCARE_SECRET_KEY is required in production.")
    if len(settings.secret_key) < SECRET_KEY_MIN_LENGTH:
        raise ConfigError(
            "OPENCARE_SECRET_KEY must be at least "
            f"{SECRET_KEY_MIN_LENGTH} characters in production."
        )
    if settings.bootstrap_secret is None or len(settings.bootstrap_secret) < SECRET_KEY_MIN_LENGTH:
        raise ConfigError(
            "OPENCARE_BOOTSTRAP_SECRET must be at least "
            f"{SECRET_KEY_MIN_LENGTH} characters in production."
        )
    if settings.private_mode_enabled and settings.access_password is None:
        raise ConfigError(
            "OPENCARE_ACCESS_PASSWORD is required when production runs with "
            "OPENCARE_DEMO_MODE=false."
        )
    if settings.vault_source == "local_file" and settings.demo_mode:
        raise ConfigError(
            "OPENCARE_DEMO_MODE must be false when production runs with "
            "OPENCARE_VAULT_SOURCE=local_file."
        )


def _is_valid_responses_url(value: str) -> bool:
    if any(ord(character) < 32 for character in value):
        return False
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme in {"http", "https"}
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def _default_session_db_path(product_db_path: Path) -> Path:
    installation = hashlib.sha256(
        str(product_db_path.resolve(strict=False)).encode("utf-8")
    ).hexdigest()[:16]
    return Path(tempfile.gettempdir()).resolve() / f"opencare-{installation}" / "sessions.sqlite3"


def _path_contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_session_storage(settings: Settings) -> None:
    session_path = settings.session_db_path.resolve(strict=False)
    if not session_path.is_absolute():
        raise ConfigError("OPENCARE_SESSION_DB_PATH must be an absolute runtime path.")
    session_dir = session_path.parent
    product_path = settings.product_db_path.resolve(strict=False)
    product_dir = product_path.parent
    source_dir = settings.source_dir.resolve(strict=False)
    overlaps = (
        session_path == product_path
        or _path_contains(product_dir, session_dir)
        or _path_contains(session_dir, product_dir)
        or _path_contains(source_dir, session_dir)
        or _path_contains(session_dir, source_dir)
    )
    if overlaps:
        raise ConfigError(
            "OPENCARE_SESSION_DB_PATH must be outside Product Core and source storage."
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
