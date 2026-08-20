from __future__ import annotations

import tomllib
from pathlib import Path

from app import __version__
from app.product_core.migrations import PRODUCT_MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]
def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_current_repository_truth_is_published_and_versioned() -> None:
    status = _read("docs/project-status.md")
    matrix = _read("docs/capability-matrix.md")
    readme = _read("README.md")
    project = tomllib.loads(_read("pyproject.toml"))["project"]

    assert "Public `main` is a mutable Git ref." in status
    assert "P3-final implementation" in status
    assert "R1 repository-truth" in status
    assert "contains the completed G1-G5, P1, P2, D1, and P3 implementation" in readme
    assert "P3 Genetics Research Studio (implemented and published on public" in status
    assert "P3 is part of the published" in matrix
    assert "P3 branch" not in matrix
    assert "pending integration" not in matrix
    assert "Genetics remains a future layer" not in readme
    assert "no document ingestion" not in readme.lower()
    assert project["version"] == __version__ == "0.3.0.dev0"
    assert PRODUCT_MIGRATIONS[-1].version == 9


def test_reviewer_commands_and_ci_gates_are_current() -> None:
    ci = _read(".github/workflows/ci.yml")
    for module in ("g5_review", "p1_review", "p2_review", "d1_review", "p3_review"):
        assert (ROOT / "evals" / f"{module}.py").is_file()
        assert f"python -m evals.{module}" in ci or module == "g5_review"
    assert "python -m pip check" in ci
    assert "git diff --check" in ci
    assert "node --check app/static/product_core_workspace.js" in ci
    assert "node --check app/static/genetics.js" in ci
