(() => {
  "use strict";

  const familyApi = "/api/family-access/v1";
  const productApi = "/api/product-core/v1";
  const byId = (id) => document.getElementById(id);
  const translationPayload = byId("product-shell-translations");
  let translations = {};
  try {
    const parsed = JSON.parse(translationPayload?.textContent || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) translations = parsed;
  } catch (_) {}
  const t = (key, fallback = key) => typeof translations[key] === "string" && translations[key] ? translations[key] : fallback;
  const tf = (key, replacements, fallback = key) => Object.entries(replacements).reduce(
    (value, [name, replacement]) => value.split(`{${name}}`).join(String(replacement)),
    t(key, fallback),
  );

  const SCOPE_PRESENTATION = Object.freeze({
    "person.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.person_read" }),
    "person.update": Object.freeze({ group: "family.scope_group.health", label: "family.scope.person_update" }),
    "source.read": Object.freeze({ group: "family.scope_group.sources_documents", label: "family.scope.source_read" }),
    "source.write": Object.freeze({ group: "family.scope_group.sources_documents", label: "family.scope.source_write" }),
    "document.read": Object.freeze({ group: "family.scope_group.sources_documents", label: "family.scope.document_read" }),
    "document.write": Object.freeze({ group: "family.scope_group.sources_documents", label: "family.scope.document_write" }),
    "candidate.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.candidate_read" }),
    "candidate.review": Object.freeze({ group: "family.scope_group.health", label: "family.scope.candidate_review" }),
    "medication.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.medication_read" }),
    "medication.write": Object.freeze({ group: "family.scope_group.health", label: "family.scope.medication_write" }),
    "condition.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.condition_read" }),
    "condition.write": Object.freeze({ group: "family.scope_group.health", label: "family.scope.condition_write" }),
    "lab.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.lab_read" }),
    "lab.write": Object.freeze({ group: "family.scope_group.health", label: "family.scope.lab_write" }),
    "timeline.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.timeline_read" }),
    "visit.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.visit_read" }),
    "visit.write": Object.freeze({ group: "family.scope_group.health", label: "family.scope.visit_write" }),
    "brief.read": Object.freeze({ group: "family.scope_group.health", label: "family.scope.brief_read" }),
    "brief.write": Object.freeze({ group: "family.scope_group.health", label: "family.scope.brief_write" }),
    "brief.export": Object.freeze({ group: "family.scope_group.export", label: "family.scope.brief_export" }),
    "vault.export": Object.freeze({ group: "family.scope_group.export", label: "family.scope.vault_export" }),
    "relationship.read": Object.freeze({ group: "family.scope_group.family", label: "family.scope.relationship_read" }),
    "relationship.manage": Object.freeze({ group: "family.scope_group.family", label: "family.scope.relationship_manage" }),
    "access.read": Object.freeze({ group: "family.scope_group.family", label: "family.scope.access_read" }),
    "access.manage": Object.freeze({ group: "family.scope_group.family", label: "family.scope.access_manage" }),
    "chat.use": Object.freeze({ group: "family.scope_group.chat", label: "family.scope.chat_use" }),
  });
  const OPTIONAL_SCOPES_BY_GENERATION = Object.freeze({
    v1: Object.freeze(["source.write", "candidate.review", "medication.write", "visit.write", "brief.write", "brief.export", "vault.export"]),
    v2: Object.freeze(["source.write", "candidate.review", "medication.write", "visit.write", "brief.write", "brief.export", "vault.export", "condition.write", "lab.write"]),
    v3: Object.freeze(["source.write", "candidate.review", "medication.write", "visit.write", "brief.write", "brief.export", "vault.export", "condition.write", "lab.write", "document.write"]),
  });
  const inferPolicyGeneration = (scopes) => {
    const values = new Set(Array.isArray(scopes) ? scopes : []);
    if (values.has("document.read") || values.has("document.write")) return "v3";
    if (["condition.read", "condition.write", "lab.read", "lab.write"].some((scope) => values.has(scope))) return "v2";
    return "v1";
  };

  const state = {
    me: null,
    people: [],
    actors: [],
    families: [],
    person: null,
    assignments: [],
    consents: [],
    audits: [],
    canReadAccess: false,
    canManageAccess: false,
    loadVersion: 0,
    controller: null,
    revisionOpener: null,
    revising: null,
    familyId: null,
  };

  const clear = (node) => node?.replaceChildren();
  const make = (tag, text = "", className = "") => {
    const node = document.createElement(tag);
    node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  const makeButton = (label, action, className = "") => {
    const node = make("button", label, className);
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  };
  const appendDefinition = (list, term, description, code = false) => {
    list.append(make("dt", term));
    const value = make("dd", description);
    if (code) value.className = "family-technical-value";
    list.append(value);
  };
  const status = (message, kind = "") => {
    const target = byId("family-access-status");
    target.textContent = message;
    target.className = kind ? `family-access-status ${kind}` : "family-access-status";
  };
  const focusStatus = () => {
    const target = byId("family-access-status");
    target.tabIndex = -1;
    target.focus();
  };
  const csrfToken = () => document.cookie.split("; ")
    .find((item) => item.startsWith("opencare_csrf="))
    ?.split("=").slice(1).join("=") || "";
  const securedOptions = (options = {}) => {
    const method = (options.method || "GET").toUpperCase();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) headers["X-OpenCare-CSRF"] = csrfToken();
    return { ...options, headers };
  };
  const safeError = (response) => {
    if (response.status === 401) return t("status.session_expired", "Your session has expired. Sign in again.");
    if (response.status === 403) return t("family.action_not_allowed", "Your account is not permitted to perform that action.");
    if (response.status === 404) return t("family.record_not_available", "That item is not available.");
    if (response.status === 409) return t("family.conflict", "That action conflicts with the current access state.");
    if (response.status === 422) return t("status.check_values", "Check the entered values and try again.");
    return t("status.request_failed", "The request could not be completed. Try again.");
  };
  class FamilyAccessRequestError extends Error {
    constructor(response) {
      super(safeError(response));
      this.name = "FamilyAccessRequestError";
      this.status = response.status;
    }
  }
  const responseIsCurrent = (context) => !context || (
    OpenCareWorkspaceState.shouldApplyResponse(context.generation, state.loadVersion)
    && context.personId === state.person?.person_id
  );
  const request = async (path, options = {}, context = null) => {
    const response = await fetch(path, {
      credentials: "same-origin",
      ...securedOptions(options),
      ...(context?.signal ? { signal: context.signal } : {}),
    });
    if (!responseIsCurrent(context)) throw new DOMException("Stale Family Access response", "AbortError");
    if (!response.ok) throw new FamilyAccessRequestError(response);
    if (response.status === 204) return null;
    const body = await response.json();
    if (!responseIsCurrent(context)) throw new DOMException("Stale Family Access response", "AbortError");
    return body;
  };
  const personContext = () => ({
    generation: state.loadVersion,
    personId: state.person?.person_id || "",
    signal: state.controller?.signal,
  });
  const personRequest = (path, options = {}) => request(path, options, personContext());
  const authorizedPerson = (personId) => state.people.find((person) => person.person_id === personId) || null;
  const personName = (personId) => authorizedPerson(personId)?.display_name || t("family.record_not_available", "That item is not available.");
  const actorFor = (actorId) => {
    if (state.me?.actor?.actor_id === actorId) return state.me.actor;
    return state.actors.find((actor) => actor.actor_id === actorId) || null;
  };
  const actorName = (actorId) => actorFor(actorId)?.display_name || t("family.shared_account", "Account with access");
  const actorSecondary = (actorId) => actorFor(actorId)?.username || "";
  const roleLabel = (role) => role === "owner" ? t("family.role_owner", "Owner") : t("family.role_caregiver", "Caregiver");
  const relationshipLabel = (value) => t(`family.relationship_${value}`, value);

  const setOptions = (select, items, placeholder, valueKey, labelKey) => {
    const selected = select.value;
    const option = make("option", placeholder);
    option.value = "";
    select.replaceChildren(option);
    items.forEach((item) => {
      const itemOption = make("option", item[labelKey]);
      itemOption.value = item[valueKey];
      select.append(itemOption);
    });
    if (items.some((item) => item[valueKey] === selected)) select.value = selected;
    select.disabled = items.length === 0;
  };
  const selectedScopes = (fieldsetId) => Array.from(
    byId(fieldsetId).querySelectorAll("input[type=checkbox]:checked:not(:disabled)"),
    (input) => input.value,
  );
  const renderScopeOptions = (fieldsetId, generation = "v3", selected = []) => {
    const fieldset = byId(fieldsetId);
    const container = fieldset.querySelector(".family-scope-options");
    clear(container);
    OPTIONAL_SCOPES_BY_GENERATION[generation].forEach((scope) => {
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = scope;
      input.checked = selected.includes(scope);
      const label = make("label");
      label.append(input, document.createTextNode(t(SCOPE_PRESENTATION[scope].label, scope)));
      container.append(label);
    });
  };
  const setRoleControls = (prefix, role) => {
    const fieldset = byId(`${prefix}-caregiver-scopes`);
    fieldset.disabled = role === "owner";
    const confirmation = prefix === "grant" ? byId("grant-owner-confirmation") : byId("confirm-full-owner-access");
    confirmation.required = role === "owner";
    confirmation.closest("label").hidden = role !== "owner";
    if (role !== "owner") confirmation.checked = false;
  };
  const scopeSummary = (scopes) => {
    const container = make("div", "", "family-scope-summary");
    const groups = new Map();
    (Array.isArray(scopes) ? scopes : []).forEach((scope) => {
      const presentation = SCOPE_PRESENTATION[scope];
      if (!presentation) return;
      if (!groups.has(presentation.group)) groups.set(presentation.group, []);
      groups.get(presentation.group).push(presentation.label);
    });
    groups.forEach((labels, group) => {
      const section = make("div", "", "family-scope-group");
      section.append(make("h4", t(group, group)));
      const list = make("ul");
      labels.forEach((label) => list.append(make("li", t(label, label))));
      section.append(list);
      container.append(section);
    });
    return container;
  };
  const clearInvitation = () => {
    byId("issued-invitation-code").textContent = "";
    byId("issued-invitation").hidden = true;
    byId("invitation-empty").hidden = false;
  };
  const clearRevision = (restoreFocus = false) => {
    const opener = state.revisionOpener;
    state.revising = null;
    state.revisionOpener = null;
    byId("revise-access-form").hidden = true;
    byId("revise-access-form").reset();
    if (restoreFocus) opener?.focus();
  };
  const updateShellPerson = (person) => {
    const statusTarget = byId("product-shell-person-status");
    const container = byId("product-shell-person");
    if (statusTarget) statusTarget.textContent = person ? person.display_name : t("person.no_selection", "No person selected");
    if (container) container.dataset.activePersonId = person?.person_id || "";
  };
  const resetScopedState = () => {
    state.assignments = [];
    state.consents = [];
    state.audits = [];
    state.canReadAccess = false;
    state.canManageAccess = false;
    clearRevision();
  };

  const renderPersonContext = () => {
    const selected = state.person;
    byId("family-person-workspace").hidden = !selected;
    byId("family-no-person").hidden = Boolean(selected);
    byId("clear-family-person").hidden = !selected;
    const emptyPeople = state.people.length === 0;
    byId("selected-access-person").textContent = selected?.display_name || (
      emptyPeople
        ? t("family.no_accessible_people", "No accessible People")
        : t("family.no_active_person", "No Person selected")
    );
    byId("selected-access-person-detail").textContent = selected
      ? tf("family.access_applies_to", { person: selected.display_name }, "Access shown here applies to {person}.")
      : emptyPeople
        ? t("family.no_accessible_people", "No accessible People")
        : t("family.choose_person", "Choose an authorized Person to review family access.");
    byId("family-no-person-heading").textContent = emptyPeople
      ? t("family.no_accessible_people", "No accessible People")
      : t("family.no_active_person", "No Person selected");
    byId("family-no-person-help").textContent = emptyPeople
      ? t("family.no_accessible_people", "No accessible People")
      : t("family.choose_person", "Choose an authorized Person to review family access.");
    byId("share-access-to-person").textContent = selected
      ? tf("family.share_access_to", { person: selected.display_name }, "Share access to {person}")
      : "";
    byId("access-person-selector").value = selected?.person_id || "";
    updateShellPerson(selected);
  };
  const renderAccount = () => {
    const list = byId("current-actor");
    clear(list);
    if (!state.me?.actor) return;
    appendDefinition(list, t("form.display_name", "Display name"), state.me.actor.display_name || "");
    appendDefinition(list, t("form.username", "Username"), state.me.actor.username || "");
  };
  const renderTechnicalContext = () => {
    const list = byId("technical-context-list");
    clear(list);
    if (state.me?.actor) appendDefinition(list, t("family.actor_id", "Actor ID"), state.me.actor.actor_id, true);
    if (state.person) appendDefinition(list, t("family.person_id", "Person ID"), state.person.person_id, true);
  };

  const renderAssignments = () => {
    const ordinary = byId("assignment-list");
    const raw = byId("raw-assignment-list");
    clear(ordinary);
    clear(raw);
    byId("family-access-read-only").hidden = state.canReadAccess;
    byId("grant-access-form").hidden = !state.canManageAccess;
    byId("create-invitation-form").hidden = !state.canManageAccess;
    byId("no-additional-access").hidden = true;
    if (!state.canReadAccess) return;

    const activeAssignments = state.assignments.filter((assignment) => assignment.is_active);
    activeAssignments.forEach((assignment) => {
      const record = make("article", "", "family-access-card");
      const heading = make("div", "", "family-access-card__identity");
      const resolvedName = actorName(assignment.actor_id);
      heading.append(make("h3", state.me?.actor?.actor_id === assignment.actor_id
        ? `${resolvedName} (${t("family.you", "You")})`
        : resolvedName));
      const secondary = actorSecondary(assignment.actor_id);
      if (secondary) heading.append(make("p", secondary, "meta"));
      const roleStatus = make("p", `${roleLabel(assignment.role)} · ${t("family.status_active", "Active")}`, "family-access-card__status");
      record.append(heading, roleStatus, scopeSummary(assignment.scopes));
      if (state.canManageAccess) {
        const actions = make("div", "", "family-card-actions");
        if (assignment.role === "caregiver") {
          const revise = makeButton(t("family.revise_access", "Revise access"), () => {
            clearRevision();
            state.revising = assignment;
            state.revisionOpener = revise;
            byId("revise-access-label").textContent = resolvedName;
            renderScopeOptions("revise-caregiver-scopes", inferPolicyGeneration(assignment.scopes), assignment.scopes);
            byId("revise-access-form").hidden = false;
            byId("revise-access-form").querySelector("input:not(:disabled), button:not(:disabled)")?.focus();
          }, "button-secondary");
          actions.append(revise);
        }
        actions.append(makeButton(t("family.revoke_access", "Revoke access"), async () => {
          if (!window.confirm(tf("family.revoke_confirm", { name: resolvedName }, "Revoke access for {name}? The final active owner cannot be removed."))) return;
          try {
            await personRequest(`${familyApi}/people/${encodeURIComponent(state.person.person_id)}/access-assignments/${encodeURIComponent(assignment.assignment_id)}:revoke`, { method: "POST", body: "{}" });
            await loadPersonAccess();
            status(t("family.access_revoked", "Access revoked."), "success");
            focusStatus();
          } catch (error) { handleError(error); }
        }, "family-action-danger"));
        record.append(actions);
      }
      ordinary.append(record);
    });
    const additional = activeAssignments.filter((assignment) => assignment.actor_id !== state.me?.actor?.actor_id);
    byId("no-additional-access").hidden = additional.length !== 0;

    state.assignments.forEach((assignment) => {
      const record = make("article", "", "family-technical-record");
      const list = make("dl");
      appendDefinition(list, t("family.assignment_id", "Assignment ID"), assignment.assignment_id, true);
      appendDefinition(list, t("family.actor_id", "Actor ID"), assignment.actor_id, true);
      appendDefinition(list, t("family.person_id", "Person ID"), assignment.person_id, true);
      appendDefinition(list, t("family.role_label", "Role"), roleLabel(assignment.role));
      appendDefinition(list, t("family.status_active", "Active"), assignment.is_active ? t("family.status_active", "Active") : t("family.status_revoked", "Revoked"));
      appendDefinition(list, t("family.raw_scopes", "Exact scopes"), (assignment.scopes || []).slice().sort().join("\n"), true);
      record.append(list);
      raw.append(record);
    });
  };

  const renderConsents = () => {
    const target = byId("consent-list");
    clear(target);
    if (!state.canReadAccess || state.consents.length === 0) {
      target.append(make("p", t("family.no_consent_history", "No visible consent history.")));
      return;
    }
    state.consents.forEach((consent) => {
      const record = make("article", "", "family-technical-record");
      const list = make("dl");
      appendDefinition(list, t("family.consent_id", "Consent event ID"), consent.consent_event_id, true);
      appendDefinition(list, t("family.actor_id", "Actor ID"), consent.recipient_actor_id, true);
      appendDefinition(list, t("family.person_id", "Person ID"), consent.person_id, true);
      appendDefinition(list, t("family.role_label", "Role"), roleLabel(consent.role));
      appendDefinition(list, t("family.created_at", "Created at"), consent.created_at || "");
      appendDefinition(list, t("family.raw_scopes", "Exact scopes"), (consent.scopes || []).slice().sort().join("\n"), true);
      appendDefinition(list, "event_type", consent.event_type || "", true);
      appendDefinition(list, "reason_code", consent.reason_code || "", true);
      record.append(list);
      target.append(record);
    });
  };
  const renderAudits = () => {
    const target = byId("access-audit-list");
    clear(target);
    if (!state.canReadAccess || state.audits.length === 0) {
      target.append(make("p", t("family.no_access_audit", "No visible access audit events.")));
      return;
    }
    state.audits.forEach((audit) => {
      const record = make("article", "", "family-technical-record");
      const list = make("dl");
      appendDefinition(list, t("family.audit_id", "Audit event ID"), audit.audit_event_id, true);
      appendDefinition(list, t("family.actor_id", "Actor ID"), audit.actor_id || "", true);
      appendDefinition(list, t("family.created_at", "Created at"), audit.created_at || "");
      appendDefinition(list, "action_code", audit.action_code || "", true);
      appendDefinition(list, "target_class", audit.target_class || "", true);
      appendDefinition(list, "target_id", audit.target_id || "", true);
      appendDefinition(list, "outcome", audit.outcome || "", true);
      appendDefinition(list, "reason_code", audit.reason_code || "", true);
      record.append(list);
      target.append(record);
    });
  };
  const renderAccess = () => {
    renderPersonContext();
    renderTechnicalContext();
    renderAssignments();
    renderConsents();
    renderAudits();
  };

  const refreshPeople = async (existingPayload = null) => {
    const payload = existingPayload || await request(`${productApi}/people`);
    state.people = Array.isArray(payload.people) ? payload.people : [];
    setOptions(byId("access-person-selector"), state.people, state.people.length
      ? t("person.no_selection", "No person selected")
      : t("family.no_accessible_people", "No accessible People"), "person_id", "display_name");
    setOptions(byId("family-member-person"), state.people, t("person.choose", "Choose a person"), "person_id", "display_name");
    setOptions(byId("relationship-person"), state.people, t("person.choose", "Choose a person"), "person_id", "display_name");
    setOptions(byId("relationship-related-person"), state.people, t("family.related_person", "Related Person"), "person_id", "display_name");
    return state.people;
  };
  const clearActivePerson = async (persist = true) => {
    state.loadVersion += 1;
    const clearGeneration = state.loadVersion;
    state.controller?.abort();
    state.controller = new AbortController();
    const context = personContext();
    clearInvitation();
    if (persist) {
      await request(`${familyApi}/active-person`, {
        method: "PUT",
        body: JSON.stringify({ person_id: null }),
      }, context);
    }
    if (!OpenCareWorkspaceState.shouldApplyResponse(clearGeneration, state.loadVersion)) return;
    state.person = null;
    state.controller = null;
    resetScopedState();
    renderAccess();
  };
  const deniedAssignmentRead = async (error, selectedId, generation) => {
    if (![403, 404].includes(error.status)) throw error;
    const people = await refreshPeople();
    if (!OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion) || state.person?.person_id !== selectedId) return;
    if (people.some((person) => person.person_id === selectedId)) {
      clearInvitation();
      resetScopedState();
      state.person = authorizedPerson(selectedId);
      renderAccess();
      status(error.message, "error");
      return;
    }
    await clearActivePerson(true);
    status(t("family.record_not_available", "That item is not available."), "error");
  };
  async function loadPersonAccess() {
    if (!state.person) {
      resetScopedState();
      renderAccess();
      return;
    }
    const selectedId = state.person.person_id;
    const generation = state.loadVersion;
    const context = personContext();
    resetScopedState();
    renderAccess();
    status(t("family.loading_access", "Loading Family Access…"));
    try {
      const assignmentsPayload = await request(`${familyApi}/people/${encodeURIComponent(selectedId)}/access-assignments`, {}, context);
      if (!responseIsCurrent(context)) return;
      state.assignments = (assignmentsPayload.assignments || []).filter((assignment) => assignment.person_id === selectedId);
      state.canReadAccess = true;
      state.canManageAccess = state.assignments.some((assignment) => (
        assignment.actor_id === state.me?.actor?.actor_id
        && assignment.is_active
        && Array.isArray(assignment.scopes)
        && assignment.scopes.includes("access.manage")
      ));
      const [consentsPayload, auditsPayload] = await Promise.all([
        request(`${familyApi}/people/${encodeURIComponent(selectedId)}/consents`, {}, context),
        request(`${familyApi}/people/${encodeURIComponent(selectedId)}/access-audit`, {}, context),
      ]);
      if (!responseIsCurrent(context)) return;
      state.consents = (consentsPayload.consents || []).filter((consent) => consent.person_id === selectedId);
      state.audits = auditsPayload.audit_events || [];
      renderAccess();
      status(t("family.access_ready", "Family Access loaded."), "success");
    } catch (error) {
      if (error.name === "AbortError") return;
      if ([403, 404].includes(error.status)) {
        await deniedAssignmentRead(error, selectedId, generation);
        return;
      }
      if (OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion)) {
        resetScopedState();
        renderAccess();
        status(error.message, "error");
      }
    }
  }
  const selectPerson = async (personId) => {
    state.loadVersion += 1;
    state.controller?.abort();
    state.controller = new AbortController();
    clearInvitation();
    clearRevision();
    const person = authorizedPerson(personId);
    if (!person) {
      await clearActivePerson(true);
      status(t("family.record_not_available", "That item is not available."), "error");
      return;
    }
    state.person = person;
    const context = personContext();
    renderPersonContext();
    try {
      await request(`${familyApi}/active-person`, { method: "PUT", body: JSON.stringify({ person_id: person.person_id }) }, context);
      if (!responseIsCurrent(context)) return;
      await loadPersonAccess();
    } catch (error) {
      if (error.name === "AbortError") return;
      state.person = null;
      resetScopedState();
      renderAccess();
      status(error.message, "error");
    }
  };

  const renderActors = () => {
    const section = byId("actor-list");
    const target = byId("actor-records");
    clear(target);
    section.hidden = state.actors.length === 0;
    state.actors.forEach((actor) => {
      const record = make("article", "", "family-technical-record");
      record.append(make("h3", actor.display_name || t("family.shared_account", "Account with access")));
      const list = make("dl");
      appendDefinition(list, t("form.username", "Username"), actor.username || "");
      appendDefinition(list, t("family.actor_id", "Actor ID"), actor.actor_id, true);
      appendDefinition(list, t("family.created_at", "Created at"), actor.created_at || "");
      appendDefinition(list, t("family.status_active", "Active"), actor.status === "active" ? t("family.status_active", "Active") : t("family.status_disabled", "Disabled"));
      record.append(list);
      if (actor.status === "active" && actor.actor_id !== state.me?.actor?.actor_id) {
        record.append(makeButton(t("family.deactivate_actor", "Deactivate account"), async () => {
          if (!window.confirm(tf("family.deactivate_confirm", { name: actor.display_name || actor.username || t("family.shared_account", "Account with access") }, "Deactivate {name} and revoke all of their Person access?"))) return;
          try {
            await request(`${familyApi}/actors/${encodeURIComponent(actor.actor_id)}:deactivate`, { method: "POST", body: "{}" });
            state.actors = state.actors.map((item) => item.actor_id === actor.actor_id ? { ...item, status: "disabled" } : item);
            renderActors();
            focusStatus();
          } catch (error) { handleError(error); }
        }, "family-action-danger"));
      }
      target.append(record);
    });
  };

  const renderFamily = async () => {
    state.familyId = byId("family-selector").value || null;
    const details = byId("family-details");
    clear(details);
    byId("add-family-member-form").hidden = !state.familyId;
    byId("create-relationship-form").hidden = !state.familyId;
    if (!state.familyId) {
      details.append(make("p", t("family.no_family_selected", "No Family selected.")));
      return;
    }
    const requestedFamilyId = state.familyId;
    try {
      const payload = await request(`${familyApi}/families/${encodeURIComponent(requestedFamilyId)}`);
      if (state.familyId !== requestedFamilyId) return;
      details.append(make("h3", payload.family.display_name));
      const familyMeta = make("dl");
      appendDefinition(familyMeta, t("family.family_id", "Family ID"), payload.family.family_id, true);
      details.append(familyMeta);
      if (payload.memberships.length === 0) details.append(make("p", t("family.no_family_members", "No visible Family members.")));
      payload.memberships.forEach((membership) => {
        const record = make("article", "", "family-technical-record");
        record.append(make("h4", personName(membership.person_id)));
        const list = make("dl");
        appendDefinition(list, t("family.membership_id", "Membership ID"), membership.membership_id, true);
        appendDefinition(list, t("family.person_id", "Person ID"), membership.person_id, true);
        record.append(list, makeButton(t("family.end_membership", "End membership"), async () => {
          try {
            await request(`${familyApi}/families/${encodeURIComponent(requestedFamilyId)}/memberships/${encodeURIComponent(membership.membership_id)}:end`, { method: "POST", body: "{}" });
            await renderFamily();
            focusStatus();
          } catch (error) { handleError(error); }
        }, "family-action-danger"));
        details.append(record);
      });
      payload.relationships.forEach((relationship) => {
        const record = make("article", "", "family-technical-record");
        record.append(make("h4", `${personName(relationship.person_id)} · ${relationshipLabel(relationship.relationship_type)} · ${personName(relationship.related_person_id)}`));
        const list = make("dl");
        appendDefinition(list, t("family.relationship_id", "Relationship ID"), relationship.relationship_id, true);
        appendDefinition(list, t("family.person_id", "Person ID"), relationship.person_id, true);
        appendDefinition(list, t("family.related_person", "Related Person"), relationship.related_person_id, true);
        record.append(list, makeButton(t("family.end_relationship", "End relationship"), async () => {
          try {
            await request(`${familyApi}/families/${encodeURIComponent(requestedFamilyId)}/relationships/${encodeURIComponent(relationship.relationship_id)}:end`, { method: "POST", body: "{}" });
            await renderFamily();
            focusStatus();
          } catch (error) { handleError(error); }
        }, "family-action-danger"));
        details.append(record);
      });
    } catch (error) { details.append(make("p", error.message, "error")); }
  };
  const renderFamilies = () => setOptions(
    byId("family-selector"), state.families, t("family.no_family_selected", "No Family selected."), "family_id", "display_name",
  );
  const handleError = (error) => {
    if (error.name !== "AbortError") status(error.message || t("status.request_failed", "The request could not be completed. Try again."), "error");
  };

  const load = async () => {
    status(t("status.loading", "Loading…"));
    try {
      state.me = await request(`${familyApi}/me`);
      renderAccount();
      renderTechnicalContext();
      const [peoplePayload, familiesPayload] = await Promise.all([
        request(`${productApi}/people`),
        request(`${familyApi}/families`),
      ]);
      state.families = familiesPayload.families || [];
      await refreshPeople(peoplePayload);
      renderFamilies();
      renderScopeOptions("grant-caregiver-scopes", "v3");
      renderScopeOptions("invitation-caregiver-scopes", "v3");
      setRoleControls("grant", byId("grant-role").value);
      setRoleControls("invitation", byId("invitation-role-select").value);
      try {
        const actorsPayload = await request(`${familyApi}/actors`);
        state.actors = actorsPayload.actors || [];
      } catch (_) {
        state.actors = [];
      }
      renderActors();
      const initialPerson = authorizedPerson(state.me.active_person_id);
      if (initialPerson) {
        state.person = initialPerson;
        state.loadVersion += 1;
        state.controller = new AbortController();
        renderPersonContext();
        await loadPersonAccess();
      } else {
        state.person = null;
        resetScopedState();
        renderAccess();
        status(t("status.ready", "Ready"), "success");
      }
    } catch (error) { handleError(error); }
  };

  byId("access-person-selector").addEventListener("change", (event) => {
    const personId = event.currentTarget.value;
    if (personId) void selectPerson(personId);
    else void clearActivePerson(true).then(() => status(t("family.clear_person", "Clear Person"), "success")).catch(handleError);
  });
  byId("clear-family-person").addEventListener("click", () => {
    void clearActivePerson(true).then(() => status(t("family.clear_person", "Clear Person"), "success")).catch(handleError);
  });
  byId("family-selector").addEventListener("change", () => { void renderFamily(); });
  byId("grant-role").addEventListener("change", (event) => setRoleControls("grant", event.currentTarget.value));
  byId("invitation-role-select").addEventListener("change", (event) => setRoleControls("invitation", event.currentTarget.value));

  byId("grant-access-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.person || !state.canManageAccess) return;
    const form = event.currentTarget;
    const role = byId("grant-role").value;
    try {
      await personRequest(`${familyApi}/people/${encodeURIComponent(state.person.person_id)}/access-assignments`, {
        method: "POST",
        body: JSON.stringify({
          recipient_actor_id: byId("grant-actor-id").value,
          role,
          optional_scopes: role === "caregiver" ? selectedScopes("grant-caregiver-scopes") : [],
          confirm_full_owner_access: role === "owner" && byId("grant-owner-confirmation").checked,
        }),
      });
      form.reset();
      renderScopeOptions("grant-caregiver-scopes", "v3");
      setRoleControls("grant", "caregiver");
      await loadPersonAccess();
      status(t("family.access_granted", "Access granted."), "success");
    } catch (error) { handleError(error); }
  });
  byId("revise-access-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.person || !state.revising || !state.canManageAccess) return;
    const assignment = state.revising;
    try {
      await personRequest(`${familyApi}/people/${encodeURIComponent(state.person.person_id)}/access-assignments/${encodeURIComponent(assignment.assignment_id)}:revise`, {
        method: "POST",
        body: JSON.stringify({ optional_scopes: selectedScopes("revise-caregiver-scopes") }),
      });
      clearRevision();
      await loadPersonAccess();
      status(t("family.access_revised", "Access updated."), "success");
      focusStatus();
    } catch (error) { handleError(error); }
  });
  byId("cancel-access-revision").addEventListener("click", () => clearRevision(true));
  byId("create-invitation-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.person || !state.canManageAccess) return;
    const form = event.currentTarget;
    const role = byId("invitation-role-select").value;
    const expiry = new Date(byId("invitation-expiry").value);
    try {
      const issued = await personRequest(`${familyApi}/people/${encodeURIComponent(state.person.person_id)}/invitations`, {
        method: "POST",
        body: JSON.stringify({
          role,
          optional_scopes: role === "caregiver" ? selectedScopes("invitation-caregiver-scopes") : [],
          expires_at: expiry.toISOString(),
          confirm_full_owner_access: role === "owner" && byId("confirm-full-owner-access").checked,
        }),
      });
      byId("issued-invitation-code").textContent = issued.secret;
      byId("issued-invitation").hidden = false;
      byId("invitation-empty").hidden = true;
      form.reset();
      renderScopeOptions("invitation-caregiver-scopes", "v3");
      setRoleControls("invitation", "caregiver");
      status(t("family.invitation_created", "Invitation created. Copy the code now."), "success");
      byId("issued-invitation").focus();
    } catch (error) { handleError(error); }
  });
  byId("clear-invitation-code").addEventListener("click", () => {
    clearInvitation();
    status(t("family.code_cleared", "Invitation code cleared from this page."));
  });

  byId("create-family-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      const family = await request(`${familyApi}/families`, { method: "POST", body: JSON.stringify({ display_name: byId("family-display-name").value }) });
      state.families.push(family);
      renderFamilies();
      byId("family-selector").value = family.family_id;
      form.reset();
      await renderFamily();
    } catch (error) { handleError(error); }
  });
  byId("add-family-member-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await request(`${familyApi}/families/${encodeURIComponent(state.familyId)}/memberships`, { method: "POST", body: JSON.stringify({ person_id: byId("family-member-person").value }) });
      await renderFamily();
    } catch (error) { handleError(error); }
  });
  byId("create-relationship-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await request(`${familyApi}/families/${encodeURIComponent(state.familyId)}/relationships`, {
        method: "POST",
        body: JSON.stringify({
          person_id: byId("relationship-person").value,
          related_person_id: byId("relationship-related-person").value,
          relationship_type: byId("relationship-type").value,
        }),
      });
      await renderFamily();
    } catch (error) { handleError(error); }
  });
  byId("change-password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await request(`${familyApi}/password:change`, {
        method: "POST",
        body: JSON.stringify({ current_password: byId("current-password").value, new_password: byId("new-password").value }),
      });
      form.reset();
      clearInvitation();
      status(t("family.password_changed", "Password changed. Sign in again."), "success");
      window.location.assign("/login");
    } catch (_) {
      form.reset();
      status(t("family.password_change_failed", "The password could not be changed. Check the current password and try again."), "error");
    }
  });
  byId("actor-logout").addEventListener("click", async () => {
    try {
      await request(`${familyApi}/logout`, { method: "POST", body: "{}" });
      byId("change-password-form").reset();
      clearInvitation();
      status(t("family.signed_out", "Signed out."), "success");
      window.location.assign("/login");
    } catch (error) { handleError(error); }
  });

  void load();
})();
