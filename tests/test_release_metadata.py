from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "874c44d1308e016c68c58bf257a29a26eea746f6"
REPOSITORY_URL = "https://github.com/KirillNedoboy/open-care-proof-kit"
ISSUES_URL = f"{REPOSITORY_URL}/issues"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_project_metadata_is_complete_without_dependency_or_version_changes() -> None:
    project = tomllib.loads(_read("pyproject.toml"))["project"]

    assert project["version"] == "0.1.0"
    assert project["readme"] == "README.md"
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE"]
    assert project["urls"] == {"Repository": REPOSITORY_URL, "Issues": ISSUES_URL}
    assert project["dependencies"] == [
        "fastapi>=0.111.0",
        "jinja2>=3.1.0",
        "uvicorn[standard]>=0.30.0",
        "pydantic>=2.7.0",
    ]
    assert project["optional-dependencies"]["dev"] == [
        "pytest>=8.2.0",
        "ruff>=0.5.0",
        "mypy>=1.10.0",
        "httpx>=0.27.0",
    ]
    assert "Apache License" in _read("LICENSE")


def test_release_documents_describe_an_undated_private_alpha_candidate() -> None:
    changelog = _read("CHANGELOG.md")
    release_notes = _read("docs/releases/v0.1.0-private-alpha.md")

    assert "## [Unreleased]" in changelog
    assert "## [0.1.0] - Release candidate" in changelog
    assert "no tag" in changelog.lower()
    assert "no public release" in changelog.lower()
    assert "not production-ready" in changelog.lower()
    assert "not clinically validated" in changelog.lower()
    assert "candidate only" in release_notes.lower()
    assert "no tag or public release" in release_notes.lower()
    assert "not production-ready" in release_notes.lower()
    assert "not clinically validated" in release_notes.lower()


def test_operator_checklist_keeps_privacy_recovery_and_stop_boundaries_visible() -> None:
    checklist = _read("docs/private-alpha-operator-checklist.md").lower()

    for required_text in (
        "backup verification",
        "recovery drill",
        "plaintext",
        "absent or empty target",
        "never overwrite active or populated state",
        "exit criteria",
        "unexpected external data transmission",
    ):
        assert required_text in checklist


def test_status_and_capability_matrix_reference_the_accepted_implementation_baseline() -> None:
    status = _read("docs/project-status.md")
    matrix = _read("docs/capability-matrix.md")

    for document in (status, matrix):
        assert BASELINE_COMMIT in document
        assert "accepted implementation baseline" in document.lower()
        assert "296a6d8" not in document

    assert "prior accepted evidence" in status.lower()
    assert "docker container recreation smoke: not executed" in status.lower()
    assert "wheel distribution" in matrix.lower()
    assert "constrained python 3.12" in matrix.lower()
    assert "do not imply clinical validation or production readiness" in matrix.lower()


def test_readme_links_to_candidate_documents_and_security_reporting() -> None:
    readme = _read("README.md")

    for link in (
        "[Changelog](CHANGELOG.md)",
        "[Private-alpha release notes](docs/releases/v0.1.0-private-alpha.md)",
        "[Private-alpha operator checklist](docs/private-alpha-operator-checklist.md)",
        "[Security reporting](SECURITY.md)",
    ):
        assert link in readme
