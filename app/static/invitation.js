(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const code = byId("invitation-code");
  const status = byId("invitation-status");
  const preview = byId("invitation-preview");
  const registerForm = byId("invitation-register-form");
  const acceptForm = byId("invitation-accept-form");
  const translate = (key) => window.OpenCareI18n?.t(key, key) || key;
  let signedIn = false;
  let invitationRole = null;

  const csrfToken = () => document.cookie
    .split("; ")
    .find((item) => item.startsWith("opencare_csrf="))
    ?.split("=").slice(1).join("=") || "";
  const showStatus = (message, kind = "") => {
    status.textContent = message;
    status.className = `auth-status ${kind}`.trim();
    status.hidden = false;
  };
  const request = async (path, payload, authenticated = false) => {
    const headers = { "Content-Type": "application/json" };
    if (authenticated) headers["X-OpenCare-CSRF"] = csrfToken();
    const response = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers,
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(translate("status.invitation_cannot_be_used"));
    return response.status === 204 ? null : response.json();
  };
  const ownerConfirmation = (id) => invitationRole === "owner" && byId(id).checked;
  const finish = () => {
    code.value = "";
    registerForm.hidden = true;
    acceptForm.hidden = true;
    byId("invitation-preview-form").hidden = true;
    byId("invitation-complete").hidden = false;
    showStatus(translate("auth.invitation_accepted"), "success");
  };

  const sessionCheck = fetch("/api/family-access/v1/me", { credentials: "same-origin" })
    .then((response) => { signedIn = response.ok; })
    .catch(() => { signedIn = false; });

  byId("invitation-preview-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    showStatus(translate("status.checking_invitation"));
    try {
      await sessionCheck;
      const payload = await request(
        "/api/family-access/v1/invite/preview",
        { secret: code.value },
      );
      invitationRole = payload.role;
      byId("invitation-role").textContent = payload.role === "owner"
        ? translate("auth.owner_invitation")
        : translate("auth.caregiver_invitation");
      byId("invitation-scopes").textContent = `${translate("auth.permissions")}: ${payload.scopes.join(", ")}`;
      byId("owner-invitation-warning").hidden = payload.role !== "owner";
      preview.hidden = false;
      registerForm.hidden = signedIn;
      acceptForm.hidden = !signedIn;
      showStatus(translate("status.review_access"));
    } catch (error) {
      invitationRole = null;
      preview.hidden = true;
      registerForm.hidden = true;
      acceptForm.hidden = true;
      showStatus(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      await request("/api/family-access/v1/invite/register", {
        secret: code.value,
        username: byId("invite-username").value,
        display_name: byId("invite-display-name").value,
        password: byId("invite-password").value,
        confirm_full_owner_access: ownerConfirmation("register-owner-confirmation"),
      });
      byId("invite-password").value = "";
      finish();
    } catch (error) {
      showStatus(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });

  acceptForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    try {
      await request("/api/family-access/v1/invite/accept", {
        secret: code.value,
        confirm_full_owner_access: ownerConfirmation("accept-owner-confirmation"),
      }, true);
      finish();
    } catch (error) {
      showStatus(error.message, "error");
    } finally {
      button.disabled = false;
    }
  });
})();
