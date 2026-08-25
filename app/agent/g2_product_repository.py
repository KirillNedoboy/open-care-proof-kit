from __future__ import annotations

import json
from datetime import datetime
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
                (audit_id, actor_id, "agent.consent", "session", execution_id,
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
                    "metadata_json": json.dumps(
                        {
                            "access_audit_id": audit_id,
                            "model_id": receipt.model_id,
                            "provider_kind": receipt.provider_kind,
                            "external": receipt.external,
                        }
                    ),
                }
            )
            uow.connection.execute(
                """INSERT INTO access_audit_events
                (audit_event_id, actor_id, action_code, target_class, target_id,
                 outcome, reason_code, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (audit_id, actor_id, "agent.execute", "session", execution_id,
                 {"completed": "success", "failed": "failure", "refused": "denied"}.get(
                     receipt.status, "failure"
                 ), "execution_observed", receipt.completed_at.isoformat()),
            )


    def get_execution_receipt(
        self, execution_id: str, *, actor_id: str, person_id: str
    ) -> dict[str, object] | None:
        with self.database.uow() as uow:
            assert uow.connection is not None
            row = uow.connection.execute(
                """SELECT * FROM agent_execution_receipts
                   WHERE execution_id = ? AND actor_id = ? AND person_id = ?""",
                (execution_id, actor_id, person_id),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        metadata = json.loads(str(data.get("metadata_json") or "{}"))
        return {
            "contract_version": "opencare-execution-receipt/1",
            "receipt_id": data["receipt_id"],
            "envelope_id": data["envelope_id"],
            "started_at": datetime.fromisoformat(str(data["started_at"])),
            "completed_at": datetime.fromisoformat(str(data["completed_at"])),
            "status": data["status"],
            "provider_id": data["provider_id"],
            "model_id": metadata.get("model_id"),
            "provider_kind": metadata.get("provider_kind"),
            "external": metadata.get("external"),
            "used_evidence_ids": json.loads(str(data["used_evidence_ids_json"])),
            "used_tools": json.loads(str(data["used_tools_json"])),
            "output_sha256": data["output_sha256"],
            "reason_codes": json.loads(str(data["reason_codes_json"])),
            "receipt_sha256": data["receipt_sha256"],
        }
