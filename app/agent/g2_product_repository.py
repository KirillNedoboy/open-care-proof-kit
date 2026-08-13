from __future__ import annotations

import json
from typing import Any

from app.agent_trust.models import ExecutionReceipt
from app.product_core.sqlite import SQLiteDatabase


class ProductCoreG2Repository:
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save_consent(
        self,
        *,
        execution_id: str,
        consent_id: str,
        actor_id: str,
        person_id: str,
        purpose_id: str,
        action_id: str,
        envelope_id: str,
        provider_id: str,
        provider_hash: str,
        fields: list[str],
        policy_version: str,
        consented_at: Any,
        expires_at: Any,
        consent_hash: str,
    ) -> None:
        audit_id = f"g2-consent:{consent_id}"
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            uow.consent_records.insert(
                {
                    "consent_id": consent_id,
                    "execution_id": execution_id,
                    "actor_id": actor_id,
                    "person_id": person_id,
                    "purpose": purpose_id,
                    "action": action_id,
                    "envelope_id": envelope_id,
                    "provider_id": provider_id,
                    "provider_descriptor_hash": provider_hash,
                    "disclosure_metadata_json": json.dumps({"fields": fields}),
                    "policy_version": policy_version,
                    "consented_at": consented_at.isoformat(),
                    "expires_at": expires_at.isoformat(),
                    "consent_hash": consent_hash,
                    "metadata_json": json.dumps({"access_audit_id": audit_id}),
                }
            )
            uow.connection.execute(
                """INSERT INTO access_audit_events
                (audit_event_id, actor_id, action_code, target_class, target_id,
                 outcome, reason_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (audit_id, actor_id, "agent.consent", "execution", execution_id,
                 "success", "consent_granted", consented_at.isoformat()),
            )

    def save_execution_receipt(
        self,
        receipt: ExecutionReceipt,
        *,
        execution_id: str,
        consent_id: str,
        actor_id: str,
        person_id: str,
        mutation_attempted: bool,
    ) -> None:
        audit_id = f"g2-receipt:{receipt.receipt_id}"
        with self.database.uow(begin_mode="IMMEDIATE") as uow:
            assert uow.connection is not None
            uow.execution_receipts.insert(
                {
                    "receipt_id": receipt.receipt_id,
                    "execution_id": execution_id,
                    "consent_id": consent_id,
                    "actor_id": actor_id,
                    "person_id": person_id,
                    "envelope_id": receipt.envelope_id,
                    "provider_id": receipt.provider_id or "local",
                    "status": receipt.status,
                    "started_at": receipt.started_at.isoformat(),
                    "completed_at": receipt.completed_at.isoformat(),
                    "used_evidence_ids_json": json.dumps(receipt.used_evidence_ids),
                    "used_tools_json": json.dumps(receipt.used_tools),
                    "output_sha256": receipt.output_sha256,
                    "mutation_attempted": int(mutation_attempted),
                    "reason_codes_json": json.dumps(receipt.reason_codes),
                    "receipt_sha256": receipt.receipt_sha256,
                    "metadata_json": json.dumps({"access_audit_id": audit_id}),
                }
            )
            uow.connection.execute(
                """INSERT INTO access_audit_events
                (audit_event_id, actor_id, action_code, target_class, target_id,
                 outcome, reason_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (audit_id, actor_id, "agent.execute", "execution", execution_id,
                 receipt.status, "execution_observed", receipt.completed_at.isoformat()),
            )


    def get_execution_receipt(self, execution_id: str) -> dict[str, object] | None:
        with self.database.uow() as uow:
            row = uow.execution_receipts.get_by_execution(execution_id)
        return None if row is None else dict(row)
