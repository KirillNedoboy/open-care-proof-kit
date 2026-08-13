"""Generic authorization boundary for the trust contract.

G4 portable trust core depends only on this protocol; it never grants access
itself. OpenCare implements the protocol in ``app.agent.trust_adapter`` using
Family Access. Generic code consuming an ``AuthorizationAdapter`` must treat an
``allow`` decision as one snapshot of a live authority's decision, never as a
self-granted right.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.agent_trust.models import AuthorizationDecision


@runtime_checkable
class AuthorizationAdapter(Protocol):
    """Capture one live authorization decision without becoming an authority.

    Implementations translate an OpenCare-specific authority (for example Family
    Access) into the generic trust contract's decision shape. Generic trust code
    never grants access itself; it only consumes decisions from an adapter.
    """

    def authorize(
        self,
        *,
        actor_id: str,
        credential_id: str,
        person_id: str,
        required_scopes: frozenset[str],
        authorized_at: datetime,
    ) -> AuthorizationDecision: ...
