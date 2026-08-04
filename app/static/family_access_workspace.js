(() => {
  "use strict";
  const familyApi = "/api/family-access/v1";
  const productApi = "/api/product-core/v1";
  const byId = (id) => document.getElementById(id);
  const state = { people: [], actors: [], families: [], personId: null, familyId: null, revising: null };
  const csrfToken = () => document.cookie.split("; ")
    .find((item) => item.startsWith("opencare_csrf="))
    ?.split("=").slice(1).join("=") || "";
  const status = (message, kind = "") => {
    byId("family-access-status").textContent = message;
    byId("family-access-status").className = kind;
  };
  const api = async (path, options = {}) => {
    const method = (options.method || "GET").toUpperCase();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
      headers["X-OpenCare-CSRF"] = csrfToken();
    }
    const response = await fetch(path, { credentials: "same-origin", ...options, headers });
    if (!response.ok) {
      const message = response.status === 403
        ? "Your account is not permitted to perform that action."
        : response.status === 404
          ? "That record is not available."
          : "The access request could not be completed.";
      throw new Error(message);
    }
    return response.status === 204 ? null : response.json();
  };
  const clear = (node) => node.replaceChildren();
  const make = (tag, text = "", className = "") => {
    const node = document.createElement(tag);
    node.textContent = text;
    node.className = className;
    return node;
  };
  const button = (label, action) => {
    const node = make("button", label);
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  };
  const selectedScopes = (fieldsetId) => Array.from(
    byId(fieldsetId).querySelectorAll("input[type=checkbox]:checked"),
    (input) => input.value,
  );
  const setSelectedScopes = (fieldsetId, scopes) => {
    byId(fieldsetId).querySelectorAll("input[type=checkbox]").forEach((input) => {
      input.checked = scopes.includes(input.value);
    });
  };
  const setOptions = (select, items, placeholder, valueKey, labelKey) => {
    const selected = select.value;
    clear(select);
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = placeholder;
    select.append(empty);
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item[valueKey];
      option.textContent = item[labelKey];
      select.append(option);
    });
    if (items.some((item) => item[valueKey] === selected)) select.value = selected;
    select.disabled = items.length === 0;
  };
  const actorName = (actorId) => state.actors.find((actor) => actor.actor_id === actorId)?.display_name || actorId;
  const personName = (personId) => state.people.find((person) => person.person_id === personId)?.display_name || personId;

  const loadPersonAccess = async () => {
    state.personId = byId("access-person-selector").value || null;
    state.revising = null;
    byId("revise-access-form").hidden = true;
    const assignmentList = byId("assignment-list");
    clear(assignmentList);
    if (!state.personId) {
      assignmentList.append(make("p", "No Person selected."));
      byId("grant-access-form").hidden = true;
      byId("create-invitation-form").hidden = true;
      clear(byId("consent-list"));
      clear(byId("access-audit-list"));
      return;
    }
    status("Loading Person access…");
    try {
      const [assignments, consents, audits] = await Promise.all([
        api(`${familyApi}/people/${encodeURIComponent(state.personId)}/access-assignments`),
        api(`${familyApi}/people/${encodeURIComponent(state.personId)}/consents`),
        api(`${familyApi}/people/${encodeURIComponent(state.personId)}/access-audit`),
      ]);
      if (assignments.assignments.length === 0) assignmentList.append(make("p", "No visible assignments."));
      assignments.assignments.forEach((assignment) => {
        const record = make("article", "", "record");
        record.append(make("strong", `${actorName(assignment.actor_id)} · ${assignment.role}`));
        record.append(make("p", assignment.is_active ? "Active" : "Revoked", "meta"));
        if (assignment.is_active && assignment.role === "caregiver") {
          record.append(button("Revise caregiver permissions", () => {
            state.revising = assignment;
            byId("revise-access-label").textContent = actorName(assignment.actor_id);
            setSelectedScopes("revise-caregiver-scopes", assignment.scopes);
            byId("revise-access-form").hidden = false;
            byId("revise-access-label").focus?.();
          }));
        }
        if (assignment.is_active) {
          record.append(button("Revoke access", async () => {
            if (!window.confirm("Revoke this Person assignment? The last owner cannot be removed.")) return;
            try {
              await api(`${familyApi}/people/${encodeURIComponent(state.personId)}/access-assignments/${encodeURIComponent(assignment.assignment_id)}:revoke`, { method: "POST", body: "{}" });
              await loadPersonAccess();
              status("Access revoked.", "success");
            } catch (error) { status(error.message, "error"); }
          }));
        }
        assignmentList.append(record);
      });
      const consentList = byId("consent-list");
      clear(consentList);
      if (consents.consents.length === 0) consentList.append(make("p", "No visible consent history."));
      consents.consents.forEach((consent) => consentList.append(make("p", `${consent.created_at} · ${consent.event_type} · ${actorName(consent.recipient_actor_id)} · ${consent.role}`, "record")));
      const auditList = byId("access-audit-list");
      clear(auditList);
      if (audits.audit_events.length === 0) auditList.append(make("p", "No visible access audit events."));
      audits.audit_events.forEach((event) => auditList.append(make("p", `${event.created_at} · ${event.action_code} · ${event.outcome}`, "record")));
      byId("grant-access-form").hidden = false;
      byId("create-invitation-form").hidden = false;
      status("Person access loaded.");
    } catch (error) {
      assignmentList.append(make("p", "Person access management is unavailable.", "error"));
      byId("grant-access-form").hidden = true;
      byId("create-invitation-form").hidden = true;
      status(error.message, "error");
    }
  };

  const renderFamily = async () => {
    state.familyId = byId("family-selector").value || null;
    const details = byId("family-details");
    clear(details);
    byId("add-family-member-form").hidden = !state.familyId;
    byId("create-relationship-form").hidden = !state.familyId;
    if (!state.familyId) { details.append(make("p", "No Family selected.")); return; }
    try {
      const payload = await api(`${familyApi}/families/${encodeURIComponent(state.familyId)}`);
      details.append(make("h3", payload.family.display_name));
      if (payload.memberships.length === 0) details.append(make("p", "No visible Family members."));
      payload.memberships.forEach((membership) => {
        const record = make("article", personName(membership.person_id), "record");
        record.append(button("End membership", async () => {
          try {
            await api(`${familyApi}/families/${encodeURIComponent(state.familyId)}/memberships/${encodeURIComponent(membership.membership_id)}:end`, { method: "POST", body: "{}" });
            await renderFamily();
          } catch (error) { status(error.message, "error"); }
        }));
        details.append(record);
      });
      payload.relationships.forEach((relationship) => {
        const record = make("article", `${personName(relationship.person_id)} · ${relationship.relationship_type} · ${personName(relationship.related_person_id)}`, "record");
        record.append(button("End relationship", async () => {
          try {
            await api(`${familyApi}/families/${encodeURIComponent(state.familyId)}/relationships/${encodeURIComponent(relationship.relationship_id)}:end`, { method: "POST", body: "{}" });
            await renderFamily();
          } catch (error) { status(error.message, "error"); }
        }));
        details.append(record);
      });
    } catch (error) { details.append(make("p", error.message, "error")); }
  };

  const load = async () => {
    status("Loading access workspace…");
    try {
      const [me, people, families] = await Promise.all([
        api(`${familyApi}/me`), api(`${productApi}/people`), api(`${familyApi}/families`),
      ]);
      state.people = people.people;
      state.families = families.families;
      byId("current-actor").textContent = `Signed in as ${me.actor.display_name}`;
      setOptions(byId("access-person-selector"), state.people, "No Person selected", "person_id", "display_name");
      setOptions(byId("family-member-person"), state.people, "Select Person", "person_id", "display_name");
      setOptions(byId("relationship-person"), state.people, "Select Person", "person_id", "display_name");
      setOptions(byId("relationship-related-person"), state.people, "Select related Person", "person_id", "display_name");
      setOptions(byId("family-selector"), state.families, "No Family selected", "family_id", "display_name");
      try {
        state.actors = (await api(`${familyApi}/actors`)).actors;
        const actorRecords = byId("actor-records");
        clear(actorRecords);
        state.actors.forEach((actor) => {
          const record = make("article", `${actor.display_name} · ${actor.status}`, "record");
          record.append(make("p", `Actor ID: ${actor.actor_id}`, "meta"));
          if (actor.status === "active" && actor.actor_id !== me.actor.actor_id) {
            record.append(button("Deactivate Actor", async () => {
              if (!window.confirm("Deactivate this Actor and revoke all of their Person access?")) return;
              try {
                await api(`${familyApi}/actors/${encodeURIComponent(actor.actor_id)}:deactivate`, { method: "POST", body: "{}" });
                record.replaceChildren(make("p", "Actor deactivated."));
              } catch (error) { status(error.message, "error"); }
            }));
          }
          actorRecords.append(record);
        });
        byId("actor-list").hidden = false;
      } catch (_) {
        state.actors = [];
        byId("actor-list").hidden = true;
      }
      if (me.active_person_id && state.people.some((person) => person.person_id === me.active_person_id)) {
        byId("access-person-selector").value = me.active_person_id;
      }
      await loadPersonAccess();
      status("Access workspace ready.", "success");
    } catch (error) { status(error.message, "error"); }
  };

  byId("access-person-selector").addEventListener("change", () => { void loadPersonAccess(); });
  byId("family-selector").addEventListener("change", () => { void renderFamily(); });
  ["grant-role", "invitation-role-select"].forEach((id) => byId(id).addEventListener("change", () => {
    const prefix = id === "grant-role" ? "grant" : "invitation";
    byId(`${prefix}-caregiver-scopes`).disabled = byId(id).value === "owner";
  }));

  byId("grant-access-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const role = byId("grant-role").value;
    try {
      await api(`${familyApi}/people/${encodeURIComponent(state.personId)}/access-assignments`, {
        method: "POST",
        body: JSON.stringify({ recipient_actor_id: byId("grant-actor-id").value, role, optional_scopes: role === "caregiver" ? selectedScopes("grant-caregiver-scopes") : [], confirm_full_owner_access: role === "owner" && byId("grant-owner-confirmation").checked }),
      });
      form.reset();
      byId("grant-caregiver-scopes").disabled = false;
      await loadPersonAccess();
      status("Access granted.", "success");
    } catch (error) { status(error.message, "error"); }
  });

  byId("revise-access-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.revising) return;
    try {
      await api(`${familyApi}/people/${encodeURIComponent(state.personId)}/access-assignments/${encodeURIComponent(state.revising.assignment_id)}:revise`, { method: "POST", body: JSON.stringify({ optional_scopes: selectedScopes("revise-caregiver-scopes") }) });
      state.revising = null;
      byId("revise-access-form").hidden = true;
      await loadPersonAccess();
      status("Caregiver permissions revised.", "success");
    } catch (error) { status(error.message, "error"); }
  });
  byId("cancel-access-revision").addEventListener("click", () => { state.revising = null; byId("revise-access-form").hidden = true; });

  byId("create-invitation-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const role = byId("invitation-role-select").value;
    const expiry = new Date(byId("invitation-expiry").value);
    try {
      const issued = await api(`${familyApi}/people/${encodeURIComponent(state.personId)}/invitations`, { method: "POST", body: JSON.stringify({ role, optional_scopes: role === "caregiver" ? selectedScopes("invitation-caregiver-scopes") : [], expires_at: expiry.toISOString(), confirm_full_owner_access: role === "owner" && byId("confirm-full-owner-access").checked }) });
      byId("issued-invitation-code").textContent = issued.secret;
      byId("issued-invitation").hidden = false;
      form.reset();
      byId("invitation-caregiver-scopes").disabled = false;
      status("Invitation created. Copy the code now.", "success");
    } catch (error) { status(error.message, "error"); }
  });
  byId("clear-invitation-code").addEventListener("click", () => { byId("issued-invitation-code").textContent = ""; byId("issued-invitation").hidden = true; status("Invitation code cleared from this page."); });

  byId("create-family-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const family = await api(`${familyApi}/families`, { method: "POST", body: JSON.stringify({ display_name: byId("family-display-name").value }) });
      state.families.push(family);
      setOptions(byId("family-selector"), state.families, "No Family selected", "family_id", "display_name");
      byId("family-selector").value = family.family_id;
      form.reset();
      await renderFamily();
    } catch (error) { status(error.message, "error"); }
  });
  byId("add-family-member-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api(`${familyApi}/families/${encodeURIComponent(state.familyId)}/memberships`, { method: "POST", body: JSON.stringify({ person_id: byId("family-member-person").value }) });
      await renderFamily();
    } catch (error) { status(error.message, "error"); }
  });
  byId("create-relationship-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api(`${familyApi}/families/${encodeURIComponent(state.familyId)}/relationships`, { method: "POST", body: JSON.stringify({ person_id: byId("relationship-person").value, related_person_id: byId("relationship-related-person").value, relationship_type: byId("relationship-type").value }) });
      await renderFamily();
    } catch (error) { status(error.message, "error"); }
  });
  byId("change-password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await api(`${familyApi}/password:change`, { method: "POST", body: JSON.stringify({ current_password: byId("current-password").value, new_password: byId("new-password").value }) });
      form.reset();
      status("Password changed. Sign in again.", "success");
    } catch (error) { status(error.message, "error"); }
  });
  byId("actor-logout").addEventListener("click", async () => {
    try {
      await api(`${familyApi}/logout`, { method: "POST", body: "{}" });
      status("Signed out. Use the sign-in page to continue.", "success");
    } catch (error) { status(error.message, "error"); }
  });

  void load();
})();
