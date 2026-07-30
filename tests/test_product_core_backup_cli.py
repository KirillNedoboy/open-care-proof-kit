from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.product_core import backup_cli
from app.product_core.models import Person
from app.product_core.services import SourceService
from app.product_core.sqlite import SQLiteDatabase


def test_backup_cli_uses_explicit_paths_and_verify_is_offline(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    now = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Synthetic profile",
                created_at=now,
                updated_at=now,
                is_active=True,
            )
        )
    sources = SourceService(database, tmp_path / "active-sources")
    source = sources.register_plain_text("person-1", "synthetic source")
    destination = tmp_path / "backup"

    assert (
        backup_cli.main(
            [
                "backup",
                "--database",
                str(database.path),
                "--source-dir",
                str(sources.store.source_dir),
                "--destination",
                str(destination),
            ]
        )
        == 0
    )
    backup_output = json.loads(capsys.readouterr().out)
    assert backup_output["status"] == "valid"
    assert "Synthetic profile" not in json.dumps(backup_output)

    database.path.unlink()
    (sources.store.source_dir / source.relative_path).unlink()
    monkeypatch.setattr(backup_cli, "load_settings", lambda: (_ for _ in ()).throw(AssertionError))
    assert backup_cli.main(["verify", "--backup", str(destination)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid"


def test_backup_cli_uses_settings_only_for_missing_backup_paths(
    tmp_path: Path,
    capsys,
    monkeypatch,
) -> None:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    now = datetime(2026, 7, 30, 12, tzinfo=UTC)
    with database.uow() as uow:
        uow.people.insert(
            Person(
                person_id="person-1",
                display_name="Synthetic profile",
                created_at=now,
                updated_at=now,
                is_active=True,
            )
        )
    sources = SourceService(database, tmp_path / "active-sources")
    sources.register_plain_text("person-1", "synthetic source")
    monkeypatch.setattr(
        backup_cli,
        "load_settings",
        lambda: SimpleNamespace(
            product_db_path=database.path,
            source_dir=sources.store.source_dir,
        ),
    )

    assert backup_cli.main(["backup", "--destination", str(tmp_path / "backup")]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "valid"
    assert backup_cli.main(["verify"]) == 2


def test_backup_cli_module_backup_and_verify_smoke(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "active.sqlite3")
    database.migrate()
    sources = SourceService(database, tmp_path / "active-sources")
    destination = tmp_path / "backup"
    root = Path(__file__).resolve().parents[1]
    backup = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.product_core.backup_cli",
            "backup",
            "--database",
            str(database.path),
            "--source-dir",
            str(sources.store.source_dir),
            "--destination",
            str(destination),
        ],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    assert backup.returncode == 0
    assert json.loads(backup.stdout)["status"] == "valid"

    verify = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.product_core.backup_cli",
            "verify",
            "--backup",
            str(destination),
        ],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    assert verify.returncode == 0
    assert json.loads(verify.stdout)["status"] == "valid"
