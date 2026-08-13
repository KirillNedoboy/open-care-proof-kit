"""Architectural boundary: generic trust core must stay portable.

The generic ``app.agent_trust`` package is a reusable trust layer with no
dependency on OpenCare runtime machinery (Product Core, Family Access,
FastAPI routes, health UI/templates, session stores, Ollama, Sentient SDK).
OpenCare-specific authorization lives in ``app.agent.trust_adapter`` and
implements the generic ``AuthorizationAdapter`` protocol.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import get_type_hints

import pytest

from app.agent_trust.authorization import AuthorizationAdapter

ROOT = Path(__file__).resolve().parents[1]
AGENT_TRUST_DIR = ROOT / "app" / "agent_trust"

NOW = datetime(2027, 8, 2, 10, tzinfo=UTC)

#: Module prefixes the generic trust package must never import.
FORBIDDEN_PREFIXES = (
    "app.product_core",
    "app.family_access",
    "app.main",
    "app.health_vault",
    "app.templates",
    "app.http_security",
    "app.agent.service",
    "app.agent.g2_runtime",
    "app.agent.providers.ollama",
    "app.integrations.sentient",
    "sentient_agent_framework",
    "fastapi",
    "starlette",
)


def _module_names(module: str) -> list[str]:
    return [module] + [f"{module}.{part}" for part in module.split(".")[1:]]


def _forbidden_hits(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported = [node.module]
        else:
            continue
        for name in imported:
            if any(
                name == prefix or name.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_PREFIXES
            ):
                hits.append((name, node.lineno))
    return hits


def test_generic_trust_package_has_no_openCare_runtime_imports() -> None:
    violations: list[str] = []
    for path in sorted(AGENT_TRUST_DIR.glob("*.py")):
        for module, lineno in _forbidden_hits(path):
            violations.append(f"{path.name}:{lineno}: imports {module}")
    assert not violations, "generic app.agent_trust must stay portable:\n" + "\n".join(
        violations
    )


def test_importing_public_api_pulls_no_forbidden_modules() -> None:
    forbidden = ",".join(repr(prefix) for prefix in FORBIDDEN_PREFIXES)
    code = (
        "import sys; import app.agent_trust.api; "
        "bad = [m for m in sys.modules if any("
        f"m == p or m.startswith(p + '.') for p in ({forbidden}))]; "
        "assert not bad, bad"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_opencare_adapter_implements_the_generic_authorization_adapter_contract() -> None:
    trust_adapter = importlib.import_module("app.agent.trust_adapter")
    adapter_class = trust_adapter.OpenCareAuthorizationAdapter
    assert adapter_class.__module__ == "app.agent.trust_adapter"

    adapter = adapter_class(object())  # type: ignore[arg-type]
    assert isinstance(adapter, AuthorizationAdapter)

    actual = inspect.signature(adapter_class.authorize)
    expected = inspect.signature(AuthorizationAdapter.authorize)
    assert list(actual.parameters) == list(expected.parameters)
    for name, parameter in expected.parameters.items():
        assert actual.parameters[name].kind == parameter.kind
    assert get_type_hints(adapter_class.authorize) == get_type_hints(
        AuthorizationAdapter.authorize
    )


def test_adapter_class_is_no_longer_importable_from_generic_core() -> None:
    generic = importlib.import_module("app.agent_trust.authorization")
    assert not hasattr(generic, "OpenCareAuthorizationAdapter")
    with pytest.raises(ImportError):
        from app.agent_trust.authorization import OpenCareAuthorizationAdapter  # noqa: F401


class SequenceIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"trust-id-{self.value}"


def test_adapter_authorization_semantics_unchanged_on_existing_fixtures(
    tmp_path: Path,
) -> None:
    from app.agent.trust_adapter import OpenCareAuthorizationAdapter
    from app.family_access.service import FamilyAccessService
    from app.product_core.sqlite import SQLiteDatabase

    database = SQLiteDatabase(tmp_path / "product.sqlite3")
    database.migrate()
    timestamp = NOW.isoformat()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, 1)",
            ("person-alice", "Alice", None, timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO people VALUES (?, ?, ?, ?, ?, 1)",
            ("person-carol", "Carol", None, timestamp, timestamp),
        )
    service = FamilyAccessService(database, clock=lambda: NOW, id_factory=SequenceIds())
    actor = service.bootstrap(
        username="alice",
        display_name="Alice",
        password="correct horse battery",
        person_ids=["person-alice"],
        own_person_id="person-alice",
        confirm_full_owner_access=True,
    )
    with database.connect() as connection:
        credential_id = str(
            connection.execute(
                "SELECT credential_id FROM actor_credentials WHERE actor_id = ?",
                (actor.actor_id,),
            ).fetchone()[0]
        )
        consent_event_id = str(
            connection.execute(
                "SELECT consent_event_id FROM person_access_assignments WHERE actor_id = ?",
                (actor.actor_id,),
            ).fetchone()[0]
        )

    adapter = OpenCareAuthorizationAdapter(service)
    allowed = adapter.authorize(
        actor_id=actor.actor_id,
        credential_id=credential_id,
        person_id="person-alice",
        required_scopes=frozenset({"person.read", "source.read"}),
        authorized_at=NOW,
    )
    assert allowed.decision == "allow"
    assert allowed.snapshot is not None
    assert allowed.snapshot.consent_event_id == consent_event_id
    assert allowed.snapshot.required_scopes == ["person.read", "source.read"]

    carol = adapter.authorize(
        actor_id=actor.actor_id,
        credential_id=credential_id,
        person_id="person-carol",
        required_scopes=frozenset({"person.read"}),
        authorized_at=NOW,
    )
    assert carol.decision == "deny"
    assert carol.reason_codes == ["required_scope_missing"]

    service.change_password(actor.actor_id, "correct horse battery", "new correct horse battery")
    revoked = adapter.authorize(
        actor_id=actor.actor_id,
        credential_id=credential_id,
        person_id="person-alice",
        required_scopes=frozenset({"person.read"}),
        authorized_at=NOW,
    )
    assert revoked.reason_codes == ["authentication_required"]
