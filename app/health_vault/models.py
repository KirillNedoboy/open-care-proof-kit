from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RelationshipType = Literal["self", "spouse", "parent", "child", "sibling", "other"]
RecordStatus = Literal["active", "resolved", "historical", "suspected", "ruled_out", "unknown"]
MedicationStatus = Literal["current", "past", "planned", "unknown"]
SourceType = Literal[
    "demo_note",
    "lab_report",
    "visit_note",
    "medication_record",
    "user_observation",
    "synthetic_document",
]
EvidenceStrength = Literal[
    "source_backed",
    "user_reported",
    "inferred_from_demo_context",
    "unknown",
]
QuestionStatus = Literal["open", "answered", "needs_source", "archived"]
QuestionScope = Literal["person", "family"]

UNSAFE_TEXT_PATTERNS = {
    "diagnosis by system": [
        "opencare diagnosis",
        "system diagnosis",
        "diagnosed by opencare",
        "diagnosis:",
    ],
    "dosage advice": [
        "increase the dose",
        "decrease the dose",
        "dose should",
        "dosage recommendation",
        "adjust the dose",
    ],
    "start/stop medication advice": [
        "stop taking",
        "start taking",
        "discontinue medication",
        "begin medication",
    ],
    "medication selection advice": [
        "recommends choosing medication",
        "choose medication",
        "medication selection advice",
        "opencare recommends",
    ],
    "clinical decision support": [
        "clinical decision support",
        "treatment decision support",
    ],
    "real patient data": [
        "real patient data",
        "actual patient data",
    ],
}


class EvidenceLink(BaseModel):
    source_id: str = Field(min_length=1)
    strength: EvidenceStrength
    note: str = Field(min_length=1)


class Person(BaseModel):
    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    synthetic: bool = True
    notes: str = Field(default="")

    @field_validator("synthetic")
    @classmethod
    def person_must_be_synthetic(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Every person must be synthetic in the demo vault.")
        return value


class Family(BaseModel):
    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    synthetic: bool = True

    @field_validator("synthetic")
    @classmethod
    def family_must_be_synthetic(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Family record must be synthetic in the demo vault.")
        return value


class Relationship(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    related_person_id: str = Field(min_length=1)
    relationship_type: RelationshipType


class DocumentSource(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: SourceType
    synthetic: bool = True
    demo_only: bool = True
    description: str = Field(default="")

    @model_validator(mode="after")
    def source_must_be_demo_synthetic(self) -> "DocumentSource":
        if not self.synthetic:
            raise ValueError("Document sources must be synthetic.")
        if not self.demo_only:
            raise ValueError("Document sources must be demo_only.")
        return self


class Condition(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: RecordStatus
    description: str = Field(default="")
    evidence: list[EvidenceLink] = Field(default_factory=list)


class Medication(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: MedicationStatus
    reason_context: str = Field(default="")
    evidence: list[EvidenceLink] = Field(default_factory=list)


class LabResult(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    result_text: str = Field(min_length=1)
    collected_on: str = Field(min_length=1)
    evidence: list[EvidenceLink] = Field(default_factory=list)


class Visit(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    visit_type: str = Field(min_length=1)
    date: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: list[EvidenceLink] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    date: str = Field(min_length=1)
    title: str = Field(min_length=1)
    evidence: list[EvidenceLink] = Field(default_factory=list)


class QuestionThread(BaseModel):
    id: str = Field(min_length=1)
    scope: QuestionScope
    person_id: str | None = None
    status: QuestionStatus
    question: str = Field(min_length=1)
    evidence: list[EvidenceLink] = Field(default_factory=list)


class VaultDataset(BaseModel):
    dataset_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    demo_only: bool = True
    synthetic: bool = True
    family: Family
    people: list[Person] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    document_sources: list[DocumentSource] = Field(default_factory=list)
    conditions: list[Condition] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    visits: list[Visit] = Field(default_factory=list)
    timeline_events: list[TimelineEvent] = Field(default_factory=list)
    question_threads: list[QuestionThread] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dataset(self) -> "VaultDataset":
        if not self.demo_only:
            raise ValueError("Health/Family Vault V1A requires demo_only datasets.")
        if not self.synthetic:
            raise ValueError("Health/Family Vault V1A requires synthetic datasets.")

        people_ids = [person.id for person in self.people]
        source_ids = [source.id for source in self.document_sources]
        self._assert_unique_ids("person", people_ids)
        self._assert_unique_ids("document source", source_ids)
        self._assert_unique_ids(
            "record",
            [
                self.family.id,
                *[relationship.id for relationship in self.relationships],
                *[condition.id for condition in self.conditions],
                *[medication.id for medication in self.medications],
                *[lab.id for lab in self.lab_results],
                *[visit.id for visit in self.visits],
                *[event.id for event in self.timeline_events],
                *[thread.id for thread in self.question_threads],
            ],
        )

        known_people = set(people_ids)
        known_sources = set(source_ids)
        for relationship in self.relationships:
            self._assert_known_person(relationship.person_id, relationship.id, known_people)
            self._assert_known_person(relationship.related_person_id, relationship.id, known_people)

        for condition in self.conditions:
            self._validate_person_record(
                condition.id,
                condition.person_id,
                condition.evidence,
                known_people,
                known_sources,
            )
        for medication in self.medications:
            self._validate_person_record(
                medication.id,
                medication.person_id,
                medication.evidence,
                known_people,
                known_sources,
            )
        for lab_result in self.lab_results:
            self._validate_person_record(
                lab_result.id,
                lab_result.person_id,
                lab_result.evidence,
                known_people,
                known_sources,
            )
        for visit in self.visits:
            self._validate_person_record(
                visit.id,
                visit.person_id,
                visit.evidence,
                known_people,
                known_sources,
            )
        for event in self.timeline_events:
            self._validate_person_record(
                event.id,
                event.person_id,
                event.evidence,
                known_people,
                known_sources,
            )
        for thread in self.question_threads:
            if thread.scope == "person":
                if thread.person_id is None:
                    raise ValueError(f"Question thread {thread.id} must reference a person.")
                self._assert_known_person(thread.person_id, thread.id, known_people)
            if not thread.evidence:
                raise ValueError(f"Question thread {thread.id} is missing provenance.")
            self._assert_known_sources(thread.id, thread.evidence, known_sources)

        self._assert_safe_text(self.model_dump())
        return self

    @staticmethod
    def _assert_unique_ids(label: str, ids: list[str]) -> None:
        seen: set[str] = set()
        for item_id in ids:
            if item_id in seen:
                raise ValueError(f"Duplicate id found in {label} records: {item_id}")
            seen.add(item_id)

    @staticmethod
    def _assert_known_person(person_id: str, record_id: str, known_people: set[str]) -> None:
        if person_id not in known_people:
            raise ValueError(f"Record {record_id} references unknown person: {person_id}")

    @classmethod
    def _validate_person_record(
        cls,
        record_id: str,
        person_id: str,
        evidence: list[EvidenceLink],
        known_people: set[str],
        known_sources: set[str],
    ) -> None:
        cls._assert_known_person(person_id, record_id, known_people)
        if not evidence:
            raise ValueError(f"Record {record_id} is missing provenance.")
        cls._assert_known_sources(record_id, evidence, known_sources)

    @staticmethod
    def _assert_known_sources(
        record_id: str,
        evidence: list[EvidenceLink],
        known_sources: set[str],
    ) -> None:
        for link in evidence:
            if link.source_id not in known_sources:
                raise ValueError(f"Record {record_id} references unknown source: {link.source_id}")

    @classmethod
    def _assert_safe_text(cls, value: object) -> None:
        for text in cls._walk_strings(value):
            normalized = text.lower()
            for reason, patterns in UNSAFE_TEXT_PATTERNS.items():
                for pattern in patterns:
                    if pattern in normalized:
                        raise ValueError(f"unsafe text detected ({reason}): {pattern}")

    @classmethod
    def _walk_strings(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            strings: list[str] = []
            for nested_value in value.values():
                strings.extend(cls._walk_strings(nested_value))
            return strings
        if isinstance(value, list):
            strings = []
            for nested_value in value:
                strings.extend(cls._walk_strings(nested_value))
            return strings
        return []
