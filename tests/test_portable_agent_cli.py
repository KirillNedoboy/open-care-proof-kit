import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.agent.context import build_agent_context
from app.agent.policy import classify_question
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


def test_portable_evidence_contract_rejects_unbound_and_noncanonical_answers() -> None:
    context = demo_portable_context()
    answer = valid_answer()

    assert (
        validate_portable_answer(context, answer, "Which medications are recorded?").valid is True
    )
    with_extra = {**answer, "extra": "not allowed"}
    try:
        parse_portable_answer(with_extra)
    except ValueError as exc:
        assert str(exc) == "invalid_answer_schema"
    else:
        raise AssertionError("unknown answer fields must be rejected")

    zero_claims = valid_answer()
    zero_claims["evidence_claims"] = []
    assert (
        validate_portable_answer(
            context, zero_claims, "Which medications are recorded?"
        ).reason_code
        == "answer_not_canonical"
    )

    unrelated_source = valid_answer()
    unrelated_source["evidence_claims"] = [
        {
            **valid_answer()["evidence_claims"][0],
            "source_id": "source-primary-care-note-2026-01",
        }
    ]
    unrelated_source["citations"] = [
        {
            **valid_answer()["citations"][0],
            "source_id": "source-primary-care-note-2026-01",
        }
    ]
    assert (
        validate_portable_answer(
            context, unrelated_source, "Which medications are recorded?"
        ).reason_code
        == "source_not_linked_to_context_item"
    )

    wrong_context_item = valid_answer()
    recorded_without_source_item = next(
        item for item in context.context_items if item.evidence_status != "source_backed"
    )
    wrong_context_item["evidence_claims"] = [
        {
            **valid_answer()["evidence_claims"][0],
            "context_item_id": recorded_without_source_item.item_id,
        }
    ]
    assert (
        validate_portable_answer(
            context, wrong_context_item, "Which medications are recorded?"
        ).reason_code
        == "evidence_not_source_backed"
    )

    unknown_context_item = valid_answer()
    unknown_context_item["evidence_claims"] = [
        {**valid_answer()["evidence_claims"][0], "context_item_id": "not-in-context"}
    ]
    assert (
        validate_portable_answer(
            context, unknown_context_item, "Which medications are recorded?"
        ).reason_code
        == "context_item_not_found"
    )

    modified_evidence = valid_answer()
    modified_evidence["evidence_claims"] = [
        {**valid_answer()["evidence_claims"][0], "evidence_text": "Modified evidence."}
    ]
    assert (
        validate_portable_answer(
            context, modified_evidence, "Which medications are recorded?"
        ).reason_code
        == "evidence_text_mismatch"
    )

    extra_prose = valid_answer()
    extra_prose["answer"] = f"{extra_prose['answer']}\nUnsupported additional prose."
    assert (
        validate_portable_answer(
            context, extra_prose, "Which medications are recorded?"
        ).reason_code
        == "answer_not_canonical"
    )

    missing_citation = valid_answer()
    missing_citation["citations"] = []
    assert (
        validate_portable_answer(
            context, missing_citation, "Which medications are recorded?"
        ).reason_code
        == "answer_not_canonical"
    )

    extra_citation = valid_answer()
    extra_citation["citations"] = [
        *valid_answer()["citations"],
        {
            "source_id": "source-primary-care-note-2026-01",
            "claim": "Unrelated context.",
        },
    ]
    assert (
        validate_portable_answer(
            context, extra_citation, "Which medications are recorded?"
        ).reason_code
        == "answer_not_canonical"
    )


@pytest.mark.parametrize(
    ("question", "reason_code"),
    [
        ("What diagnosis do I have?", "policy_status_mismatch"),
        ("What treatment should I start?", "policy_status_mismatch"),
        ("Should I increase my dosage?", "policy_status_mismatch"),
        ("I have chest pain and cannot breathe", "policy_status_mismatch"),
    ],
)
def test_portable_validation_rejects_answered_policy_questions(
    question: str,
    reason_code: str,
) -> None:
    result = validate_portable_answer(demo_portable_context(), valid_answer(), question)
    assert result.reason_code == reason_code


@pytest.mark.parametrize(
    "question",
    [
        "What diagnosis do I have?",
        "I have chest pain and cannot breathe",
    ],
)
def test_portable_validation_accepts_fixed_policy_refusals(question: str) -> None:
    policy = classify_question(question)
    answer = {
        "status": "refused",
        "answer": policy.response_text,
        "citations": [],
        "unknowns": [],
        "doctor_questions": [],
        "boundary_notices": ["OpenCare does not provide diagnosis or treatment recommendations."],
        "evidence_claims": [],
    }

    assert validate_portable_answer(demo_portable_context(), answer, question).valid is True


def test_portable_validation_requires_question_without_context_disclosure() -> None:
    result = validate_portable_answer(demo_portable_context(), valid_answer(), None)

    assert result.reason_code == "question_required"
    assert "sertraline" not in (result.reason_code or "")


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
    assert json.loads(capsys.readouterr().out)["reason_codes"] == [
        "source_not_linked_to_context_item"
    ]

    assert (
        cli.main(
            [
                "validate-answer",
                "--context",
                str(context_path),
                "--answer",
                str(answer_path),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["reason_codes"] == ["question_required"]


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
    assert medication["evidence_claims"]
    assert medication["evidence_claims"][0]["context_item_id"] == "medication-alex-sertraline"
    assert medication["evidence_claims"][0]["source_id"] == "source-medication-list-2026-03"
    assert medication["answer"] == "\n".join(
        claim["evidence_text"] for claim in medication["evidence_claims"]
    )

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
    refused = json.loads(capsys.readouterr().out)
    assert refused["status"] == "refused"
    assert refused["evidence_claims"] == []
