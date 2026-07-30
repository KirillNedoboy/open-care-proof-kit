import os
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contains_and_uses_runtime_assets_outside_checkout(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
            str(PROJECT_ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel_path = next(wheel_dir.glob("open_care_proof_kit-*.whl"))

    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())

    assert {
        "app/static/product_core_workspace.css",
        "app/static/product_core_workspace.js",
        "app/templates/product_core_workspace.html",
        "app/assets/data/demo_patients/demo_patient_a.json",
        "app/assets/data/demo_patients/demo_family_vault.json",
        "app/assets/data/demo_patients/demo_patient_a_23andme.txt",
        "app/assets/data/evidence_packs/pgx_demo_pack.json",
        "app/assets/docs/reviewer_quickstart.md",
        "app/assets/docs/health_vault/family-vault-manifest.json",
    }.issubset(names)

    install_dir = tmp_path / "installed"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(install_dir),
            str(wheel_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    runtime_dir = tmp_path / "runtime"
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(install_dir),
            "OPENCARE_PRODUCT_DB_PATH": str(runtime_dir / "opencare.sqlite3"),
            "OPENCARE_SOURCE_DIR": str(runtime_dir / "sources"),
        }
    )
    installed_runtime = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "from pathlib import Path",
                    "from fastapi.testclient import TestClient",
                    "from app.main import APP_DIR, app",
                    "assert APP_DIR.is_relative_to(Path.cwd() / 'installed')",
                    "with TestClient(app) as client:",
                    "    for path in ('/health', '/readyz', '/workspace', '/chat', "
                    "'/static/product_core_workspace.css', "
                    "'/static/product_core_workspace.js'):",
                    "        assert client.get(path).status_code == 200, path",
                ]
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=environment,
    )
    assert installed_runtime.returncode == 0, installed_runtime.stderr
