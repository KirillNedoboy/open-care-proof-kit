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
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert "indexedDB" not in script
    assert "serviceWorker" not in script
    assert "innerHTML" not in script
    assert "insertAdjacentHTML" not in script
    assert "document.write" not in script
    assert "console." not in script
    assert "window.prompt" not in script
    assert "person-id" not in template
    assert "person-selector" in template
    assert "create-profile-form" in template
    assert "edit-profile" in template
    assert "window.location" not in script
    assert "URLSearchParams" not in script
    assert "Correct medication entry" in script
    assert "Save correction" in script
    assert "Cancel" in script
    assert "name.focus()" in script
    assert "trigger.focus()" in script
    assert "visit-form" in script
    assert "visit-question-form" in script
    assert "Move question up" in script
    assert "Move question down" in script
    assert "initialize-brief" in script
    assert "brief-preparation-notes" in script
    assert "current:export" in script
    assert "visit-briefs:generate" not in script


def test_workspace_static_assets_exist() -> None:
    css = ROOT / "app" / "static" / "product_core_workspace.css"
    script = ROOT / "app" / "static" / "product_core_workspace.js"

    assert css.is_file()
    assert script.is_file()
