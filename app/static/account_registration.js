(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const status = byId("registration-status");
  const form = byId("actor-register-form");
  const disabled = byId("registration-disabled");
  const uninitialized = byId("registration-uninitialized");
  const translate = (key) => window.OpenCareI18n?.t(key, key) || key;
  const showStatus = (message, kind = "") => {
    status.textContent = message;
    status.className = `auth-status ${kind}`.trim();
    status.hidden = false;
  };

  fetch("/api/family-access/v1/registration-status", { credentials: "same-origin" })
    .then((response) => response.ok ? response.json() : Promise.reject())
    .then((payload) => {
      if (payload.registration_available) {
        form.hidden = false;
        status.hidden = true;
        return;
      }
      form.hidden = true;
      if (payload.registration_enabled) {
        uninitialized.hidden = false;
        status.hidden = true;
      } else {
        disabled.hidden = false;
        status.hidden = true;
      }
    })
    .catch(() => showStatus(translate("status.registration_status_unavailable"), "error"));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    const password = byId("register-password");
    const confirmation = byId("register-password-confirm");
    if (password.value !== confirmation.value) {
      showStatus(translate("status.password_mismatch"), "error");
      return;
    }
    button.disabled = true;
    showStatus(translate("status.creating_account"));
    try {
      const response = await fetch("/api/family-access/v1/register", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: byId("register-username").value,
          display_name: byId("register-display-name").value,
          password: password.value,
        }),
      });
      if (!response.ok) throw new Error(translate("status.account_could_not_created"));
      password.value = "";
      confirmation.value = "";
      window.location.assign("/workspace");
    } catch (error) {
      showStatus(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });
})();
