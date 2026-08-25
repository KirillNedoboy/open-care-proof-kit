(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const status = byId("registration-status");
  const form = byId("actor-register-form");
  const disabled = byId("registration-disabled");
  const uninitialized = byId("registration-uninitialized");
  const showStatus = (message, kind = "") => {
    status.textContent = message;
    status.className = kind;
  };

  fetch("/api/family-access/v1/registration-status", { credentials: "same-origin" })
    .then((response) => response.ok ? response.json() : Promise.reject())
    .then((payload) => {
      if (payload.registration_available) {
        form.hidden = false;
        status.hidden = true;
        return;
      }
      if (payload.registration_enabled) {
        uninitialized.hidden = false;
        status.hidden = true;
      } else {
        disabled.hidden = false;
        status.hidden = true;
      }
    })
    .catch(() => showStatus("Account registration status is unavailable.", "error"));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    const password = byId("register-password");
    const confirmation = byId("register-password-confirm");
    if (password.value !== confirmation.value) {
      showStatus("Passwords do not match.", "error");
      return;
    }
    button.disabled = true;
    showStatus("Creating account…");
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
      if (!response.ok) throw new Error("Account could not be created.");
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
