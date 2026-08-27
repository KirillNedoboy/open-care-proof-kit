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
        "form.username": "Username",
        "form.password": "Password",
        "form.display_name": "Display name",
        "form.confirm_password": "Confirm password",
        "form.invitation_code": "Invitation code",
        "form.existing_person_ids": "Existing Person IDs (optional, comma-separated)",
        "auth.private_workspace": "Private workspace",
        "auth.welcome_back": "Welcome back",
        "auth.sign_in": "Sign in",
        "auth.sign_in_intro": (
            "Use your local username and password to access your private workspace."
        ),
        "auth.create_account": "Create account",
        "auth.have_invitation": "Have an invitation?",
        "auth.use_invitation": "Use invitation",
        "auth.installation_setup": "Installation setup",
        "auth.open_workspace": "Open Workspace",
        "auth.local_account": "Private account",
        "auth.create_account_title": "Create your account",
        "auth.registration_intro": (
            "Create a private workspace for your own records. An invitation is not required "
            "when public registration is enabled."
        ),
        "auth.registration_status_checking": "Checking account registration…",
        "auth.registration_disabled": (
            "New account registration is not enabled for this installation. Sign in or use "
            "an invitation from someone sharing access with you."
        ),
        "auth.registration_uninitialized": (
            "This installation must be set up by its operator before accounts can be created."
        ),
        "auth.create_account_submit": "Create account",
        "auth.one_time_setup": "One-time installation setup",
        "auth.bootstrap_title": "Create the installation administrator",
        "auth.bootstrap_intro": "This page is used once by the server owner.",
        "auth.administrator_account": "Administrator account",
        "auth.bootstrap_admin_copy": (
            "The administrator manages this installation. Person access is granted only "
            "through the explicit existing-Person controls below."
        ),
        "auth.advanced": "Advanced",
        "auth.existing_person_ids_help": (
            "Use this only when the installation owner must claim existing People. Full "
            "owner confirmation is required."
        ),
        "auth.owner_confirmation": (
            "I understand that every listed Person will grant this Actor full owner access."
        ),
        "auth.create_administrator": "Create administrator",
        "auth.setup_complete": "Installation setup is complete. Sign in to continue.",
        "auth.sign_in_instead": "Sign in instead",
        "auth.private_invitation": "Family sharing invitation",
        "auth.invitation_title": "Use an invitation",
        "auth.invitation_intro": (
            "An invitation grants access shared by another person or family member. It is "
            "not required for normal sign-in or self-registration."
        ),
        "auth.review_invitation": "Review invitation",
        "auth.invitation_details": "Invitation details",
        "auth.owner_invitation": "Owner invitation — full control",
        "auth.caregiver_invitation": "Caregiver invitation",
        "auth.permissions": "Permissions",
        "auth.owner_warning": (
            "This invitation grants full owner control, including access management and export."
        ),
        "auth.create_account_accept": "Create an account and accept",
        "auth.accept_signed_in": "Accept with the signed-in account",
        "auth.accept_invitation": "Accept invitation",
        "auth.invitation_accepted": "Invitation accepted.",
        "status.signing_in": "Signing in…",
        "status.account_request_failed": "The account request could not be completed.",
        "status.bootstrap_status_unavailable": "Setup status is unavailable.",
        "status.creating_administrator": "Creating the first administrator…",
        "status.administrator_created": "Installation administrator created.",
        "status.registration_status_unavailable": "Account registration status is unavailable.",
        "status.password_mismatch": "Passwords do not match.",
        "status.creating_account": "Creating account…",
        "status.account_could_not_created": "Account could not be created.",
        "status.checking_invitation": "Checking invitation…",
        "status.invitation_cannot_be_used": "This invitation cannot be used.",
        "status.review_access": "Review the access before accepting.",
        "page.login_title": "Sign in · OpenCare",
        "page.register_title": "Create account · OpenCare",
        "page.bootstrap_title": "Installation setup · OpenCare",
        "page.invitation_title": "Use invitation · OpenCare",
        "auth.other_options": "Other account options",
        "form.bootstrap_secret": "Operator bootstrap secret",
        "auth.bootstrap_secret_production": (
            "Required in production. It is checked once and never stored."
        ),
        "auth.checking_setup": "Checking setup availability…",
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
        "form.username": "Имя пользователя",
        "form.password": "Пароль",
        "form.display_name": "Отображаемое имя",
        "form.confirm_password": "Подтвердите пароль",
        "form.invitation_code": "Код приглашения",
        "form.existing_person_ids": "Идентификаторы пользователей (необязательно, через запятую)",
        "auth.private_workspace": "Личное рабочее пространство",
        "auth.welcome_back": "С возвращением",
        "auth.sign_in": "Войти",
        "auth.sign_in_intro": (
            "Введите локальные имя пользователя и пароль для доступа к личному рабочему "
            "пространству."
        ),
        "auth.create_account": "Создать аккаунт",
        "auth.have_invitation": "Есть приглашение?",
        "auth.use_invitation": "Использовать приглашение",
        "auth.installation_setup": "Настройка установки",
        "auth.open_workspace": "Открыть рабочую область",
        "auth.local_account": "Личный аккаунт",
        "auth.create_account_title": "Создайте аккаунт",
        "auth.registration_intro": (
            "Создайте личную рабочую область для собственных записей. При включённой "
            "открытой регистрации приглашение не требуется."
        ),
        "auth.registration_status_checking": "Проверяем доступность регистрации…",
        "auth.registration_disabled": (
            "Регистрация новых аккаунтов отключена для этой установки. Войдите или "
            "используйте приглашение от пользователя, который делится доступом."
        ),
        "auth.registration_uninitialized": "Сначала оператор должен настроить эту установку.",
        "auth.create_account_submit": "Создать аккаунт",
        "auth.one_time_setup": "Однократная настройка установки",
        "auth.bootstrap_title": "Создайте администратора установки",
        "auth.bootstrap_intro": "Эта страница используется один раз владельцем сервера.",
        "auth.administrator_account": "Аккаунт администратора",
        "auth.bootstrap_admin_copy": (
            "Администратор управляет этой установкой. Доступ к пользователям выдаётся только "
            "через явные настройки существующих пользователей ниже."
        ),
        "auth.advanced": "Расширенные настройки",
        "auth.existing_person_ids_help": (
            "Используйте это, только если владельцу установки нужно заявить права на "
            "существующих пользователей. Требуется полное подтверждение прав владельца."
        ),
        "auth.owner_confirmation": (
            "Я понимаю, что каждый указанный пользователь предоставит этому аккаунту полный "
            "доступ владельца."
        ),
        "auth.create_administrator": "Создать администратора",
        "auth.setup_complete": "Установка уже настроена. Войдите, чтобы продолжить.",
        "auth.sign_in_instead": "Войти вместо этого",
        "auth.private_invitation": "Приглашение для семейного доступа",
        "auth.invitation_title": "Использовать приглашение",
        "auth.invitation_intro": (
            "Приглашение предоставляет доступ, которым делится другой пользователь или член "
            "семьи. Для обычного входа или самостоятельной регистрации оно не требуется."
        ),
        "auth.review_invitation": "Проверить приглашение",
        "auth.invitation_details": "Сведения о приглашении",
        "auth.owner_invitation": "Приглашение владельца — полный доступ",
        "auth.caregiver_invitation": "Приглашение помощника",
        "auth.permissions": "Разрешения",
        "auth.owner_warning": (
            "Это приглашение предоставляет полный доступ владельца, включая управление "
            "доступом и экспорт."
        ),
        "auth.create_account_accept": "Создать аккаунт и принять",
        "auth.accept_signed_in": "Принять вошедшим аккаунтом",
        "auth.accept_invitation": "Принять приглашение",
        "auth.invitation_accepted": "Приглашение принято.",
        "status.signing_in": "Выполняем вход…",
        "status.account_request_failed": "Не удалось выполнить запрос аккаунта.",
        "status.bootstrap_status_unavailable": "Статус настройки недоступен.",
        "status.creating_administrator": "Создаём первого администратора…",
        "status.administrator_created": "Администратор установки создан.",
        "status.registration_status_unavailable": "Статус регистрации аккаунта недоступен.",
        "status.password_mismatch": "Пароли не совпадают.",
        "status.creating_account": "Создаём аккаунт…",
        "status.account_could_not_created": "Не удалось создать аккаунт.",
        "status.checking_invitation": "Проверяем приглашение…",
        "status.invitation_cannot_be_used": "Это приглашение нельзя использовать.",
        "status.review_access": "Проверьте предоставляемый доступ перед принятием.",
        "page.login_title": "Вход · OpenCare",
        "page.register_title": "Создание аккаунта · OpenCare",
        "page.bootstrap_title": "Настройка установки · OpenCare",
        "page.invitation_title": "Использование приглашения · OpenCare",
        "auth.other_options": "Другие варианты",
        "form.bootstrap_secret": "Секрет оператора для настройки",
        "auth.bootstrap_secret_production": (
            "Требуется в production. Проверяется один раз и не сохраняется."
        ),
        "auth.checking_setup": "Проверяем доступность настройки…",
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
