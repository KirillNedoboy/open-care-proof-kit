from __future__ import annotations

from html import unescape
from pathlib import Path

from fastapi.testclient import TestClient

from app.family_access.policy import (
    CAREGIVER_OPTIONAL_SCOPES,
    CAREGIVER_OPTIONAL_SCOPES_V1,
    CAREGIVER_OPTIONAL_SCOPES_V2,
    CAREGIVER_OPTIONAL_SCOPES_V3,
    OWNER_SCOPES,
)
from app.ui_localization import TRANSLATIONS

ROOT = Path(__file__).resolve().parents[1]

SCOPE_LABELS = {
    "person.read": ("View Person profile", "Просмотр профиля пользователя"),
    "person.update": ("Edit Person profile", "Изменение профиля пользователя"),
    "source.read": ("View sources", "Просмотр источников"),
    "source.write": ("Add sources", "Добавление источников"),
    "document.read": ("View documents", "Просмотр документов"),
    "document.write": ("Manage documents", "Управление документами"),
    "candidate.read": ("View review items", "Просмотр записей на проверку"),
    "candidate.review": (
        "Review candidate records",
        "Проверка предложенных записей",
    ),
    "medication.read": ("View medications", "Просмотр лекарств"),
    "medication.write": ("Manage medications", "Управление лекарствами"),
    "condition.read": (
        "View recorded conditions",
        "Просмотр записанных состояний",
    ),
    "condition.write": (
        "Manage recorded conditions",
        "Управление записанными состояниями",
    ),
    "lab.read": ("View lab records", "Просмотр анализов"),
    "lab.write": ("Manage lab records", "Управление анализами"),
    "timeline.read": ("View timeline", "Просмотр хронологии"),
    "visit.read": ("View visits", "Просмотр визитов"),
    "visit.write": ("Manage visits", "Управление визитами"),
    "brief.read": ("View Visit Briefs", "Просмотр сводок визитов"),
    "brief.write": ("Manage Visit Briefs", "Управление сводками визитов"),
    "brief.export": ("Export Visit Briefs", "Экспорт сводок визитов"),
    "vault.export": ("Export Person data", "Экспорт данных пользователя"),
    "relationship.read": (
        "View family relationships",
        "Просмотр семейных связей",
    ),
    "relationship.manage": (
        "Manage family relationships",
        "Управление семейными связями",
    ),
    "access.read": ("View Family Access", "Просмотр семейного доступа"),
    "access.manage": ("Manage Family Access", "Управление семейным доступом"),
    "chat.use": ("Use OpenCare chat", "Использование чата OpenCare"),
}

SCOPE_GROUP_LABELS = {
    "family.scope_group.health": ("Health data", "Данные о здоровье"),
    "family.scope_group.sources_documents": (
        "Sources & documents",
        "Источники и документы",
    ),
    "family.scope_group.family": (
        "Family administration",
        "Управление семейным доступом",
    ),
    "family.scope_group.export": ("Exports", "Экспорт"),
    "family.scope_group.chat": ("OpenCare chat", "Чат OpenCare"),
}


def test_family_workspace_renders_localized_human_facing_chrome(
    product_core_client: TestClient,
) -> None:
    cleared = product_core_client.put(
        "/api/family-access/v1/active-person",
        json={"person_id": None},
    )
    assert cleared.status_code == 204

    english = unescape(product_core_client.get("/family-access").text)
    english_chrome = (
        "Family & Access",
        "Access for Person",
        "People with access",
        "Invite someone",
        "Your account",
        "Advanced",
    )
    for label in english_chrome:
        assert label in english

    product_core_client.cookies.set("opencare_locale", "ru", path="/")
    russian_response = product_core_client.get("/family-access")
    assert russian_response.status_code == 200
    russian = unescape(russian_response.text)
    for label in (
        "Семья и доступ",
        "Доступ к пользователю",
        "Пользователи с доступом",
        "Пригласить пользователя",
        "Ваш аккаунт",
        "Расширенные настройки",
    ):
        assert label in russian
    for label in english_chrome:
        assert label not in russian


def test_family_person_context_and_read_only_access_fail_closed(
    product_core_client: TestClient,
) -> None:
    people = product_core_client.get("/api/product-core/v1/people")
    assert people.status_code == 200
    assert {person["person_id"] for person in people.json()["people"]} == {
        "person-1",
        "person-2",
    }

    selected = product_core_client.put(
        "/api/family-access/v1/active-person",
        json={"person_id": "person-1"},
    )
    assert selected.status_code == 204
    unavailable = product_core_client.put(
        "/api/family-access/v1/active-person",
        json={"person_id": "person-not-assigned"},
    )
    assert unavailable.status_code == 404
    assert product_core_client.get("/api/family-access/v1/me").json()[
        "active_person_id"
    ] == "person-1"

    invitation = product_core_client.post(
        "/api/family-access/v1/people/person-1/invitations",
        json={
            "role": "caregiver",
            "optional_scopes": [],
            "expires_at": "2026-07-27T12:00:00+00:00",
            "confirm_full_owner_access": False,
        },
    )
    assert invitation.status_code == 201, invitation.text

    product_core_client.cookies.clear()
    registered = product_core_client.post(
        "/api/family-access/v1/invite/register",
        headers={"origin": "http://testserver"},
        json={
            "secret": invitation.json()["secret"],
            "username": "r54-caregiver",
            "display_name": "R5.4 caregiver",
            "password": "synthetic caregiver password",
            "confirm_full_owner_access": False,
        },
    )
    assert registered.status_code == 201, registered.text

    caregiver_people = product_core_client.get("/api/product-core/v1/people")
    assert caregiver_people.status_code == 200
    assert [
        person["person_id"] for person in caregiver_people.json()["people"]
    ] == ["person-1"]

    assignments = product_core_client.get(
        "/api/family-access/v1/people/person-1/access-assignments"
    )
    assert assignments.status_code == 404


def test_family_scope_presentation_preserves_machine_boundaries(
    product_core_client: TestClient,
) -> None:
    script = (ROOT / "app" / "static" / "family_access_workspace.js").read_text(
        encoding="utf-8"
    )
    presented_scopes = OWNER_SCOPES | CAREGIVER_OPTIONAL_SCOPES
    assert presented_scopes == set(SCOPE_LABELS)
    for scope, (english_label, russian_label) in SCOPE_LABELS.items():
        translation_key = f"family.scope.{scope.replace('.', '_')}"
        assert f'"{scope}"' in script
        assert script.count(translation_key) == 1
        assert TRANSLATIONS["en"][translation_key] == english_label
        assert TRANSLATIONS["ru"][translation_key] == russian_label

    for key, (english_label, russian_label) in SCOPE_GROUP_LABELS.items():
        assert key in script
        assert TRANSLATIONS["en"][key] == english_label
        assert TRANSLATIONS["ru"][key] == russian_label

    assert "genetics.read" not in script
    assert "genetics.write" not in script
    assert not any(scope.startswith("genetics.") for scope in presented_scopes)

    genetics_invitation = product_core_client.post(
        "/api/family-access/v1/people/person-1/invitations",
        json={
            "role": "caregiver",
            "optional_scopes": ["genetics.read"],
            "expires_at": "2026-07-27T12:00:00+00:00",
            "confirm_full_owner_access": False,
        },
    )
    assert genetics_invitation.status_code == 422

    v1 = {
        "source.write",
        "candidate.review",
        "medication.write",
        "visit.write",
        "brief.write",
        "brief.export",
        "vault.export",
    }
    assert v1 == CAREGIVER_OPTIONAL_SCOPES_V1
    assert (v1 | {
        "condition.write",
        "lab.write",
    }) == CAREGIVER_OPTIONAL_SCOPES_V2
    assert (v1 | {
        "condition.write",
        "lab.write",
        "document.write",
    }) == CAREGIVER_OPTIONAL_SCOPES_V3


def test_family_invitation_account_and_advanced_security_contracts(
    product_core_client: TestClient,
) -> None:
    template = (
        ROOT / "app" / "templates" / "family_access_workspace.html"
    ).read_text(encoding="utf-8")
    script = (ROOT / "app" / "static" / "family_access_workspace.js").read_text(
        encoding="utf-8"
    )

    invitation_panel = template.index('id="issued-invitation"')
    assert "hidden" in template[invitation_panel : invitation_panel + 160]
    assert 'id="issued-invitation-code"' in template
    assert 'id="clear-invitation-code"' in template
    assert 'tabindex="-1"' in template[invitation_panel : invitation_panel + 500]

    for forbidden in (
        "URLSearchParams",
        "location.search",
        "localStorage",
        "sessionStorage",
        "innerHTML",
        "insertAdjacentHTML",
        "console.",
    ):
        assert forbidden not in script
    assert '"/api/family-access/v1/invite/preview"' not in script
    assert "/invitations`" in script
    assert "body: JSON.stringify" in script

    current_password = template[template.index('id="current-password"') :]
    current_password = current_password[: current_password.index(">")]
    assert 'type="password"' in current_password
    assert 'autocomplete="current-password"' in current_password
    assert " value=" not in current_password

    new_password = template[template.index('id="new-password"') :]
    new_password = new_password[: new_password.index(">")]
    assert 'type="password"' in new_password
    assert 'autocomplete="new-password"' in new_password
    assert 'minlength="12"' in new_password
    assert 'maxlength="1024"' in new_password
    assert " value=" not in new_password

    rejected_password_change = product_core_client.post(
        "/api/family-access/v1/password:change",
        headers={
            "origin": "http://testserver",
            "x-opencare-csrf": "invalid-csrf-token",
        },
        json={
            "current_password": "correct horse battery",
            "new_password": "replacement password value",
        },
    )
    assert rejected_password_change.status_code == 403

    advanced = template.index('<details id="family-access-advanced"')
    assert "open" not in template[advanced : template.index(">", advanced)]
    for ordinary_id in (
        'id="family-person-context"',
        'id="people-with-access"',
        'id="invite-someone"',
        'id="account-settings"',
    ):
        assert template.index(ordinary_id) < advanced
    advanced_markup = template[advanced:]
    for technical_area in (
        'id="grant-access-form"',
        'id="actor-list"',
        'id="consent-list"',
        'id="access-audit-list"',
        'id="create-family-form"',
    ):
        assert technical_area in advanced_markup
    for technical_key in (
        "family.actor_id",
        "family.person_id",
        "family.assignment_id",
        "family.raw_scopes",
    ):
        assert technical_key in template or technical_key in script
