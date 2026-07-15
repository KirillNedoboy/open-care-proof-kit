import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.agent.models import AuditRecord, PolicyDecision

AUDIT_LOGGER = logging.getLogger("opencare.agent.audit")


def emit_audit(
    *,
    provider_mode: str,
    policy: PolicyDecision,
    validation_result: str,
    citation_source_ids: list[str],
    question_length: int,
    reason_code: str | None,
    latency_ms: int | None,
) -> AuditRecord:
    record = AuditRecord(
        timestamp=datetime.now(tz=UTC).isoformat(),
        request_id=str(uuid4()),
        provider_mode=provider_mode,
        policy_category=policy.decision,
        policy_decision=policy.reason_code,
        validation_result=validation_result,
        citation_source_ids=citation_source_ids,
        question_length=question_length,
        reason_code=reason_code,
        latency_ms=latency_ms,
    )
    AUDIT_LOGGER.info("agent_audit=%s", json.dumps(record.model_dump(), sort_keys=True))
    return record
