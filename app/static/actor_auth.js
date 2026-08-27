(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const status = byId("actor-auth-status");
  const complete = byId("actor-auth-complete");
  const translate = (key) => window.OpenCareI18n?.t(key, key) || key;
  const showStatus = (message, kind = "") => {
    if (!status) return;
    status.textContent = message;
    status.className = `auth-status ${kind}`.trim();
    status.hidden = false;
  };
  const submit = async (path, payload) => {
    const response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(translate("status.account_request_failed"));
    return response;
  };

  const registrationLink = byId("registration-link");
  if (registrationLink) {
    fetch("/api/family-access/v1/registration-status", { credentials: "same-origin" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload) => { registrationLink.hidden = !payload.registration_available; })
      .catch(() => {});
  }

  const bootstrapLink = byId("bootstrap-link");
  if (bootstrapLink) {
    fetch("/api/family-access/v1/bootstrap-status", { credentials: "same-origin" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload) => { bootstrapLink.hidden = !payload.bootstrap_available; })
      .catch(() => {});
  }

  const loginForm = byId("actor-login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      button.disabled = true;
      showStatus(translate("status.signing_in"));
      try {
        await submit("/api/family-access/v1/login", {
          username: byId("login-username").value,
          password: byId("login-password").value,
        });
        byId("login-password").value = "";
        window.location.assign(byId("login-next").value || "/workspace");
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
        bootstrapForm.hidden = !payload.bootstrap_available;
        if (payload.bootstrap_available) {
          status.hidden = true;
        } else {
          byId("bootstrap-setup-complete").hidden = false;
          showStatus(translate("auth.setup_complete"));
        }
      })
      .catch(() => {
        bootstrapForm.hidden = true;
        showStatus(translate("status.bootstrap_status_unavailable"), "error");
      });
    bootstrapForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = event.submitter;
      const personIds = byId("bootstrap-person-ids").value
        .split(/[\s,]+/)
        .map((value) => value.trim())
        .filter(Boolean);
      button.disabled = true;
      showStatus(translate("status.creating_administrator"));
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
        showStatus(translate("status.administrator_created"), "success");
      } catch (error) {
        showStatus(error.message, "error");
      } finally {
        if (byId("bootstrap-secret")) byId("bootstrap-secret").value = "";
        button.disabled = false;
      }
    });
  }
})();
