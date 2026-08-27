(() => {
  "use strict";

  const localeWhitelist = new Set(["en", "ru"]);
  const shell = document.querySelector(".public-auth-shell");
  const localeSelect = document.getElementById("public-auth-locale");
  const translationPayload = document.getElementById("public-auth-translations");

  let translations = {};
  try {
    const parsed = JSON.parse(translationPayload?.textContent || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      translations = parsed;
    }
  } catch (_error) {
    translations = {};
  }

  const translate = (key, fallback = "") => {
    const value = translations[key];
    return typeof value === "string" && value ? value : fallback;
  };

  window.OpenCareI18n = Object.freeze({
    locale: document.documentElement.lang,
    t: translate,
  });

  if (!localeSelect) {
    return;
  }

  const configuredLocales = (shell?.dataset.supportedLocales || "")
    .split(/\s+/)
    .filter((locale) => localeWhitelist.has(locale));
  const supportedLocales = new Set(
    configuredLocales.length ? configuredLocales : localeWhitelist,
  );

  localeSelect.addEventListener("change", () => {
    const locale = localeSelect.value;
    if (!supportedLocales.has(locale)) {
      return;
    }

    document.cookie = `opencare_locale=${locale}; Max-Age=31536000; Path=/; SameSite=Lax`;
    window.location.reload();
  });
})();
