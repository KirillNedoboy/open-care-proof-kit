import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_assets_are_external_and_avoid_browser_persistence_or_unsafe_html() -> None:
    template = (ROOT / "app" / "templates" / "product_core_workspace.html").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "app" / "static" / "product_core_workspace.js").read_text(
        encoding="utf-8"
    )

    assert "onclick=" not in template
    assert "<script>" not in template
    for forbidden in (
        "localStorage",
        "sessionStorage",
        "indexedDB",
        "serviceWorker",
        "innerHTML",
        "insertAdjacentHTML",
        "document.write",
        "console.",
        "window.prompt",
        "window.location",
        "URLSearchParams",
    ):
        assert forbidden not in script
    assert "person-id" not in template
    assert "person-selector" in template
    assert "create-profile-form" in template
    assert "edit-profile" in template
    assert "Create correction" in script
    assert "Save correction" in script
    assert "trigger.focus()" in script
    assert "visit-form" in script
    assert "visit-question-form" in script
    assert "Move question up" in script
    assert "Move question down" in script
    assert "initialize-brief" in script
    assert "brief-preparation-notes" in script
    assert "current:export" in script
    assert "open-vault-export" in script
    assert "requestBlob" in script
    assert "confirm-vault-export" in script
    assert "visit-briefs:generate" not in script
    assert "probePersonList" not in script
    assert "AbortController" in script
    assert "shouldApplyResponse" in script
    assert "workspace-capabilities" in script
    assert "include_inactive=true" in script
    assert "/sources/" in script
    assert "opencare-person-vault-v2.zip" not in script
    assert script.count("opencare-person-vault-v3.zip") == 1


def test_workspace_static_assets_exist() -> None:
    for relative_path in (
        "app/static/product_core_workspace.css",
        "app/static/product_core_workspace.js",
        "app/static/workspace_state.js",
    ):
        assert (ROOT / relative_path).is_file()


def test_workspace_uses_session_csrf_and_server_side_active_person() -> None:
    script = (ROOT / "app" / "static" / "product_core_workspace.js").read_text(
        encoding="utf-8"
    )

    assert "X-OpenCare-CSRF" in script
    assert "/api/family-access/v1/active-person" in script
    assert "confirm_owner_assignment: byId(\"create-owner-confirmation\").checked" in script
    assert "opencare-person-vault-v3.zip" in script


def test_workspace_generation_helper_rejects_stale_person_responses() -> None:
    state_script = ROOT / "app" / "static" / "workspace_state.js"
    program = (
        f'require({str(state_script)!r});'
        "const helper=globalThis.OpenCareWorkspaceState;"
        "if(!helper.shouldApplyResponse(4,4))process.exit(1);"
        "if(helper.shouldApplyResponse(3,4))process.exit(2);"
        "if(helper.shouldApplyResponse('4',4))process.exit(3);"
    )

    result = subprocess.run(
        ["node", "-e", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_workspace_state_helpers_enforce_download_and_visit_contracts() -> None:
    state_script = ROOT / "app" / "static" / "workspace_state.js"
    program = (
        f"require({str(state_script)!r});"
        "const helper=globalThis.OpenCareWorkspaceState;"
        "const unsafe=helper.sanitizeDownloadFilename("
        "'..\\\\\\\\folder/file\\x01name','fallback.zip');"
        "if(/[\\\\\\\\/\\x00-\\x1f\\x7f]/.test(unsafe)||unsafe.startsWith('.')||!unsafe.endsWith('.zip'))process.exit(1);"
        "if(helper.sanitizeDownloadFilename('', 'fallback.zip')!=='fallback.zip')process.exit(2);"
        "if(helper.sanitizeDownloadFilename('vault','fallback.zip')!=='vault.zip')process.exit(3);"
        "if(helper.contentDispositionFilename("
        "'attachment; filename=\"server-vault.zip\"')"
        "!=='server-vault.zip')process.exit(4);"
        "if(helper.contentDispositionFilename("
        "\"attachment; filename*=UTF-8''family%20vault.zip\")"
        "!=='family vault.zip')process.exit(5);"
        "const visits=helper.sortVisits(["
        "{visit_id:'z',title:'Zulu',scheduled_date:null},"
        "{visit_id:'b',title:'Beta',scheduled_date:'2026-09-01'},"
        "{visit_id:'a',title:'Alpha',scheduled_date:'2026-09-01'}]);"
        "if(visits.map(item=>item.visit_id).join(',')!=='a,b,z')process.exit(6);"
    )

    result = subprocess.run(
        ["node", "-e", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_workspace_script_defends_exact_frontend_labels_and_provenance() -> None:
    script = (ROOT / "app" / "static" / "product_core_workspace.js").read_text(
        encoding="utf-8"
    )

    for label in (
        "Confirm record",
        "Reject candidate",
        "Mark unsupported by source",
        "Create correction",
        "Medication record confirmed",
        "Condition record confirmed",
        "Lab record confirmed",
        "Record superseded by reviewed correction",
        "Recorded in OpenCare",
        "Onset date (as recorded)",
        "Observed date (as reported)",
        "Current",
        "Evidence changed since this revision",
        "Selected record or source changed",
        "Revision unavailable",
        "Source & provenance",
        "Source type:",
        "Created:",
        "SHA-256:",
        "Integrity verified",
        "Correction lineage:",
    ):
        assert label in script
