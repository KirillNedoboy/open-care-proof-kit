from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.agent.providers.contract import ProviderExecutionRequest
from tests.d2_browser_acceptance_server import (
    SYNTHETIC_DOCUMENT_TEXT,
    BrowserAcceptanceProvider,
)


def test_browser_acceptance_provider_is_external_source_bound_and_reports_calls(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "provider-calls.json"
    provider = BrowserAcceptanceProvider(report_path)
    result = provider.execute(
        ProviderExecutionRequest(
            question="extract",
            purpose_id="document_fact_extraction",
            action_id="document.extract_facts",
            requested_action="extract",
            evidence=({"page_number": 1, "text": SYNTHETIC_DOCUMENT_TEXT},),
            allowed_tools=("source.read",),
            allowed_fields=("condition", "lab", "medication"),
            output_contract={},
            system_instructions="",
            disclosure_constraints=(),
            prohibited_operations=(),
        )
    )
    assert provider.descriptor.external is True
    assert result.failure is None
    assert result.answer is not None
    assert len(result.answer["medications"]) == 1
    assert len(result.answer["conditions"]) == 1
    assert len(result.answer["labs"]) == 1
    assert json.loads(report_path.read_text(encoding="utf-8"))["provider_calls"] == 1


def test_browser_acceptance_server_direct_script_help_resolves_app_from_repo_root() -> None:
    script = Path(__file__).with_name("d2_browser_acceptance_server.py")
    repository_root = script.parents[1]
    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Offline D2.1 browser-acceptance server" in result.stdout
