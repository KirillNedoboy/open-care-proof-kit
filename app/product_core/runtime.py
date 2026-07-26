from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.product_core.services import (
    Clock,
    IdFactory,
    MedicationLifecycleService,
    SourceService,
    default_clock,
    default_id_factory,
)
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visit_brief import VisitBriefService


@dataclass(frozen=True)
class ProductCoreRuntime:
    database: SQLiteDatabase
    sources: SourceService
    lifecycle: MedicationLifecycleService
    visit_briefs: VisitBriefService
    clock: Clock
    id_factory: IdFactory


def create_product_core_runtime(
    settings: Settings,
    *,
    clock: Clock = default_clock,
    id_factory: IdFactory = default_id_factory,
) -> ProductCoreRuntime:
    database = SQLiteDatabase(Path(settings.product_db_path))
    return ProductCoreRuntime(
        database=database,
        sources=SourceService(
            database,
            Path(settings.source_dir),
            clock=clock,
            id_factory=id_factory,
        ),
        lifecycle=MedicationLifecycleService(
            database,
            clock=clock,
            id_factory=id_factory,
        ),
        visit_briefs=VisitBriefService(database),
        clock=clock,
        id_factory=id_factory,
    )
