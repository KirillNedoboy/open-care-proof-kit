import json
from datetime import UTC, datetime
from pathlib import Path

from app.agent.context import build_agent_context
from app.agent.portable import (
    ANSWER_FIELDS,
    PortableHealthContext,
    export_portable_context,
    parse_portable_answer,
    validate_portable_answer,
)
from app.config import load_settings
from app.health_vault.runtime_loader import load_active_vault


def demo_portable_context() -> PortableHealthContext:
    return export_portable_context(
        build_agent_context(load_active_vault(load_settings({}))),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def valid_answer() -> dict[str, object]:
    evidence_text = (
        "sertraline | current | Medication question recorded for clinician-review preparation."
    )
    return {
        "status": "answered",
        "answer": evidence_text,
        "citations": [
            {
                "source_id": "source-medication-list-2026-03",
                "claim": evidence_text,
            }
        ],
        "unknowns": [],
        "doctor_questions": [],
        "boundary_notices": ["This is not a treatment recommendation."],
        "evidence_claims": [
            {
                "context_item_id": "medication-alex-sertraline",
                "source_id": "source-medication-list-2026-03",
                "evidence_text": evidence_text,
            }
        ],
    }


def test_skill_package_and_schemas_are_present_and_parseable() -> None:
    package = Path("skills/opencare-health-agent")

    for name in [
        "SKILL.md",
        "README.md",
        "install.md",
        "context.schema.json",
        "answer.schema.json",
        "examples.md",
    ]:
        assert (package / name).is_file()

    context_schema = json.loads((package / "context.schema.json").read_text(encoding="utf-8"))
    answer_schema = json.loads((package / "answer.schema.json").read_text(encoding="utf-8"))
    assert context_schema["$schema"].endswith("2020-12/schema")
    assert set(answer_schema["required"]) == ANSWER_FIELDS
    assert answer_schema["additionalProperties"] is False
    assert "Tula" not in (package / "SKILL.md").read_text(encoding="utf-8")


def test_portable_context_export_is_safe_deterministic_and_preserves_medication_source() -> None:
    first = demo_portable_context()
    second = demo_portable_context()

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert "source-medication-list-2026-03" in {
        source_id for item in first.medications for source_id in item.source_ids
    }
    dumped = first.model_dump_json()
    assert "OPENCARE_" not in dumped
    assert "C:\\" not in dumped
    assert "/opt/" not in dumped


def test_answer_contract_rejects_unknown_fields_and_unknown_citations() -> None:
    context = demo_portable_context()
    answer = valid_answer()

    assert validate_portable_answer(context, answer, "Which medications are recorded?").valid is True
    with_extra = {**answer, "extra": "not allowed"}
    try:
        parse_portable_answer(with_extra)
    except ValueError as exc:
        assert str(exc) == "invalid_answer_schema"
    else:
        raise AssertionError("unknown answer fields must be rejected")

    answer["citations"] = [{"source_id": "not-in-context", "claim": "Unsupported."}]
    assert (
        validate_portable_answer(context, answer, "Which medications are recorded?").reason_code
        == "answer_not_canonical"
    )


def test_portable_validation_rejects_diagnosis_treatment_and_dosage_change_advice() -> None:
    context = demo_portable_context()

    for unsafe_text in [
        "You have a diagnosis.",
        "I recommend treatment.",
        "You should increase the dosage.",
    ]:
        answer = valid_answer()
        answer["answer"] = unsafe_text
        assert (
            validate_portable_answer(context, answer, "Which medications are recorded?").reason_code
            == "answer_not_canonical"
        )


def test_cli_exports_and_validates_portable_answers(
    tmp_path: Path,
    capsys,
) -> None:
    from app.agent import cli

    context_path = tmp_path / "context.json"
    answer_path = tmp_path / "answer.json"
    answer_path.write_text(json.dumps(valid_answer()), encoding="utf-8")

    assert (
        cli.main(
            ["export-context", "--vault-source", "demo", "--output", str(context_path)]
        )
        == 0
    )
    assert PortableHealthContext.model_validate_json(context_path.read_text(encoding="utf-8"))
    assert (
        cli.main(
            [
                "validate-answer",
                "--context",
                str(context_path),
                "--answer",
                str(answer_path),
                "--question",
                "Which medications are recorded?",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["valid"] is True

    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(
        json.dumps(
            {
                **valid_answer(),
                "citations": [{"source_id": "bad", "claim": "bad"}],
                "evidence_claims": [
                    {
                        **valid_answer()["evidence_claims"][0],
                        "source_id": "bad",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert (
        cli.main(
            [
                "validate-answer",
                "--context",
                str(context_path),
                "--answer",
                str(invalid_path),
                "--question",
                "Which medications are recorded?",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["reason_codes"] == ["invalid_evidence_binding"]


def test_cli_rejects_unsafe_answer_and_demo_ask_preserves_guardrails(capsys) -> None:
    from app.agent import cli

    answer = cli.main(
        [
            "demo-ask",
            "--vault-source",
            "demo",
            "--question",
            "Which medications are recorded in this vault?",
        ]
    )
    assert answer == 0
    medication = json.loads(capsys.readouterr().out)
    assert medication["status"] == "answered"
    assert medication["citations"][0]["source_id"] == "source-medication-list-2026-03"

    assert (
        cli.main(
            [
                "demo-ask",
                "--vault-source",
                "demo",
                "--question",
                "Should I increase my dosage?",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "refused"
