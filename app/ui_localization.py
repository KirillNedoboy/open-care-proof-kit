from typing import Final, Literal

from fastapi import Request

Locale = Literal["en", "ru"]

SUPPORTED_LOCALES: Final[tuple[Locale, ...]] = ("en", "ru")
DEFAULT_LOCALE: Final[Locale] = "en"
LOCALE_COOKIE_NAME: Final = "opencare_locale"

TRANSLATIONS: Final[dict[Locale, dict[str, str]]] = {
    "en": {
        "app.name": "OpenCare",
        "page.workspace_title": "OpenCare Health Workspace",
        "page.genetics_title": "OpenCare Genetics Workspace",
        "page.vault_title": "Private Person vault · OpenCare",
        "page.family_title": "Family and access · OpenCare",
        "nav.overview": "Overview",
        "nav.health": "Health",
        "nav.workspace": "Workspace",
        "nav.documents": "Documents",
        "nav.activity": "Activity",
        "nav.chat": "Chat",
        "nav.genetics": "Genetics",
        "nav.vault": "Vault",
        "nav.family": "Family & access",
        "nav.family_access": "Family & access",
        "nav.settings": "Settings",
        "shell.primary_navigation": "Primary navigation",
        "shell.open_navigation": "Open navigation",
        "shell.close_navigation": "Close navigation",
        "shell.skip_to_content": "Skip to content",
        "shell.account": "Account",
        "shell.person": "Person",
        "shell.no_person_selected": "No person selected",
        "shell.language": "Language",
        "locale.en": "English",
        "locale.ru": "Russian",
        "locale.current": "Current language",
        "person.label": "Person",
        "person.selected": "Selected person",
        "person.no_selection": "No person selected",
        "person.switch": "Switch person",
        "person.choose": "Choose a person",
        "account.label": "Account",
        "account.menu": "Account menu",
        "account.profile": "Profile",
        "account.signed_in_as": "Signed in as",
        "status.loading": "Loading…",
        "status.ready": "Ready",
        "status.error": "Something went wrong",
        "status.unavailable": "Unavailable",
        "status.saving": "Saving…",
        "status.saved": "Saved",
        "action.save": "Save",
        "action.cancel": "Cancel",
        "action.close": "Close",
        "action.retry": "Try again",
        "action.sign_out": "Sign out",
        "action.select": "Select",
        "action.switch": "Switch",
        "action.open_menu": "Open menu",
        "action.close_menu": "Close menu",
        "button.save": "Save",
        "button.cancel": "Cancel",
        "button.close": "Close",
        "button.retry": "Try again",
        "button.sign_out": "Sign out",
    },
    "ru": {
        "app.name": "OpenCare",
        "page.workspace_title": "Рабочая область здоровья OpenCare",
        "page.genetics_title": "Рабочая область генетики OpenCare",
        "page.vault_title": "Личное хранилище пользователя · OpenCare",
        "page.family_title": "Семья и доступ · OpenCare",
        "nav.overview": "Обзор",
        "nav.health": "Здоровье",
        "nav.workspace": "Рабочая область",
        "nav.documents": "Документы",
        "nav.activity": "Активность",
        "nav.chat": "Чат",
        "nav.genetics": "Генетика",
        "nav.vault": "Хранилище",
        "nav.family": "Семья и доступ",
        "nav.family_access": "Семья и доступ",
        "nav.settings": "Настройки",
        "shell.primary_navigation": "Основная навигация",
        "shell.open_navigation": "Открыть навигацию",
        "shell.close_navigation": "Закрыть навигацию",
        "shell.skip_to_content": "Перейти к содержимому",
        "shell.account": "Аккаунт",
        "shell.person": "Пользователь",
        "shell.no_person_selected": "Пользователь не выбран",
        "shell.language": "Язык",
        "locale.en": "English",
        "locale.ru": "Русский",
        "locale.current": "Текущий язык",
        "person.label": "Пользователь",
        "person.selected": "Выбранный пользователь",
        "person.no_selection": "Пользователь не выбран",
        "person.switch": "Сменить пользователя",
        "person.choose": "Выберите пользователя",
        "account.label": "Аккаунт",
        "account.menu": "Меню аккаунта",
        "account.profile": "Профиль",
        "account.signed_in_as": "Выполнен вход как",
        "status.loading": "Загрузка…",
        "status.ready": "Готово",
        "status.error": "Что-то пошло не так",
        "status.unavailable": "Недоступно",
        "status.saving": "Сохранение…",
        "status.saved": "Сохранено",
        "action.save": "Сохранить",
        "action.cancel": "Отмена",
        "action.close": "Закрыть",
        "action.retry": "Повторить",
        "action.sign_out": "Выйти",
        "action.select": "Выбрать",
        "action.switch": "Сменить",
        "action.open_menu": "Открыть меню",
        "action.close_menu": "Закрыть меню",
        "button.save": "Сохранить",
        "button.cancel": "Отмена",
        "button.close": "Закрыть",
        "button.retry": "Повторить",
        "button.sign_out": "Выйти",
    },
}


def _normalize_locale(locale: str | None) -> Locale:
    if locale == "ru":
        return "ru"
    return DEFAULT_LOCALE


def resolve_locale(request: Request) -> Locale:
    """Resolve an exact supported locale from the dedicated locale cookie."""
    return _normalize_locale(request.cookies.get(LOCALE_COOKIE_NAME))


def get_translations(locale: str | None) -> dict[str, str]:
    """Return an isolated catalog with missing entries filled from English."""
    requested = TRANSLATIONS[_normalize_locale(locale)]
    return {**TRANSLATIONS[DEFAULT_LOCALE], **requested}


def translate(locale: str | None, key: str) -> str:
    """Translate a UI key, falling back to English and then the unchanged key."""
    requested = TRANSLATIONS[_normalize_locale(locale)]
    if key in requested:
        return requested[key]
    return TRANSLATIONS[DEFAULT_LOCALE].get(key, key)
