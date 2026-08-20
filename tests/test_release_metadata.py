from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_URL = "https://github.com/KirillNedoboy/open-care-proof-kit"
ISSUES_URL = f"{REPOSITORY_URL}/issues"
REVIEWER_QUICKSTART_URLS = (
    f"{REPOSITORY_URL}/blob/main/docs/adr/0001-opencare-product-direction.md",
    f"{REPOSITORY_URL}/blob/main/docs/project-status.md",
)
MARKDOWN_LINK_RE = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _tracked_markdown_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / path for path in result.stdout.splitlines()]


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
        "pypdf>=6.13,<7",
    ]
    assert project["optional-dependencies"]["dev"] == [
        "pytest>=8.2.0",
        "ruff>=0.5.0",
        "mypy>=1.10.0",
        "httpx>=0.27.0",
    ]
    assert "Apache License" in _read("LICENSE")


def test_release_documents_preserve_published_v010_and_unreleased_phase2() -> None:
    changelog = _read("CHANGELOG.md")
    release_notes = _read("docs/releases/v0.1.0-private-alpha.md")

    assert "## [Unreleased]" in changelog
    assert "## [0.1.0] - 2026-07-31" in changelog
    assert "tag `v0.1.0`" in changelog
    assert "phase 2" in changelog.lower()
    assert "unreleased" in changelog.lower()
    assert "production-ready" in changelog.lower()
    assert "clinically validated" in changelog.lower()
    assert "published as tag `v0.1.0`" in release_notes.lower()
    assert "phase 2" in release_notes.lower()
    assert "after this tag" in release_notes.lower()
    assert "not production-ready" in release_notes.lower()
    assert "clinically validated" in release_notes.lower()


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


def test_status_and_capability_matrix_describe_phase2_release_state() -> None:
    status = _read("docs/project-status.md")
    matrix = _read("docs/capability-matrix.md")

    assert "phase 2" in status.lower()
    assert "`v0.1.0`" in status
    assert "`v0.2.0`" in status
    assert "family permissions" in matrix.lower()
    assert "`implemented`" in matrix.lower()
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


def test_tracked_markdown_local_links_resolve() -> None:
    broken: list[tuple[str, str]] = []
    for document in _tracked_markdown_paths():
        for raw_link in MARKDOWN_LINK_RE.findall(document.read_text(encoding="utf-8")):
            link = raw_link.strip().strip("<>")
            if not link or link.startswith(("#", "http://", "https://", "mailto:", "tel:")):
                continue
            local_path = link.split("#", 1)[0].split(" ", 1)[0]
            if local_path and not (document.parent / local_path).resolve().exists():
                broken.append((document.relative_to(ROOT).as_posix(), raw_link))
    assert not broken


def test_packaged_reviewer_quickstart_links_target_canonical_main_documents() -> None:
    quickstart = _read("app/assets/docs/reviewer_quickstart.md")

    for url in REVIEWER_QUICKSTART_URLS:
        assert url in quickstart
        tracked_path = url.removeprefix(f"{REPOSITORY_URL}/blob/main/")
        assert tracked_path != url
        assert (ROOT / tracked_path).is_file()
