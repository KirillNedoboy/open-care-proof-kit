import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.agent.context import build_agent_context
from app.agent.models import AgentContext
from app.agent.portable import (
    PortableHealthContext,
    export_portable_context,
    parse_portable_answer,
    validate_portable_answer,
)
from app.agent.service import GuardedChatService
from app.config import load_settings
from app.health_vault.runtime_loader import load_active_vault


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.agent.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_context = subparsers.add_parser("export-context")
    export_context.add_argument("--vault-source", choices=("demo", "local_file"), required=True)
    export_context.add_argument("--output", type=Path)

    validate_answer = subparsers.add_parser("validate-answer")
    validate_answer.add_argument("--context", type=Path, required=True)
    validate_answer.add_argument("--answer", type=Path, required=True)
    validate_answer.add_argument("--question", required=True)

    demo_ask = subparsers.add_parser("demo-ask")
    demo_ask.add_argument("--vault-source", choices=("demo", "local_file"), default="demo")
    demo_ask.add_argument("--question", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export-context":
        return _export_context(args.vault_source, args.output)
    if args.command == "validate-answer":
        return _validate_answer(args.context, args.answer, args.question)
    if args.command == "demo-ask":
        return _demo_ask(args.vault_source, args.question)
    return 2


def _export_context(vault_source: str, output: Path | None) -> int:
    try:
        context = export_portable_context(_load_context(vault_source))
    except (OSError, ValueError, ValidationError):
        return _print_result(False, ["context_export_failed"])
    rendered = json.dumps(context.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    if output is None:
        print(rendered, end="")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return 0


def _validate_answer(context_path: Path, answer_path: Path, question: str) -> int:
    try:
        context = PortableHealthContext.model_validate_json(
            context_path.read_text(encoding="utf-8-sig")
        )
    except (OSError, ValidationError, ValueError):
        return _print_result(False, ["invalid_context_schema"])
    try:
        answer_payload: Any = json.loads(answer_path.read_text(encoding="utf-8-sig"))
        answer = parse_portable_answer(answer_payload)
        result = validate_portable_answer(context, answer.model_dump(mode="json"), question)
    except (OSError, ValidationError, ValueError, json.JSONDecodeError):
        return _print_result(False, ["invalid_answer_schema"])
    if not result.valid:
        return _print_result(False, [result.reason_code or "validation_failed"])
    return _print_result(True, [])


def _demo_ask(vault_source: str, question: str) -> int:
    if vault_source != "demo":
        return _print_result(False, ["demo_mode_required"])
    try:
        answer = GuardedChatService.for_settings(load_settings({})).answer(question)
    except (ValueError, ValidationError):
        return _print_result(False, ["demo_answer_failed"])
    print(json.dumps(answer.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def _load_context(vault_source: str) -> AgentContext:
    settings = load_settings({}) if vault_source == "demo" else load_settings()
    if settings.vault_source != vault_source:
        raise ValueError("vault_source_mismatch")
    return build_agent_context(load_active_vault(settings))


def _print_result(valid: bool, reason_codes: list[str]) -> int:
    print(
        json.dumps(
            {
                "valid": valid,
                "status": "accepted" if valid else "rejected",
                "reason_codes": reason_codes,
            },
            sort_keys=True,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
