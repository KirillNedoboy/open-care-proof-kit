(() => {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const code = byId("invitation-code");
  const status = byId("invitation-status");
  const preview = byId("invitation-preview");
  const registerForm = byId("invitation-register-form");
  const acceptForm = byId("invitation-accept-form");
  let signedIn = false;
  let invitationRole = null;

  const csrfToken = () => document.cookie
    .split("; ")
    .find((item) => item.startsWith("opencare_csrf="))
    ?.split("=").slice(1).join("=") || "";
  const showStatus = (message, kind = "") => {
    status.textContent = message;
    status.className = kind;
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
    if (!response.ok) throw new Error("This invitation cannot be used.");
    return response.status === 204 ? null : response.json();
  };
  const ownerConfirmation = (id) => invitationRole === "owner" && byId(id).checked;
  const finish = () => {
    code.value = "";
    registerForm.hidden = true;
    acceptForm.hidden = true;
    byId("invitation-preview-form").hidden = true;
    byId("invitation-complete").hidden = false;
    showStatus("Invitation accepted.", "success");
  };

  const sessionCheck = fetch("/api/family-access/v1/me", { credentials: "same-origin" })
    .then((response) => { signedIn = response.ok; })
    .catch(() => { signedIn = false; });

  byId("invitation-preview-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = event.submitter;
    button.disabled = true;
    showStatus("Checking invitation…");
    try {
      await sessionCheck;
      const payload = await request(
        "/api/family-access/v1/invite/preview",
        { secret: code.value },
      );
      invitationRole = payload.role;
      byId("invitation-role").textContent = payload.role === "owner"
        ? "Owner invitation — full control"
        : "Caregiver invitation";
      byId("invitation-scopes").textContent = `Permissions: ${payload.scopes.join(", ")}`;
      byId("owner-invitation-warning").hidden = payload.role !== "owner";
      preview.hidden = false;
      registerForm.hidden = signedIn;
      acceptForm.hidden = !signedIn;
      showStatus("Review the access before accepting.");
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
