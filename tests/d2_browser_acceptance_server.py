"""Offline D2.1 browser-acceptance server.

Run this file directly from the repository root.  It creates an isolated
Product Core/session/source/report tree, installs one synthetic external
provider before the application lifespan starts, and serves the real app via
uvicorn.  The provider never performs network I/O and records only its call
count in the report file.

Example::

    py -3.12 tests/d2_browser_acceptance_server.py --port 8765

The launch paths can be overridden with ``D2_BROWSER_*`` environment
variables or the corresponding command-line options.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from app.agent.providers.contract import (  # noqa: E402
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ProviderFailure,
)

SYNTHETIC_DOCUMENT_TEXT = (
    "Current medication: Aspirin 81 mg daily. "
    "Diagnosis: hypertension. "
    "Lab: Hemoglobin 13.2 g/dL."
)


@dataclass(frozen=True)
class BrowserHarnessPaths:
    work_dir: Path
    product_db_path: Path
    source_dir: Path
    session_db_path: Path
    report_path: Path
    synthetic_source_path: Path


def _path_from_env_or_default(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value and value.strip() else default


def configure_environment(
    *,
    work_dir: Path | None = None,
    product_db_path: Path | None = None,
    source_dir: Path | None = None,
    session_db_path: Path | None = None,
    report_path: Path | None = None,
    synthetic_source_path: Path | None = None,
) -> BrowserHarnessPaths:
    """Set isolated app paths before importing ``app.main``."""
    selected_work_dir = work_dir or _path_from_env_or_default(
        "D2_BROWSER_WORK_DIR",
        Path(tempfile.mkdtemp(prefix="opencare-d2-browser-")),
    )
    selected_work_dir.mkdir(parents=True, exist_ok=True)
    paths = BrowserHarnessPaths(
        work_dir=selected_work_dir,
        product_db_path=product_db_path
        or _path_from_env_or_default(
            "D2_BROWSER_PRODUCT_DB_PATH", selected_work_dir / "product" / "db.sqlite3"
        ),
        source_dir=source_dir
        or _path_from_env_or_default(
            "D2_BROWSER_SOURCE_DIR", selected_work_dir / "sources"
        ),
        session_db_path=session_db_path
        or _path_from_env_or_default(
            "D2_BROWSER_SESSION_DB_PATH", selected_work_dir / "runtime" / "sessions.sqlite3"
        ),
        report_path=report_path
        or _path_from_env_or_default(
            "D2_BROWSER_REPORT_PATH", selected_work_dir / "provider-calls.json"
        ),
        synthetic_source_path=synthetic_source_path
        or _path_from_env_or_default(
            "D2_BROWSER_SYNTHETIC_SOURCE_PATH",
            selected_work_dir / "synthetic-document.txt",
        ),
    )
    for key, value in {
        "OPENCARE_PRODUCT_DB_PATH": paths.product_db_path,
        "OPENCARE_SOURCE_DIR": paths.source_dir,
        "OPENCARE_SESSION_DB_PATH": paths.session_db_path,
        "OPENCARE_DATA_DIR": paths.work_dir / "data",
        "OPENCARE_REPORTS_DIR": paths.work_dir / "reports",
        "OPENCARE_ENV": "development",
        "OPENCARE_DEMO_MODE": "true",
        "OPENCARE_AGENT_MODE": "demo",
        "OPENCARE_ALLOW_CLOUD_LLM": "false",
        "OPENCARE_PUBLIC_REGISTRATION": "false",
    }.items():
        os.environ[key] = str(value)
    paths.synthetic_source_path.parent.mkdir(parents=True, exist_ok=True)
    if paths.synthetic_source_path.exists():
        if paths.synthetic_source_path.read_text(encoding="utf-8") != SYNTHETIC_DOCUMENT_TEXT:
            raise ValueError("D2 browser synthetic source path contains unexpected content")
    else:
        paths.synthetic_source_path.write_text(SYNTHETIC_DOCUMENT_TEXT, encoding="utf-8")
    return paths


class BrowserAcceptanceProvider:
    """A deterministic, no-network external descriptor for browser closure."""

    def __init__(self, report_path: Path) -> None:
        self.report_path = report_path
        self.calls = 0

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            provider_id="tests.d2-browser-external",
            provider_kind="external_http",
            provider_mode="external_provider",
            endpoint_class="non_loopback",
            external=True,
            model_id="d2-browser-model",
        )

    def _write_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            json.dumps({"provider_calls": self.calls}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        self.calls += 1
        self._write_report()
        if request.evidence != (
            {"page_number": 1, "text": SYNTHETIC_DOCUMENT_TEXT},
        ):
            return ProviderExecutionResult(
                answer=None,
                provider_id=self.descriptor.provider_id,
                model_id=self.descriptor.model_id,
                tool_calls=(),
                failure=ProviderFailure(
                    reason_code="synthetic_source_mismatch",
                    message="The browser harness accepts only its synthetic TXT source.",
                ),
            )
        return ProviderExecutionResult(
            answer={
                "medications": [
                    {
                        "page_number": 1,
                        "evidence_quote": "Current medication: Aspirin 81 mg daily.",
                        "display_name": "Aspirin",
                        "schedule_text": "81 mg daily",
                    }
                ],
                "conditions": [
                    {
                        "page_number": 1,
                        "evidence_quote": "Diagnosis: hypertension.",
                        "display_name": "hypertension",
                    }
                ],
                "labs": [
                    {
                        "page_number": 1,
                        "evidence_quote": "Lab: Hemoglobin 13.2 g/dL.",
                        "test_name": "Hemoglobin",
                        "result_text": "13.2",
                        "unit_text": "g/dL",
                    }
                ],
            },
            provider_id=self.descriptor.provider_id,
            model_id=self.descriptor.model_id,
            tool_calls=(),
            failure=None,
        )


def create_application(paths: BrowserHarnessPaths | None = None) -> Any:
    """Configure paths/provider and return the real FastAPI app."""
    selected_paths = paths or configure_environment()
    # Import only after the isolated paths have been placed in the process
    # environment.  Patch the factory before uvicorn starts the lifespan.
    from app.config import clear_settings_cache

    clear_settings_cache()
    import app.main as main_module

    provider = BrowserAcceptanceProvider(selected_paths.report_path)
    main_module._build_agent_provider = lambda _settings: provider
    main_module.app.state.d2_browser_acceptance_provider = provider
    main_module.app.state.d2_browser_acceptance_paths = selected_paths
    return main_module.app


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("D2_BROWSER_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("D2_BROWSER_PORT", "8765"))
    )
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--product-db-path", type=Path, default=None)
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--session-db-path", type=Path, default=None)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--synthetic-source-path", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    paths = configure_environment(
        work_dir=args.work_dir,
        product_db_path=args.product_db_path,
        source_dir=args.source_dir,
        session_db_path=args.session_db_path,
        report_path=args.report_path,
        synthetic_source_path=args.synthetic_source_path,
    )
    application = create_application(paths)
    print(f"D2 browser synthetic source: {paths.synthetic_source_path}", flush=True)
    print(f"D2 browser provider report: {paths.report_path}", flush=True)
    import uvicorn

    uvicorn.run(application, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
