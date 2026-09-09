from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from app.agent.providers.contract import ProviderExecutionRequest
from app.product_core.document_fact_extraction import DocumentFactAnswerV2
from tests.d2_browser_acceptance_server import (
    SYNTHETIC_DOCUMENT_TEXT,
    BrowserAcceptanceProvider,
)

# Mirrors how the real request builder constructs allowed_fields:
# sorted(set(projection.allowed_fields) & DOCUMENT_FACT_TYPES) for the D2.2
# six-family extraction contract.
D22_ALLOWED_FIELDS = (
    "condition",
    "follow_up",
    "lab",
    "medication",
    "procedure",
    "recommendation",
)

ANSWER_FAMILY_KEYS = (
    "medications",
    "conditions",
    "labs",
    "procedures",
    "recommendations",
    "follow_ups",
)


def _d22_request() -> ProviderExecutionRequest:
    return ProviderExecutionRequest(
        question="extract",
        purpose_id="document_fact_extraction",
        action_id="document.extract_facts",
        requested_action="extract",
        evidence=({"page_number": 1, "text": SYNTHETIC_DOCUMENT_TEXT},),
        allowed_tools=("source.read",),
        allowed_fields=D22_ALLOWED_FIELDS,
        output_contract={},
        system_instructions="",
        disclosure_constraints=(),
        prohibited_operations=(),
    )


def test_browser_acceptance_provider_is_external_source_bound_and_reports_calls(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "provider-calls.json"
    provider = BrowserAcceptanceProvider(report_path)
    result = provider.execute(_d22_request())
    assert provider.descriptor.external is True
    assert result.failure is None
    assert result.answer is not None
    assert set(result.answer) == set(ANSWER_FAMILY_KEYS)
    for key in ANSWER_FAMILY_KEYS:
        assert len(result.answer[key]) == 1
    DocumentFactAnswerV2.model_validate(result.answer)
    assert json.loads(report_path.read_text(encoding="utf-8"))["provider_calls"] == 1


def test_canned_answer_evidence_quotes_are_exact_unique_substrings_of_source(
    tmp_path: Path,
) -> None:
    """The server-side locator requires each quote to occur exactly once in the
    persisted page text; pin that validity precondition for all six families."""
    provider = BrowserAcceptanceProvider(tmp_path / "provider-calls.json")
    result = provider.execute(_d22_request())
    assert result.failure is None
    assert result.answer is not None
    quotes = [
        item["evidence_quote"]
        for key in ANSWER_FAMILY_KEYS
        for item in result.answer[key]
    ]
    assert len(quotes) == 6
    for quote in quotes:
        assert SYNTHETIC_DOCUMENT_TEXT.count(quote) == 1


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
    assert "Offline D2.2 browser-acceptance server" in result.stdout
