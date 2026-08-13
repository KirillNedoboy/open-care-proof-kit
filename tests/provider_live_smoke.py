"""Optional live Ollama smoke (Sentient G3).

Runs ONLY when a real Ollama runtime is reachable; otherwise the whole module
skips. Detection is a bounded GET to ``{endpoint}/api/tags``; nothing is
installed or downloaded. Synthetic data only — no personal data, no external
provider.
"""

from __future__ import annotations

import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agent.g2_runtime import G2Runtime
from app.agent.providers.ollama import OllamaProvider, OllamaProviderConfig
from app.agent_trust.builders import EnvelopeRequest, TrustedEnvelopeBuilder
from app.agent_trust.models import ProviderDescriptorContract
from app.agent_trust.testing import SyntheticAuthority
from app.family_access.sessions import SessionStore

ENDPOINT = os.environ.get("OPENCARE_OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
MODEL = os.environ.get("OPENCARE_OLLAMA_MODEL", "llama3.2")
FIELDS = ["medication.name", "medication.status"]


def _ollama_reachable(endpoint: str = ENDPOINT, timeout: float = 1.0) -> bool:
    try:
        urllib.request.urlopen(f"{endpoint.rstrip('/')}/api/tags", timeout=timeout)  # noqa: S310
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _ollama_reachable(),
    reason="no reachable local Ollama runtime; offline path verified by trust suite",
)


def test_live_ollama_flow_fails_closed_or_completes_with_receipt(tmp_path: Path) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = SessionStore(tmp_path / "sessions.sqlite", clock=lambda: now)
    created = store.create("actor-alice", "credential-alice")
    store.set_active_person(created.session_token, "person-alice")
    authority = SyntheticAuthority.allowed(now=now)
    builder = TrustedEnvelopeBuilder(authority, clock=lambda: now)
    provider = OllamaProvider(OllamaProviderConfig(endpoint_url=ENDPOINT, model=MODEL))
    descriptor = provider.descriptor
    descriptor_contract = ProviderDescriptorContract(
        provider_id=descriptor.provider_id,
        model_id=descriptor.model_id,
        provider_kind=descriptor.provider_kind,
        endpoint_class=descriptor.endpoint_class,
        external=descriptor.external,
        descriptor_hash=descriptor.descriptor_hash,
    )

    def prepare_envelope(
        *,
        actor_id: str,
        person_id: str,
        purpose_id: str,
        action_id: str,
        question: str,
    ) -> object:
        del question
        return builder.build(
            EnvelopeRequest(
                actor_id=actor_id,
                credential_id="credential-alice",
                person_id=person_id,
                purpose_id=purpose_id,
                action_id=action_id,
                requested_action="Answer a recorded-context question.",
                requested_tools=["context.read", "source.read"],
                evidence_ids=["evidence-medication-alice"],
                disclosure_mode=(
                    "local_only" if not descriptor_contract.external else "external_provider"
                ),
                provider_id=None,
                provider_descriptor=descriptor_contract,
                consent_basis_id="consent-alice",
                ttl_seconds=300,
            )
        )

    runtime = G2Runtime(
        store,
        prepare_envelope=prepare_envelope,
        revalidate=lambda pending, session: bool(pending and session),
        provider=provider,
        clock=lambda: now,
    )
    question = "What medications are recorded?"
    prepared = runtime.prepare(
        created.session_token, question, purpose_id="visit_preparation",
        action_id="summarize_records",
    )
    runtime.grant_disclosure_consent(
        created.session_token, prepared.execution_id, fields=list(FIELDS)
    )
    result = runtime.execute(created.session_token, prepared.execution_id, question)
    assert result.status in {"answered", "refused"}
    if result.status == "answered":
        assert result.answer is not None
    receipt = runtime.get_receipt(created.session_token, prepared.execution_id)
    assert receipt is not None
    assert receipt.status in {"completed", "failed", "refused"}
    # Fail-closed invariant: a live failure must never surface a raw model
    # answer; it produces a receipt with provider_failed instead.
    if result.status != "answered":
        assert result.reason_code in {"provider_failed", "validation_failed"}
        assert receipt.status == "failed"
