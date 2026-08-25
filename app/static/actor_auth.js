(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const status = byId("actor-auth-status");
  const complete = byId("actor-auth-complete");
  const showStatus = (message, kind = "") => {
    status.textContent = message;
    status.className = kind;
  };
  const submit = async (path, payload) => {
    const response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("The account request could not be completed.");
    return response;
  };

  const loginForm = byId("actor-login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
      showStatus("Signing in…");
      try {
        await submit("/api/family-access/v1/login", {
          username: byId("login-username").value,
          password: byId("login-password").value,
        });
        byId("login-password").value = "";
        loginForm.hidden = true;
        complete.hidden = false;
        showStatus("Signed in.", "success");
      } catch (error) {
        showStatus(error.message, "error");
      } finally {
        button.disabled = false;
      }
    });
  }

  const bootstrapForm = byId("actor-bootstrap-form");
  if (bootstrapForm) {
    fetch("/api/family-access/v1/bootstrap-status", { credentials: "same-origin" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload) => {
        if (!payload.bootstrap_available) {
          bootstrapForm.hidden = true;
          showStatus("This installation has already been set up. Sign in instead.", "error");
        }
      })
      .catch(() => showStatus("Setup status is unavailable.", "error"));
    bootstrapForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      const personIds = byId("bootstrap-person-ids").value
        .split(/[\s,]+/)
        .map((value) => value.trim())
        .filter(Boolean);
      button.disabled = true;
      showStatus("Creating the first administrator…");
      try {
        await submit("/api/family-access/v1/bootstrap", {
          username: byId("bootstrap-username").value,
          display_name: byId("bootstrap-display-name").value,
          password: byId("bootstrap-password").value,
          bootstrap_secret: byId("bootstrap-secret")?.value || null,
          person_ids: personIds,
          own_person_id: null,
          confirm_full_owner_access: byId("bootstrap-owner-confirmation").checked,
        });
        byId("bootstrap-password").value = "";
        byId("bootstrap-person-ids").value = "";
        bootstrapForm.hidden = true;
        complete.hidden = false;
        showStatus("Installation administrator created.", "success");
      } catch (error) {
        showStatus(error.message, "error");
      } finally {
        if (byId("bootstrap-secret")) byId("bootstrap-secret").value = "";
        button.disabled = false;
      }
    });
  }
})();
