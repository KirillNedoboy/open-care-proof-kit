import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, Field

from app.health_vault.models import UNSAFE_TEXT_PATTERNS, VaultDataset
from app.health_vault.read_model import VaultReadModel, build_vault_read_model

ARTIFACT_VERSION = "0.1.0"
BUILDER_NAME = "health_vault_artifact_builder"
BUILDER_VERSION = "0.1.0"

READ_MODEL_FILENAME = "family-vault-read-model.json"
SUMMARY_FILENAME = "family-vault-summary.md"
MANIFEST_FILENAME = "family-vault-manifest.json"


class VaultArtifactFile(BaseModel):
    filename: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    path: Path


class VaultArtifactManifest(BaseModel):
    artifact_version: str = Field(min_length=1)
    created_artifacts: list[dict[str, str]] = Field(default_factory=list)
    demo_only: bool
    synthetic: bool
    provenance_coverage_summary: dict[str, object]
    safety_boundary_notice_count: int
    builder_name: str = Field(min_length=1)
    builder_version: str = Field(min_length=1)
    no_llm_generation: bool
    no_genetics: bool
    no_medical_advice: bool


class VaultArtifactResult(BaseModel):
    manifest: VaultArtifactManifest
    files: list[VaultArtifactFile] = Field(default_factory=list)


def build_vault_artifacts(dataset: VaultDataset, out_dir: Path) -> VaultArtifactResult:
    read_model = build_vault_read_model(dataset)
    _assert_safe_artifact_inputs(read_model)

    files = [
        VaultArtifactFile(
            filename=READ_MODEL_FILENAME,
            artifact_type="health_family_vault_read_model",
            path=out_dir / READ_MODEL_FILENAME,
        ),
        VaultArtifactFile(
            filename=SUMMARY_FILENAME,
            artifact_type="health_family_vault_markdown_summary",
            path=out_dir / SUMMARY_FILENAME,
        ),
        VaultArtifactFile(
            filename=MANIFEST_FILENAME,
            artifact_type="health_family_vault_manifest",
            path=out_dir / MANIFEST_FILENAME,
        ),
    ]
    read_model_artifact = _read_model_artifact(read_model)
    markdown_artifact = _markdown_summary(read_model)
    manifest = _manifest(read_model, files)
    manifest_artifact = manifest.model_dump(mode="json")

    _assert_safety_metadata(read_model_artifact, manifest)
    _assert_safe_text(read_model_artifact)
    _assert_safe_text(markdown_artifact)
    _assert_safe_text(manifest_artifact)

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / READ_MODEL_FILENAME).write_text(
            _json_dump(read_model_artifact),
            encoding="utf-8",
        )
        (out_dir / SUMMARY_FILENAME).write_text(markdown_artifact, encoding="utf-8")
        (out_dir / MANIFEST_FILENAME).write_text(
            _json_dump(manifest_artifact),
            encoding="utf-8",
        )
    except OSError as exc:
        raise ValueError(f"Unable to write Health/Family Vault artifacts: {exc}") from exc

    return VaultArtifactResult(manifest=manifest, files=files)


def _assert_safe_artifact_inputs(read_model: VaultReadModel) -> None:
    if not read_model.family.demo_only:
        raise ValueError("Artifact builder requires demo_only read models.")
    if not read_model.family.synthetic:
        raise ValueError("Artifact builder requires synthetic read models.")
    if read_model.provenance_coverage.records_missing_source != 0:
        raise ValueError("Artifact builder requires complete provenance coverage.")
    if read_model.provenance_coverage.missing_source_item_ids:
        raise ValueError("Artifact builder requires complete provenance coverage.")
    if not read_model.safety_notices:
        raise ValueError("Artifact builder requires safety boundary notices.")


def _read_model_artifact(read_model: VaultReadModel) -> dict[str, object]:
    return {
        "artifact_type": "health_family_vault_read_model",
        "artifact_version": ARTIFACT_VERSION,
        "demo_only": read_model.family.demo_only,
        "synthetic": read_model.family.synthetic,
        "family": read_model.family.model_dump(mode="json"),
        "people": [person.model_dump(mode="json") for person in read_model.people],
        "relationships": [
            relationship.model_dump(mode="json")
            for relationship in read_model.relationships
        ],
        "medications_by_person": _dump_grouped(read_model.medications_by_person),
        "conditions_by_person": _dump_grouped(read_model.conditions_by_person),
        "labs_by_person": _dump_grouped(read_model.labs_by_person),
        "visits_by_person": _dump_grouped(read_model.visits_by_person),
        "timeline": read_model.timeline.model_dump(mode="json"),
        "question_threads": [
            question.model_dump(mode="json") for question in read_model.questions
        ],
        "provenance_coverage": read_model.provenance_coverage.model_dump(mode="json"),
        "safety_boundary_notices": [
            notice.model_dump(mode="json") for notice in read_model.safety_notices
        ],
        "generated_from": {
            "dataset_id": read_model.dataset_id,
            "dataset_version": read_model.version,
            "source_dataset": "validated VaultDataset",
            "deterministic_builder": BUILDER_NAME,
            "deterministic_builder_version": BUILDER_VERSION,
        },
    }


def _dump_grouped(
    grouped: Mapping[str, Sequence[BaseModel]],
) -> dict[str, list[dict[str, object]]]:
    return {
        person_id: [item.model_dump(mode="json") for item in items]
        for person_id, items in grouped.items()
    }


def _manifest(
    read_model: VaultReadModel,
    files: list[VaultArtifactFile],
) -> VaultArtifactManifest:
    return VaultArtifactManifest(
        artifact_version=ARTIFACT_VERSION,
        created_artifacts=[
            {
                "filename": file.filename,
                "artifact_type": file.artifact_type,
            }
            for file in files
        ],
        demo_only=read_model.family.demo_only,
        synthetic=read_model.family.synthetic,
        provenance_coverage_summary=read_model.provenance_coverage.model_dump(mode="json"),
        safety_boundary_notice_count=len(read_model.safety_notices),
        builder_name=BUILDER_NAME,
        builder_version=BUILDER_VERSION,
        no_llm_generation=True,
        no_genetics=True,
        no_medical_advice=True,
    )


def _markdown_summary(read_model: VaultReadModel) -> str:
    lines = [
        "# Health/Family Vault Summary",
        "",
        "## Safety Boundary",
        "- This artifact is synthetic/demo-only.",
        "- It is a deterministic summary of recorded context.",
        "- It is not diagnosis.",
        "- It is not treatment recommendation.",
        "- It is not dosage guidance.",
        "- It is not medication selection.",
        "- It is not start/stop medication advice.",
        "- There is no genetics in V1C.",
        "",
        "## Family Overview",
        f"- Family: {read_model.family.display_name} ({read_model.family.id})",
        f"- People: {read_model.family.people_count}",
        f"- Relationships: {read_model.family.relationship_count}",
        "",
        "## People",
        *_people_lines(read_model),
        "",
        "## Relationships",
        *_relationship_lines(read_model),
        "",
        "## Recorded Medications",
        *_medication_lines(read_model),
        "",
        "## Recorded Conditions / Concerns",
        *_condition_lines(read_model),
        "",
        "## Recorded Labs",
        *_lab_lines(read_model),
        "",
        "## Visits / Encounters",
        *_visit_lines(read_model),
        "",
        "## Timeline",
        *_timeline_lines(read_model),
        "",
        "## Question Workspace",
        *_question_lines(read_model),
        "",
        "## Provenance Coverage",
        *_provenance_lines(read_model),
        "",
        "## What This Artifact Does Not Do",
        "- Does not create medical interpretation.",
        "- Does not use LLM generation.",
        "- Does not add API routes, CLI commands, UI, or templates.",
        "- Does not add genetic data support or genome_profile implementation.",
        "- Does not change PGx behavior or Medication-to-Doctor Briefing.",
        "",
    ]
    return "\n".join(lines)


def _people_lines(read_model: VaultReadModel) -> list[str]:
    return [
        f"- {person.display_name} ({person.id}); role: {person.role}; synthetic: {person.synthetic}"
        for person in read_model.people
    ]


def _relationship_lines(read_model: VaultReadModel) -> list[str]:
    return [
        "- "
        f"{relationship.person_id} -> {relationship.related_person_id} "
        f"({relationship.relationship_type})"
        for relationship in read_model.relationships
    ]


def _medication_lines(read_model: VaultReadModel) -> list[str]:
    lines: list[str] = []
    for person_id, medications in read_model.medications_by_person.items():
        for medication in medications:
            lines.append(
                f"- {person_id}: {medication.name} ({medication.status}); "
                f"{medication.reason_context}; {medication.safety_label}; "
                f"sources: {_source_titles(medication.source_links)}"
            )
    return lines


def _condition_lines(read_model: VaultReadModel) -> list[str]:
    lines: list[str] = []
    for person_id, conditions in read_model.conditions_by_person.items():
        for condition in conditions:
            lines.append(
                f"- {person_id}: {condition.name} ({condition.status}); "
                f"{condition.description}; {condition.safety_label}; "
                f"sources: {_source_titles(condition.source_links)}"
            )
    return lines


def _lab_lines(read_model: VaultReadModel) -> list[str]:
    lines: list[str] = []
    for person_id, labs in read_model.labs_by_person.items():
        for lab in labs:
            lines.append(
                f"- {person_id}: {lab.name} on {lab.collected_on}; "
                f"{lab.result_text}; {lab.safety_label}; "
                f"sources: {_source_titles(lab.source_links)}"
            )
    return lines


def _visit_lines(read_model: VaultReadModel) -> list[str]:
    lines: list[str] = []
    for person_id, visits in read_model.visits_by_person.items():
        for visit in visits:
            lines.append(
                f"- {person_id}: {visit.visit_type} on {visit.date}; "
                f"{visit.summary}; {visit.safety_label}; "
                f"sources: {_source_titles(visit.source_links)}"
            )
    return lines


def _timeline_lines(read_model: VaultReadModel) -> list[str]:
    return [
        f"- {event.date}: {event.person_id} - {event.title} ({event.event_type}); "
        f"sources: {_source_titles(event.source_links)}"
        for event in read_model.timeline.events
    ]


def _question_lines(read_model: VaultReadModel) -> list[str]:
    return [
        f"- {question.id}: {question.question} "
        f"({question.scope}, {question.status}); {question.safety_label}; "
        f"sources: {_source_titles(question.source_links)}"
        for question in read_model.questions
    ]


def _provenance_lines(read_model: VaultReadModel) -> list[str]:
    coverage = read_model.provenance_coverage
    return [
        f"- Total important records: {coverage.total_important_records}",
        f"- Records with source: {coverage.records_with_source}",
        f"- Records missing source: {coverage.records_missing_source}",
        f"- Missing source item IDs: {', '.join(coverage.missing_source_item_ids) or 'none'}",
    ]


def _source_titles(source_links: Sequence[BaseModel]) -> str:
    titles = [str(source.model_dump(mode="json")["source_title"]) for source in source_links]
    return ", ".join(titles)


def _assert_safety_metadata(
    read_model_artifact: dict[str, object],
    manifest: VaultArtifactManifest,
) -> None:
    if not read_model_artifact.get("safety_boundary_notices"):
        raise ValueError("Read-model artifact is missing safety boundary metadata.")
    if manifest.safety_boundary_notice_count < 1:
        raise ValueError("Manifest artifact is missing safety boundary metadata.")
    if not manifest.no_llm_generation or not manifest.no_genetics or not manifest.no_medical_advice:
        raise ValueError("Manifest artifact is missing product boundary metadata.")


def _assert_safe_text(value: object) -> None:
    for text in _walk_strings(value):
        normalized = text.lower()
        for reason, patterns in UNSAFE_TEXT_PATTERNS.items():
            for pattern in patterns:
                if pattern in normalized:
                    raise ValueError(f"unsafe text detected ({reason}): {pattern}")


def _walk_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested_value in value.values():
            strings.extend(_walk_strings(nested_value))
        return strings
    if isinstance(value, list):
        strings = []
        for nested_value in value:
            strings.extend(_walk_strings(nested_value))
        return strings
    return []


def _json_dump(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"
