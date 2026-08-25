from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_COMPOSE = PROJECT_ROOT / "docker-compose.prod.yml"
DEVELOPMENT_COMPOSE = PROJECT_ROOT / "docker-compose.yml"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
PRODUCTION_ENV_EXAMPLE = PROJECT_ROOT / "deploy" / "env.production.example"
PRODUCT_DATA_BIND_SOURCE = (
    'source: "${OPENCARE_PRODUCT_DATA_DIR:?OPENCARE_PRODUCT_DATA_DIR is required}"'
)
BACKUP_BIND_SOURCE = 'source: "${OPENCARE_BACKUP_DIR:?OPENCARE_BACKUP_DIR is required}"'


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


def test_production_compose_uses_ephemeral_session_tmpfs_outside_persistent_mounts() -> None:
    compose = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "OPENCARE_SESSION_DB_PATH: /run/opencare/sessions.sqlite3" in compose
    assert "tmpfs:" in compose
    assert "- /run/opencare:mode=0700" in compose
    volume_targets = [
        line.strip() for line in compose.splitlines() if line.strip().startswith("target:")
    ]
    assert all("/run/opencare" not in line for line in volume_targets)


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
    assert "/var/lib/opencare/product-core" not in development
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
