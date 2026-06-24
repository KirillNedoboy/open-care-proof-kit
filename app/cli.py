import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from app.demo_pipeline import build_demo_briefing


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_report = subparsers.add_parser("demo-report")
    demo_report.add_argument("--drug", default="sertraline")
    demo_report.add_argument("--out-dir", type=Path, default=Path("reports"))

    return parser


def write_demo_report_files(*, drug: str, out_dir: Path) -> tuple[Path, Path]:
    result = build_demo_briefing(drug)
    if not result.policy_passed:
        raise SystemExit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"demo-{drug}-briefing.md"
    audit_path = out_dir / f"demo-{drug}-audit.json"
    audit = dict(result.audit)
    audit["generated_files"] = {
        "report_markdown": str(report_path),
        "audit_json": str(audit_path),
    }

    report_path.write_text(result.report_markdown, encoding="utf-8")
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    return report_path, audit_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "demo-report":
        try:
            report_path, audit_path = write_demo_report_files(
                drug=args.drug,
                out_dir=args.out_dir,
            )
        except SystemExit as exc:
            if isinstance(exc.code, int):
                return exc.code
            return 1

        print(f"Wrote {report_path}")
        print(f"Wrote {audit_path}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
