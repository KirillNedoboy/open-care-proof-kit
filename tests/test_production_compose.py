from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_COMPOSE = PROJECT_ROOT / "docker-compose.prod.yml"
DEVELOPMENT_COMPOSE = PROJECT_ROOT / "docker-compose.yml"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
PRODUCTION_ENV_EXAMPLE = PROJECT_ROOT / "deploy" / "env.production.example"
DOCKERIGNORE = PROJECT_ROOT / ".dockerignore"
PRODUCT_DATA_BIND_SOURCE = (
    'source: "${OPENCARE_PRODUCT_DATA_DIR:?OPENCARE_PRODUCT_DATA_DIR is required}"'
)
BACKUP_BIND_SOURCE = 'source: "${OPENCARE_BACKUP_DIR:?OPENCARE_BACKUP_DIR is required}"'
R6_PROVIDER_DEFAULTS = {
    "OPENCARE_PUBLIC_REGISTRATION: ${OPENCARE_PUBLIC_REGISTRATION:-false}",
    "OPENCARE_ALLOW_CLOUD_LLM: ${OPENCARE_ALLOW_CLOUD_LLM:-false}",
    "OPENCARE_AGENT_MODE: ${OPENCARE_AGENT_MODE:-demo}",
    "OPENCARE_AGENT_ALLOW_EXTERNAL_LLM: ${OPENCARE_AGENT_ALLOW_EXTERNAL_LLM:-false}",
    "OPENCARE_LLM_RESPONSES_URL: ${OPENCARE_LLM_RESPONSES_URL:-}",
    "OPENCARE_LLM_API_KEY: ${OPENCARE_LLM_API_KEY:-}",
    "OPENCARE_LLM_MODEL: ${OPENCARE_LLM_MODEL:-}",
    "OPENCARE_OPENROUTER_API_KEY: ${OPENCARE_OPENROUTER_API_KEY:-}",
    "OPENCARE_OPENROUTER_MODEL: ${OPENCARE_OPENROUTER_MODEL:-}",
    "OPENCARE_OLLAMA_ENDPOINT: ${OPENCARE_OLLAMA_ENDPOINT:-http://127.0.0.1:11434}",
    "OPENCARE_OLLAMA_MODEL: ${OPENCARE_OLLAMA_MODEL:-}",
    "OPENCARE_OLLAMA_TIMEOUT_SECONDS: ${OPENCARE_OLLAMA_TIMEOUT_SECONDS:-15.0}",
    "OPENCARE_OLLAMA_MAX_RESPONSE_BYTES: ${OPENCARE_OLLAMA_MAX_RESPONSE_BYTES:-1000000}",
}


def test_production_compose_uses_required_persistent_product_core_mounts() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "OPENCARE_PRODUCT_DB_PATH: /var/lib/opencare/product-core/database.sqlite3" in compose
    assert "OPENCARE_SOURCE_DIR: /var/lib/opencare/product-core/sources" in compose
    assert PRODUCT_DATA_BIND_SOURCE in compose
    assert "target: /var/lib/opencare/product-core" in compose
    assert BACKUP_BIND_SOURCE in compose
    assert "target: /var/backups/opencare" in compose
    assert "OPENCARE_BOOTSTRAP_SECRET: ${OPENCARE_BOOTSTRAP_SECRET}" in compose
    assert "OPENCARE_LOCAL_VAULT_PATH" not in compose


def test_production_compose_passes_current_optional_configuration_safely() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    for variable in (
        "OPENCARE_PUBLIC_REGISTRATION",
        "OPENCARE_AGENT_MODE",
        "OPENCARE_AGENT_ALLOW_EXTERNAL_LLM",
        "OPENCARE_LLM_RESPONSES_URL",
        "OPENCARE_LLM_API_KEY",
        "OPENCARE_LLM_MODEL",
        "OPENCARE_OPENROUTER_API_KEY",
        "OPENCARE_OPENROUTER_MODEL",
        "OPENCARE_OLLAMA_ENDPOINT",
        "OPENCARE_OLLAMA_MODEL",
        "OPENCARE_OLLAMA_TIMEOUT_SECONDS",
        "OPENCARE_OLLAMA_MAX_RESPONSE_BYTES",
    ):
        assert f"{variable}:" in compose
    assert "OPENCARE_AGENT_MODE: ${OPENCARE_AGENT_MODE:-demo}" in compose
    assert (
        "OPENCARE_AGENT_ALLOW_EXTERNAL_LLM: "
        "${OPENCARE_AGENT_ALLOW_EXTERNAL_LLM:-false}" in compose
    )
    assert "OPENCARE_PUBLIC_REGISTRATION: ${OPENCARE_PUBLIC_REGISTRATION:-false}" in compose


def test_production_compose_keeps_app_private_but_provider_egress_capable() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    app_section = compose.split("\n  opencare:\n", 1)[1].split("\nnetworks:\n", 1)[0]
    assert "ports:" not in app_section
    assert "- app_internal" in app_section
    assert "- provider_egress" in app_section
    assert "internal: true" in compose


def test_development_compose_persists_product_core_without_hiding_demo_assets() -> None:
    compose = DEVELOPMENT_COMPOSE.read_text(encoding="utf-8")

    assert "      - opencare_product_data:/var/lib/opencare/product-core" in compose
    assert "target: /app/data" not in compose
    assert (
        "OPENCARE_PRODUCT_DB_PATH: /var/lib/opencare/product-core/"
        "database.sqlite3" in compose
    )


def test_dockerfile_declares_stable_non_root_runtime_identity() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "groupadd --gid 10001 opencare" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "mkdir -p /app/data /app/reports /run/opencare" in dockerfile


def test_dockerignore_excludes_runtime_and_operator_data() -> None:
    dockerignore = (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8")

    for pattern in (".git", ".env", "private", "*.sqlite3", "data/sources/*"):
        assert pattern in dockerignore


def test_production_compose_uses_ephemeral_session_tmpfs_outside_persistent_mounts() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "OPENCARE_SESSION_DB_PATH: /run/opencare/sessions.sqlite3" in compose
    assert "tmpfs:" in compose
    assert "- /run/opencare:mode=0700" in compose
    volume_targets = [
        line.strip() for line in compose.splitlines() if line.strip().startswith("target:")
    ]
    assert all("/run/opencare" not in line for line in volume_targets)


def test_production_compose_passes_public_and_r6_provider_settings_with_safe_defaults() -> None:
    production = PRODUCTION_COMPOSE.read_text(encoding="utf-8")
    development = DEVELOPMENT_COMPOSE.read_text(encoding="utf-8")

    for setting in R6_PROVIDER_DEFAULTS:
        assert f"      {setting}" in production
        assert f"      {setting}" in development


def test_production_compose_keeps_app_non_root_private_and_egress_capable() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")
    app_service = compose.split("\n  opencare:", 1)[1].split("\nnetworks:", 1)[0]

    assert 'user: "10001:10001"' in app_service
    assert "no-new-privileges:true" in app_service
    assert "cap_drop:\n      - ALL" in app_service
    assert "ports:" not in app_service
    assert 'expose:\n      - "8000"' in app_service
    assert "      - app_internal\n      - provider_egress" in app_service
    assert "  app_internal:\n    internal: true" in compose
    assert "  provider_egress:\n" in compose


def test_production_compose_uses_readyz_healthcheck_and_owned_session_tmpfs() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "http://127.0.0.1:8000/readyz" in compose
    assert "- /run/opencare:mode=0700,uid=10001,gid=10001" in compose


def test_dockerfile_declares_fixed_non_root_runtime_identity_and_directories() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert "groupadd --gid 10001 opencare" in dockerfile
    assert "useradd --uid 10001 --gid 10001" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "/run/opencare" in dockerfile
    assert "/var/lib/opencare/product-core" in dockerfile
    assert "/var/backups/opencare" in dockerfile
    assert 'CMD ["uvicorn", "app.main:app"' in dockerfile


def test_development_compose_persists_local_product_core_data() -> None:
    compose = DEVELOPMENT_COMPOSE.read_text(encoding="utf-8")

    assert "      - opencare_product_data:/var/lib/opencare/product-core" in compose
    assert "target: /app/data" not in compose
    assert "volumes:\n  opencare_product_data:" in compose


def test_dockerignore_excludes_sensitive_runtime_and_operator_paths() -> None:
    dockerignore = DOCKERIGNORE.read_text(encoding="utf-8")

    for pattern in (
        ".env",
        ".env.*",
        "deploy/env.production",
        "private",
        "vault.local.json",
        "*.sqlite3",
        "*.sqlite3-*",
        "data/sources/*",
        "data/private/*",
    ):
        assert pattern in dockerignore
    assert "!.env.example" in dockerignore


def test_container_trusts_forwarded_https_from_the_internal_caddy_proxy() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert '"--proxy-headers"' in dockerfile
    assert '"--forwarded-allow-ips", "*"' in dockerfile


def test_production_compose_keeps_host_paths_and_secrets_out_of_app_environment() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "      OPENCARE_PRODUCT_DATA_DIR:" not in compose
    assert "      OPENCARE_BACKUP_DIR:" not in compose
    source_lines = [line for line in compose.splitlines() if line.strip().startswith("source:")]
    assert all("OPENCARE_SECRET_KEY" not in line for line in source_lines)
    assert all("OPENCARE_ACCESS_PASSWORD" not in line for line in source_lines)


def test_production_compose_has_no_reports_volume_and_development_remains_unchanged() -> None:
    production = PRODUCTION_COMPOSE.read_text(encoding="utf-8")
    development = DEVELOPMENT_COMPOSE.read_text(encoding="utf-8")

    assert "opencare_reports" not in production
    assert "OPENCARE_PRODUCT_DATA_DIR" not in development
    assert "OPENCARE_BACKUP_DIR" not in development
    assert "/var/backups/opencare" not in development


def test_production_environment_example_has_nonsecret_relative_persistence_paths() -> None:
    environment = PRODUCTION_ENV_EXAMPLE.read_text(encoding="utf-8")

    assert "OPENCARE_PRODUCT_DATA_DIR=./private/opencare-product-core" in environment
    assert "OPENCARE_BACKUP_DIR=./private/opencare-backups" in environment
    assert "OPENCARE_SECRET_KEY=replace-with-" in environment
    assert "OPENCARE_ACCESS_PASSWORD=replace-with-" in environment
    assert "OPENCARE_BOOTSTRAP_SECRET=replace-with-" in environment


def test_production_documentation_describes_product_core_persistence() -> None:
    documents = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs" / "deployment.md",
        PROJECT_ROOT / "docs" / "production_deployment.md",
        PROJECT_ROOT / "docs" / "project-status.md",
        PROJECT_ROOT / "docs" / "capability-matrix.md",
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in documents)

    assert "No database persistence" not in content
    assert "OPENCARE_PRODUCT_DATA_DIR" in content
    assert "OPENCARE_BACKUP_DIR" in content
    assert "deployment changes remain deferred" not in content
