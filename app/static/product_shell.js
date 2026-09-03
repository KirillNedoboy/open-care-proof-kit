(() => {
  "use strict";

  const supportedLocales = new Set(["en", "ru"]);
  const shell = document.querySelector(".product-shell");
  const sidebar = document.getElementById("product-sidebar");
  const menuButton = document.querySelector(".product-shell__menu-button");
  const localeSelect = document.getElementById("product-shell-locale");
  const translationPayload = document.getElementById("product-shell-translations");

  if (!shell || !sidebar || !menuButton || !localeSelect || !translationPayload) {
    return;
  }

  let translations = {};
  try {
    const parsed = JSON.parse(translationPayload.textContent || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      translations = parsed;
    }
  } catch (_error) {
    translations = {};
  }

  const translatedLabel = (key, currentLabel) => {
    const value = translations[key];
    return typeof value === "string" && value ? value : currentLabel;
  };

  const mobileNavigation = window.matchMedia("(max-width: 52rem)");
  const navigationLinks = Array.from(shell.querySelectorAll("[data-nav-key]"));

  const resolvePrimaryNavigation = () => {
    const { pathname, hash } = window.location;
    if (pathname === "/workspace") {
      return {
        "#overview": "overview",
        "#records": "health",
        "#documents": "documents",
        "#timeline": "activity",
      }[hash] || "overview";
    }
    if (pathname === "/chat") return "chat";
    if (pathname === "/genetics") return "genetics";
    if (pathname === "/family-access") return hash === "#account-settings" ? "settings" : "family";
    return null;
  };

  const syncPrimaryNavigation = () => {
    const activeKey = resolvePrimaryNavigation();
    if (!activeKey) return;
    navigationLinks.forEach((link) => {
      link.classList.remove("is-active");
      link.removeAttribute("aria-current");
    });
    const activeLink = navigationLinks.find((link) => link.dataset.navKey === activeKey);
    if (!activeLink) return;
    activeLink.classList.add("is-active");
    activeLink.setAttribute("aria-current", "page");
  };

  const setNavigationOpen = (open) => {
    const isOpen = Boolean(open);
    shell.dataset.navigationOpen = String(isOpen);
    menuButton.setAttribute("aria-expanded", String(isOpen));

    const key = isOpen ? "shell.close_navigation" : "shell.open_navigation";
    const label = translatedLabel(key, menuButton.getAttribute("aria-label") || "");
    menuButton.setAttribute("aria-label", label);
    menuButton.setAttribute("title", label);
  };

  shell.classList.add("product-shell--enhanced");
  setNavigationOpen(!mobileNavigation.matches);
  syncPrimaryNavigation();

  window.addEventListener("hashchange", syncPrimaryNavigation);

  menuButton.addEventListener("click", () => {
    setNavigationOpen(shell.dataset.navigationOpen !== "true");
  });

  sidebar.addEventListener("click", (event) => {
    if (mobileNavigation.matches && event.target.closest("a")) {
      setNavigationOpen(false);
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && mobileNavigation.matches && shell.dataset.navigationOpen === "true") {
      setNavigationOpen(false);
      menuButton.focus();
    }
  });

  const handleViewportChange = (event) => {
    setNavigationOpen(!event.matches);
  };

  if (typeof mobileNavigation.addEventListener === "function") {
    mobileNavigation.addEventListener("change", handleViewportChange);
  } else {
    mobileNavigation.addListener(handleViewportChange);
  }

  localeSelect.addEventListener("change", () => {
    const locale = localeSelect.value;
    if (!supportedLocales.has(locale)) {
      return;
    }

    document.cookie = `opencare_locale=${locale}; Max-Age=31536000; Path=/; SameSite=Lax`;
    window.location.reload();
  });
})();
