from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS_PATH = ROOT / "constraints" / "python312.txt"
PIN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*==[A-Za-z0-9][A-Za-z0-9._+!-]*$")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _active_constraint_lines() -> list[str]:
    return [
        line.strip()
        for line in CONSTRAINTS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _constraint_names() -> set[str]:
    return {
        _normalize_name(line.split("==", maxsplit=1)[0])
        for line in _active_constraint_lines()
    }


def _declared_dependency_names() -> set[str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = [
        *pyproject["project"]["dependencies"],
        *pyproject["project"]["optional-dependencies"]["dev"],
    ]
    names: set[str] = set()
    for requirement in dependencies:
        match = NAME_PATTERN.match(requirement)
        assert match is not None
        names.add(_normalize_name(match.group(0)))
    return names


def test_python312_constraints_file_exists() -> None:
    assert CONSTRAINTS_PATH.is_file()


def test_python312_constraints_use_exact_safe_pins_with_unique_normalized_names() -> None:
    lines = _active_constraint_lines()

    assert lines
    assert all(PIN_PATTERN.fullmatch(line) for line in lines)
    assert len(_constraint_names()) == len(lines)
    assert not any(
        token in line.lower()
        for line in lines
        for token in ("-e ", "../", "/", "\\", "://", "git+", "@")
    )


def test_python312_constraints_cover_declared_runtime_and_dev_dependencies() -> None:
    assert _declared_dependency_names() <= _constraint_names()


def test_python312_constraints_document_the_release_baseline() -> None:
    text = CONSTRAINTS_PATH.read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "CPython 3.12" in text
    assert pyproject["project"]["requires-python"] == ">=3.12"
    assert 'python-version: "3.12"' in workflow


def test_repository_controlled_installation_paths_use_python312_constraints() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert '-c constraints/python312.txt -e ".[dev]"' in workflow
    assert "COPY constraints/python312.txt ./constraints/python312.txt" in dockerfile
    assert "-c constraints/python312.txt ." in dockerfile
