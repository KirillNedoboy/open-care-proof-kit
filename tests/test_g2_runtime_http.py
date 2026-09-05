# ruff: noqa: E501
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx

from app.agent.g2_runtime import G2Runtime
from app.agent.provider import HttpResponse
from app.agent.providers.contract import (
    ProviderDescriptor,
    ProviderExecutionRequest,
    ProviderExecutionResult,
    ToolCall,
)
from app.agent.providers.openrouter import OpenRouterProvider, OpenRouterProviderConfig
from app.agent_trust.models import EvidenceItem, ProviderDescriptorContract, ProviderDisclosure
from app.family_access.sessions import SessionStore
from app.main import app


class Provider:
    def __init__(self):
        self.calls = 0
        self._descriptor = ProviderDescriptor(
            provider_id="local.deterministic",
            provider_kind="deterministic",
            provider_mode="local_only",
            endpoint_class="none",
            external=False,
            model_id=None,
        )

    @property
    def descriptor(self) -> ProviderDescriptor:
        return self._descriptor

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        self.calls += 1
        return ProviderExecutionResult(
            answer={
                "answer": "recorded context",
                "question": request.question,
                "fields": list(request.allowed_fields),
            },
            provider_id=self._descriptor.provider_id,
            model_id=None,
            tool_calls=(),
            failure=None,
            runtime_metadata={},
        )


class MutationProvider(Provider):
    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        self.calls += 1
        return ProviderExecutionResult(
            answer={"answer": "mutation attempt"},
            provider_id=self._descriptor.provider_id,
            model_id=None,
            tool_calls=(ToolCall(tool="context.read", operation="write"),),
            failure=None,
            runtime_metadata={},
        )


def envelope_factory(**kwargs):
    item = EvidenceItem(
        evidence_id="evidence-1", evidence_type="record", person_id=kwargs["person_id"],
        resource_scope="source.read", content_sha256="a" * 64, source_ids=["source-1"],
        provenance_status="source_backed", selected_fields=["medication.name"],
        observed_at=datetime.now(UTC),
    )
    return SimpleNamespace(
        envelope_id="sha256:" + "e" * 64, person_id=kwargs["person_id"], purpose_id=kwargs["purpose_id"],
        action_id=kwargs["action_id"], requested_action="Summarize selected records.",
        evidence=[item], allowed_tools=["source.read"],
        disclosure_constraints=[], prohibited_operations=[],
        provider_disclosure=ProviderDisclosure(
            mode="local_only", provider_id=None, consent_basis_id="basis-1",
            allowed_evidence_ids=["evidence-1"], allowed_fields=["medication.name"],
            prohibited_data_classes=["credentials"], retention="request_only",
        ),
    )


def setup(tmp_path: Path):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = SessionStore(tmp_path / "sessions.sqlite", clock=lambda: now)
    created = store.create("actor-alice", "credential-alice")
    store.set_active_person(created.session_token, "person-alice")
    provider = Provider()
    runtime = G2Runtime(store, prepare_envelope=envelope_factory, revalidate=lambda *_: True, provider=provider, clock=lambda: now)
    return runtime, created.session_token, provider, created.csrf_token


def test_runtime_is_consent_gated_and_replay_safe(tmp_path):
    runtime, token, provider, _ = setup(tmp_path)
    prepared = runtime.prepare(token, "What is recorded?", purpose_id="visit_preparation", action_id="summarize_records")
    assert provider.calls == 0
    refused = runtime.execute(token, prepared.execution_id, "What is recorded?")
    assert refused.status == "refused"
    runtime.grant_disclosure_consent(token, prepared.execution_id, fields=["medication.name"])
    answered = runtime.execute(token, prepared.execution_id, "What is recorded?")
    assert answered.status == "answered"
    assert provider.calls == 1
    replay = runtime.execute(token, prepared.execution_id, "What is recorded?")
    assert replay.status == "refused"
    assert replay.reason_code in {"context_changed", "replay"}


def test_http_prepare_consent_execute_receipt(tmp_path):
    runtime, token, _, csrf = setup(tmp_path)
    app.state.g2_runtime = runtime
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            cookies = {"opencare_session": token}
            headers = {"origin": "http://test", "x-opencare-csrf": csrf}
            p = await client.post("/api/chat/prepare", json={"question": "What is recorded?"}, cookies=cookies, headers=headers)
            assert p.status_code == 200
            execution_id = p.json()["execution_id"]
            c = await client.post(f"/api/chat/executions/{execution_id}/consent", json={"fields": ["medication.name"]}, cookies=cookies, headers=headers)
            assert c.status_code == 200
            e = await client.post(f"/api/chat/executions/{execution_id}/execute", json={"question": "What is recorded?"}, cookies=cookies, headers=headers)
            assert e.status_code == 200 and e.json()["status"] == "answered"
            r = await client.get(f"/api/chat/executions/{execution_id}/receipt", cookies=cookies)
            assert r.status_code == 200 and r.json()["receipt_id"].startswith("sha256:")
    asyncio.run(run())


def test_openrouter_provider_uses_existing_consent_and_receipt_contract(tmp_path):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = SessionStore(tmp_path / "sessions.sqlite", clock=lambda: now)
    created = store.create("actor-alice", "credential-alice")
    store.set_active_person(created.session_token, "person-alice")

    provider = OpenRouterProvider(
        OpenRouterProviderConfig(
            api_key="R6_OPENROUTER_SECRET_DO_NOT_RENDER",
            model="synthetic/provider-model",
        ),
        post=lambda *_: HttpResponse(
            status_code=200,
            body=json.dumps(
                {
                    "model": "synthetic/provider-model",
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "answer": "Recorded context only.",
                                        "citations": [],
                                        "unknowns": [],
                                        "doctor_questions": [],
                                        "boundary_notices": [],
                                    }
                                )
                            }
                        }
                    ],
                }
            ).encode(),
        ),
    )
    descriptor = provider.descriptor
    descriptor_contract = ProviderDescriptorContract(
        provider_id=descriptor.provider_id,
        model_id=descriptor.model_id,
        provider_kind=descriptor.provider_kind,
        endpoint_class=descriptor.endpoint_class,
        external=descriptor.external,
        descriptor_hash=descriptor.descriptor_hash,
    )

    def external_envelope(**kwargs):
        item = EvidenceItem(
            evidence_id="evidence-1", evidence_type="record", person_id=kwargs["person_id"],
            resource_scope="source.read", content_sha256="a" * 64, source_ids=["source-1"],
            provenance_status="source_backed", selected_fields=["medication.name"],
            observed_at=now,
        )
        return SimpleNamespace(
            envelope_id="sha256:" + "e" * 64,
            person_id=kwargs["person_id"],
            purpose_id=kwargs["purpose_id"],
            action_id=kwargs["action_id"],
            requested_action="Summarize selected records.",
            evidence=[item],
            allowed_tools=["source.read"],
            disclosure_constraints=[],
            prohibited_operations=[],
            provider_disclosure=ProviderDisclosure(
                mode="external_provider",
                provider_id=descriptor.provider_id,
                provider_descriptor=descriptor_contract,
                consent_basis_id="basis-1",
                allowed_evidence_ids=["evidence-1"],
                allowed_fields=["medication.name"],
                prohibited_data_classes=["credentials"],
                retention="provider_policy",
            ),
        )

    runtime = G2Runtime(
        store,
        prepare_envelope=external_envelope,
        revalidate=lambda *_: True,
        provider=provider,
        project=lambda _projection, _question: {
            "provider_id": "opencare.openrouter",
            "model_id": "synthetic/provider-model",
            "external": True,
        },
        clock=lambda: now,
    )
    prepared = runtime.prepare(
        created.session_token,
        "What is recorded?",
        purpose_id="visit_preparation",
        action_id="summarize_records",
    )
    assert prepared.preview["provider_id"] == "opencare.openrouter"
    assert prepared.preview["external"] is True
    runtime.grant_disclosure_consent(
        created.session_token, prepared.execution_id, fields=["medication.name"]
    )
    result = runtime.execute(created.session_token, prepared.execution_id, "What is recorded?")
    assert result.status == "answered"
    assert result.receipt_id is not None
    receipt = runtime.get_receipt(created.session_token, prepared.execution_id)
    assert receipt is not None
    assert receipt.provider_id == "opencare.openrouter"
    assert receipt.model_id == "synthetic/provider-model"
    assert receipt.provider_kind == "external_http"
    assert receipt.external is True

def test_provider_tool_mutation_is_refused_and_not_returned(tmp_path):
    runtime, token, _, _ = setup(tmp_path)
    provider = MutationProvider()
    runtime.provider = provider
    prepared = runtime.prepare(token, "What is recorded?", purpose_id="visit_preparation", action_id="summarize_records")
    runtime.grant_disclosure_consent(token, prepared.execution_id, fields=["medication.name"])
    result = runtime.execute(token, prepared.execution_id, "What is recorded?")
    assert result.status == "refused"
    assert result.reason_code == "tool_not_allowed"


def test_runtime_keeps_prepared_envelope_stable_across_consent_and_execute(tmp_path):
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = SessionStore(tmp_path / "sessions.sqlite", clock=lambda: now)
    created = store.create("actor-alice", "credential-alice")
    store.set_active_person(created.session_token, "person-alice")
    calls = 0

    def factory(**kwargs):
        nonlocal calls
        calls += 1
        return envelope_factory(**kwargs)

    runtime = G2Runtime(
        store,
        prepare_envelope=factory,
        revalidate=lambda *_: True,
        provider=Provider(),
        clock=lambda: now,
    )
    prepared = runtime.prepare(
        created.session_token,
        "What is recorded?",
        purpose_id="visit_preparation",
        action_id="summarize_records",
    )
    runtime.grant_disclosure_consent(
        created.session_token, prepared.execution_id, fields=["medication.name"]
    )
    result = runtime.execute(
        created.session_token, prepared.execution_id, "What is recorded?"
    )

    assert result.status == "answered"
    assert calls == 1
