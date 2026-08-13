"""Development-only Sentient demo for the OpenCare G2 consent-gated runtime.

Synthetic data only: this module never opens the live OpenCare Product Core
database and is never part of normal OpenCare startup. It binds one fixed
synthetic Actor/Person authorization and serves a demo agent over localhost
(non-production) via the Sentient framework's own ``DefaultServer``.
"""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sentient_agent_framework import DefaultServer

from app.agent.g2_runtime import EnvelopeProjection, G2Runtime
from app.agent.providers.contract import AgentProvider
from app.agent_trust.builders import (
    BuildRefused,
    EnvelopeRequest,
    TrustAuthority,
    TrustedEnvelopeBuilder,
)
from app.agent_trust.identifiers import ActionId, PurposeId
from app.agent_trust.models import ProviderDescriptorContract, TrustEnvelope
from app.agent_trust.testing import SyntheticAuthority
from app.family_access.sessions import SessionStore
from app.integrations.sentient.adapter import (
    ACTION_ID,
    PURPOSE_ID,
    DeterministicDemoProvider,
    OpenCareSentientDemoAgent,
)

ACTOR_ID = "actor-alice"
CREDENTIAL_ID = "credential-alice"
PERSON_ID = "person-alice"
EVIDENCE_IDS = ["evidence-medication-alice"]
CONSENT_BASIS_ID = "consent-alice"
FIXED_REQUESTED_ACTION = "Answer a recorded-context question"
TTL_SECONDS = 900


@dataclass(frozen=True)
class DemoContext:
    """Fixed synthetic context the demo agent is bound to."""

    runtime: G2Runtime
    session_token: str
    provider: AgentProvider
    projection: EnvelopeProjection
    now: datetime


def _descriptor_contract(provider: AgentProvider) -> ProviderDescriptorContract:
    descriptor = provider.descriptor
    return ProviderDescriptorContract(
        provider_id=descriptor.provider_id,
        model_id=descriptor.model_id,
        provider_kind=descriptor.provider_kind,
        endpoint_class=descriptor.endpoint_class,
        external=descriptor.external,
        descriptor_hash=descriptor.descriptor_hash,
    )


def build_demo_context(
    store_dir: Path,
    *,
    now: datetime | None = None,
    authority: TrustAuthority | None = None,
    provider: AgentProvider | None = None,
) -> DemoContext:
    """Build a fresh synthetic G2 demo context; fails closed on any problem."""
    try:
        now = now or datetime.now(UTC)
        store_dir = Path(store_dir)
        db_path = store_dir / "sessions.sqlite"
        if db_path.exists():
            raise RuntimeError("refusing to reuse an existing session store (live vault guard)")
        store = SessionStore(db_path, clock=lambda: now)
        created = store.create(ACTOR_ID, CREDENTIAL_ID)
        store.set_active_person(created.session_token, PERSON_ID)
        authority = authority or SyntheticAuthority.allowed(now=now)
        builder = TrustedEnvelopeBuilder(authority, clock=lambda: now)

        provider = provider or DeterministicDemoProvider()
        provider_descriptor = _descriptor_contract(provider)

        def _prepare_envelope(
            *,
            actor_id: str,
            person_id: str,
            purpose_id: PurposeId,
            action_id: ActionId,
            question: str,
        ) -> TrustEnvelope:
            del question
            if actor_id != ACTOR_ID or person_id != PERSON_ID:
                raise BuildRefused(["identity_binding_required"])
            request = EnvelopeRequest(
                actor_id=actor_id,
                credential_id=CREDENTIAL_ID,
                person_id=person_id,
                purpose_id=purpose_id,
                action_id=action_id,
                requested_action=FIXED_REQUESTED_ACTION,
                requested_tools=["context.read", "source.read"],
                evidence_ids=list(EVIDENCE_IDS),
                disclosure_mode="local_only",
                provider_id=None,
                provider_descriptor=provider_descriptor,
                consent_basis_id=CONSENT_BASIS_ID,
                ttl_seconds=TTL_SECONDS,
            )
            return builder.build(request)

        def _project(projection: EnvelopeProjection, question: str) -> dict[str, Any]:
            del question
            return {
                "envelope_id": projection.envelope_id,
                "purpose_id": projection.purpose_id,
                "action_id": projection.action_id,
                "evidence": [
                    {
                        "evidence_id": item["evidence_id"],
                        "selected_fields": list(item["selected_fields"]),
                    }
                    for item in projection.evidence
                ],
            }

        provider = provider or DeterministicDemoProvider()
        runtime = G2Runtime(
            store,
            prepare_envelope=_prepare_envelope,
            revalidate=lambda pending, session: bool(pending and session),
            provider=provider,
            project=_project,
            clock=lambda: now,
        )
        envelope = runtime.prepare_envelope(
            actor_id=ACTOR_ID,
            person_id=PERSON_ID,
            purpose_id=PURPOSE_ID,
            action_id=ACTION_ID,
            question="",
        )
        projection = EnvelopeProjection.from_envelope(envelope)
        return DemoContext(
            runtime=runtime,
            session_token=created.session_token,
            provider=provider,
            projection=projection,
            now=now,
        )
    except Exception as exc:
        raise RuntimeError(
            "synthetic demo authority unavailable; refusing to fall back to live vault"
        ) from exc


def main() -> None:
    """Run the demo agent over the Sentient framework's localhost server."""
    parser = argparse.ArgumentParser(
        description="OpenCare Sentient demo agent (synthetic data only; non-production)."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    tmp_dir = tempfile.mkdtemp(prefix="opencare-sentient-demo-")
    context = build_demo_context(Path(tmp_dir))
    agent = OpenCareSentientDemoAgent("OpenCare Sentient Demo (synthetic only)", context)
    DefaultServer(agent).run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
