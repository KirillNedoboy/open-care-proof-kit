from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.family_access.policy import PersonAccessPolicy
from app.family_access.service import FamilyAccessService
from app.family_access.sessions import SessionStore
from app.product_core.services import Clock, IdFactory, default_clock, default_id_factory
from app.product_core.sqlite import SQLiteDatabase


@dataclass(frozen=True)
class FamilyAccessRuntime:
    service: FamilyAccessService
    sessions: SessionStore
    settings: Settings


def create_family_access_runtime(
    settings: Settings,
    database: SQLiteDatabase,
    *,
    clock: Clock = default_clock,
    id_factory: IdFactory = default_id_factory,
) -> FamilyAccessRuntime:
    sessions = SessionStore(settings.session_db_path, clock=clock)
    service = FamilyAccessService(
        database,
        clock=clock,
        id_factory=id_factory,
        policy=PersonAccessPolicy(),
        session_invalidator=sessions.invalidate_actor,
    )
    return FamilyAccessRuntime(service=service, sessions=sessions, settings=settings)
