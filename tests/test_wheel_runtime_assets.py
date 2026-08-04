import os
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_URL = "https://github.com/KirillNedoboy/open-care-proof-kit"
REVIEWER_QUICKSTART_URLS = (
    f"{REPOSITORY_URL}/blob/main/docs/adr/0001-opencare-product-direction.md",
    f"{REPOSITORY_URL}/blob/main/docs/project-status.md",
)


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
        quickstart = wheel.read("app/assets/docs/reviewer_quickstart.md").decode("utf-8")

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
    for url in REVIEWER_QUICKSTART_URLS:
        assert url in quickstart

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
                    "    for path in ('/health', '/readyz', '/demo/chat', "
                    "'/demo/health-vault', "
                    "'/static/product_core_workspace.css', "
                    "'/static/product_core_workspace.js'):",
                    "        assert client.get(path).status_code == 200, path",
                    "    for path in ('/workspace', '/chat', '/vault'):",
                    "        assert client.get(path).status_code == 401, path",
                    "    quickstart = client.get('/reviewer-quickstart')",
                    "    assert quickstart.status_code == 200",
                    *[f"    assert {url!r} in quickstart.text" for url in REVIEWER_QUICKSTART_URLS],
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
