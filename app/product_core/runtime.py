from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.product_core.persisted_visit_briefs import PersistedVisitBriefService
from app.product_core.portable_vault_export import PortableVaultExportService
from app.product_core.services import (
    Clock,
    IdFactory,
    MedicationLifecycleService,
    PeopleService,
    SourceService,
    default_clock,
    default_id_factory,
)
from app.product_core.sqlite import SQLiteDatabase
from app.product_core.visit_brief import VisitBriefService
from app.product_core.visits import VisitPlanningService


@dataclass(frozen=True)
class ProductCoreRuntime:
    database: SQLiteDatabase
    sources: SourceService
    people: PeopleService
    lifecycle: MedicationLifecycleService
    visit_briefs: VisitBriefService
    persisted_visit_briefs: PersistedVisitBriefService
    portable_vault_exports: PortableVaultExportService
    visits: VisitPlanningService
    clock: Clock
    id_factory: IdFactory


def create_product_core_runtime(
    settings: Settings,
    *,
    clock: Clock = default_clock,
    id_factory: IdFactory = default_id_factory,
) -> ProductCoreRuntime:
    database = SQLiteDatabase(Path(settings.product_db_path))
    sources = SourceService(
        database,
        Path(settings.source_dir),
        clock=clock,
        id_factory=id_factory,
    )
    return ProductCoreRuntime(
        database=database,
        sources=sources,
        people=PeopleService(database, clock=clock, id_factory=id_factory),
        lifecycle=MedicationLifecycleService(
            database,
            clock=clock,
            id_factory=id_factory,
        ),
        visit_briefs=VisitBriefService(database),
        persisted_visit_briefs=PersistedVisitBriefService(
            database,
            clock=clock,
            id_factory=id_factory,
            source_reader=sources.store.read,
        ),
        portable_vault_exports=PortableVaultExportService(database, sources.store),
        visits=VisitPlanningService(database, clock=clock, id_factory=id_factory),
        clock=clock,
        id_factory=id_factory,
    )
