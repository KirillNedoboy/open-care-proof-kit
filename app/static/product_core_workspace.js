(() => {
  "use strict";

  const api = "/api/product-core/v1";
  const state = { person: null, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], conditionCandidates: [], labCandidates: [], conditionEnabled: false, labEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null, loadVersion: 0, controller: null };
  const byId = (id) => document.getElementById(id);
  const translationPayload = byId("product-shell-translations");
  let translations = {};
  try {
    const parsed = JSON.parse(translationPayload?.textContent || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) translations = parsed;
  } catch (_) {}
  const t = (key, fallback = key) => typeof translations[key] === "string" && translations[key] ? translations[key] : fallback;
  const updateShellPerson = (person) => {
    const target = byId("product-shell-person-status");
    if (!target) return;
    target.textContent = person ? `${t("workspace.viewing")} ${person.display_name}` : t("person.no_selection");
  };
  const make = (tag, value = "", className = "") => { const node = document.createElement(tag); node.textContent = value; node.className = className; return node; };
  const div = (id) => { const node = document.createElement("div"); node.id = id; return node; };
  const clear = (node) => node.replaceChildren();
  const status = (message, kind = "") => { const target = byId("workspace-status"); target.textContent = message; target.className = kind ? `workspace-status ${kind}` : "workspace-status"; };
  const safeError = (response, body) => {
    if (response.status === 401) return t("status.session_expired", "Your session has expired. Sign in again.");
    if (response.status === 403) return t("status.action_unavailable", "This action is no longer available.");
    if (response.status === 404) return t("workspace.person_not_available", "This Person is not available.");
    if (response.status === 409) return t("status.record_changed", "This record changed. Refresh to see the latest version.");
    if (response.status === 422) return t("status.check_values", "Check the entered values and try again.");
    if (body?.error?.code === "product_core_integrity_failure") return t("status.integrity_failure", "Integrity: stored evidence could not be verified.");
    if (body?.error?.code === "product_core_storage_unavailable") return t("status.storage_unavailable", "Local Product Core storage is unavailable. Try again shortly.");
    return t("status.request_failed", "The request could not be completed. Try again.");
  };
  class WorkspaceRequestError extends Error {
    constructor(response, body) {
      super(safeError(response, body));
      this.name = "WorkspaceRequestError";
      this.status = response.status;
      this.code = body?.error?.code || "";
    }
  }
  const isMutation = (options) => ["POST", "PUT", "PATCH", "DELETE"].includes((options.method || "GET").toUpperCase());
  const csrfToken = () => document.cookie.split("; ").find((item) => item.startsWith("opencare_csrf="))?.split("=").slice(1).join("=") || "";
  const securedOptions = (options = {}) => {
    const method = (options.method || "GET").toUpperCase();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) headers["X-OpenCare-CSRF"] = csrfToken();
    return { ...options, headers };
  };
  const labelled = (label, control) => { const element = document.createElement("label"); element.textContent = label; element.append(control); return element; };
  const currentPersonContext = () => ({ personId: state.person?.person_id || "", generation: state.loadVersion, signal: state.controller?.signal });
  const personRequest = (path, options = {}) => request(path, options, currentPersonContext());

  async function request(path, options = {}, personContext = null) {
    const response = await fetch(api + path, { credentials: "same-origin", ...securedOptions(options), ...(personContext?.signal ? { signal: personContext.signal } : {}) });
    if (personContext && (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id)) throw new DOMException("Stale workspace response", "AbortError");
    let body;
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) {
      const error = new WorkspaceRequestError(response, body);
      if (personContext && isMutation(options)) await refreshCapabilitiesAfterDenial(error, personContext);
      throw error;
    }
    if (personContext && (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id)) throw new DOMException("Stale workspace response", "AbortError");
    return body;
  }

  async function requestText(path, options = {}, personContext = null) {
    const response = await fetch(api + path, { credentials: "same-origin", ...securedOptions(options), ...(personContext?.signal ? { signal: personContext.signal } : {}) });
    if (personContext && (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id)) throw new DOMException("Stale workspace response", "AbortError");
    if (!response.ok) {
      let body;
      try { body = await response.json(); } catch (_) {}
      const error = new WorkspaceRequestError(response, body);
      if (personContext && isMutation(options)) await refreshCapabilitiesAfterDenial(error, personContext);
      throw error;
    }
    const text = await response.text();
    if (personContext && (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id)) throw new DOMException("Stale workspace response", "AbortError");
    return text;
  }

  async function requestBlob(path, options = {}, personContext = null) {
    const response = await fetch(api + path, { credentials: "same-origin", ...securedOptions(options), ...(personContext?.signal ? { signal: personContext.signal } : {}) });
    if (personContext && (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id)) throw new DOMException("Stale workspace response", "AbortError");
    if (!response.ok) {
      let body;
      try { body = await response.json(); } catch (_) {}
      const error = new WorkspaceRequestError(response, body);
      if (personContext && isMutation(options)) await refreshCapabilitiesAfterDenial(error, personContext);
      throw error;
    }
    const blob = await response.blob();
    if (personContext && (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id)) throw new DOMException("Stale workspace response", "AbortError");
    return { blob, response };
  }

  function documentContext() {
    return { personId: state.person?.person_id || "", generation: state.loadVersion, signal: state.controller?.signal };
  }
  function documentCandidateAllowed(type = byId("document-candidate-type")?.value) {
    return Boolean(state.capabilities.document_read && state.capabilities.candidate_review && state.capabilities[`${type}_write`] && state.capabilities[`${type}_read`]);
  }
  async function sha256Hex(value) {
    const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
    return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  async function loadDocumentPage(document, pageNumber, trigger) {
    if (!document || !state.capabilities.document_read) return;
    try {
      const page = await personRequest(`/people/${encodeURIComponent(state.person.person_id)}/documents/${encodeURIComponent(document.source_id)}/extractions/${encodeURIComponent(document.extraction.extraction_id)}/pages/${pageNumber}`);
      if (page.source_id !== state.selectedDocument?.source_id || document.person_id !== state.person?.person_id) return;
      state.selectedPage = page; state.selectedSpan = null; renderDocumentViewer(); byId("document-page-text").focus();
    } catch (error) { if (error.name !== "AbortError") { status(error.message, "error"); trigger?.focus(); } }
  }
  function renderDocumentViewer() {
    const viewer = byId("document-viewer"), doc = state.selectedDocument;
    viewer.hidden = !doc;
    if (!doc) return;
    byId("document-viewer-title").textContent = doc.original_filename || "Document page text";
    byId("document-viewer-provenance").textContent = `${doc.document_kind === "pdf" ? "PDF" : "Plain text"} · ${doc.size_bytes} bytes · SHA-256 ${doc.content_hash}`;
    const select = byId("document-page-selector"); clear(select);
    for (let page = 1; page <= doc.extraction.page_count; page += 1) { const option = document.createElement("option"); option.value = page; option.textContent = `Page ${page}`; option.selected = page === state.selectedPage?.page_number; select.append(option); }
    byId("document-page-text").value = state.selectedPage?.normalized_text || "Choose a page to inspect.";
    const span = state.selectedSpan;
    byId("document-selection").textContent = span
      ? `Selected page ${state.selectedPage?.page_number || "?"}, codepoints ${span.start}–${span.end}.`
      : "Select text to attach a precise source span.";
    byId("document-candidate-form").hidden = !span || !documentCandidateAllowed();
  }
  function renderDocuments() {
    const section = byId("documents"), list = byId("document-list"); section.hidden = !state.capabilities.document_read; clear(list);
    byId("document-upload-panel").hidden = !(state.capabilities.document_write && state.capabilities.source_write);
    byId("documents-empty").hidden = state.documents.length > 0;
    state.documents.forEach((doc) => { const card = make("article", "", "record"), button = make("button", doc.original_filename || "Open document"); button.type = "button"; button.addEventListener("click", () => { state.selectedDocument = doc; state.selectedPage = null; state.selectedSpan = null; renderDocumentViewer(); void loadDocumentPage(doc, 1, button); }); card.append(make("strong", doc.original_filename || "Untitled document"), make("p", `${doc.document_kind === "pdf" ? "PDF" : "Plain text"} · ${doc.extraction.page_count} page${doc.extraction.page_count === 1 ? "" : "s"} · Added ${doc.created_at}`, "meta"), button); list.append(card); });
    renderDocumentViewer();
  }
  async function loadDocuments(personIdContext) {
    if (!state.capabilities.document_read) { state.documents = []; return []; }
    const response = await request(`/people/${encodeURIComponent(personIdContext)}/documents`, {}, documentContext());
    if (response.documents.some((doc) => doc.person_id !== personIdContext)) return [];
    return response.documents;
  }
  async function uploadDocument(event) {
    event.preventDefault();
    if (!state.person || !state.capabilities.document_write || !state.capabilities.source_write) return;
    const file = byId("document-file").files[0], submit = event.submitter;
    if (!file) return;
    submit.disabled = true;
    try {
      const body = await file.arrayBuffer();
      const filename = OpenCareWorkspaceState.sanitizeDocumentFilename(file.name);
      await personRequest(`/people/${encodeURIComponent(state.person.person_id)}/documents`, { method: "POST", body, headers: { "Content-Type": file.type === "application/pdf" ? "application/pdf" : "text/plain", "X-OpenCare-Filename": filename } });
      event.target.reset(); await loadWorkspace(); status("Document uploaded.", "success");
    } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; }
  }
  async function submitDocumentCandidate(event) {
    event.preventDefault();
    const span = state.selectedSpan, type = byId("document-candidate-type").value;
    if (!state.person || !state.selectedDocument || !state.selectedPage || !span || !documentCandidateAllowed(type)) return;
    const submit = event.submitter; submit.disabled = true;
    const name = byId("document-candidate-name").value.trim(), detail = byId("document-candidate-detail").value.trim() || null;
    try {
      const pageText = state.selectedPage.normalized_text || "";
      const codepoints = Array.from(pageText);
      const selectedText = codepoints.slice(span.start, span.end).join("");
      const locator = {
        kind: "document_text_span",
        source_id: state.selectedDocument.source_id,
        content_hash: state.selectedDocument.content_hash,
        extraction_id: state.selectedDocument.extraction.extraction_id,
        page_number: state.selectedPage.page_number,
        start_codepoint: span.start,
        end_codepoint: span.end,
        selected_text_sha256: await sha256Hex(selectedText),
      };
      const sourceId = state.selectedDocument.source_id;
      if (type === "medication") { await personRequest("/candidates/medications", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: sourceId, display_name: name, schedule_text: detail, note: null, provenance_locator: locator }) }); }
      else if (type === "condition") { await personRequest("/candidates/conditions", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: sourceId, display_name: name, status_text: detail, onset_date: null, note: null, provenance_locator: locator }) }); }
      else { await personRequest("/candidates/labs", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: sourceId, test_name: name, result_text: detail || "", unit_text: null, reference_range_text: null, observed_date: null, source_flag_text: null, note: null, provenance_locator: locator }) }); }
      event.target.reset(); state.selectedSpan = null; await loadWorkspace(); status("Typed candidate is waiting for review.", "success");
    } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; }
  }

  function pruneWorkspaceToCapabilities() {
    if (!state.capabilities.medication_read) Object.assign(state, { candidates: [], medications: [] });
    if (!state.capabilities.condition_read) Object.assign(state, { conditionCandidates: [], conditions: [] });
    if (!state.capabilities.lab_read) Object.assign(state, { labCandidates: [], labs: [] });
    state.conditionEnabled = Boolean(state.capabilities.condition_read);
    state.labEnabled = Boolean(state.capabilities.lab_read);
    if (!state.capabilities.timeline_read) state.timeline = [];
    if (!state.capabilities.visit_read) Object.assign(state, { visits: [], visit: null, questions: [], editingQuestion: null });
    if (!state.capabilities.brief_read) Object.assign(state, { persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false });
    if (!Object.values(state.capabilities).some(Boolean)) state.sources = new Map();
  }

  async function refreshCapabilitiesAfterDenial(error, personContext) {
    if (!OpenCareWorkspaceState.shouldRefreshCapabilities(error.status)) return;
    if (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id) return;
    let capabilities = {};
    try {
      const response = await request(`/people/${encodeURIComponent(personContext.personId)}/workspace-capabilities`, {}, personContext);
      if (response.person_id === personContext.personId) capabilities = response.capabilities;
    } catch (refreshError) {
      if (refreshError.name === "AbortError") return;
    }
    if (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id) return;
    state.capabilities = capabilities;
    pruneWorkspaceToCapabilities();
    render();
    if (!Object.values(capabilities).some(Boolean)) enableWorkspace(false);
  }

  function enableWorkspace(enabled) {
    byId("workspace-content").hidden = !enabled;
    byId("section-navigation").hidden = !enabled;
    byId("workspace-content").setAttribute("aria-disabled", String(!enabled));
    byId("workspace-content").querySelectorAll("input, textarea, select, button").forEach((item) => { item.disabled = !enabled; });
    byId("edit-profile").disabled = !enabled || !state.capabilities.person_update;
  }

  function renderPeople(people) {
    const selector = byId("person-selector");
    const selectedId = state.person?.person_id || "";
    clear(selector);
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = people.length ? t("workspace.selector_placeholder") : t("workspace.selector_empty");
    selector.append(placeholder);
    people.forEach((person) => {
      const option = document.createElement("option");
      option.value = person.person_id;
      option.textContent = person.display_name;
      option.selected = person.person_id === selectedId;
      selector.append(option);
    });
    selector.disabled = false;
    byId("load-workspace").disabled = !selector.value;
  }

  function renderSelectionEmptyState(people) {
    const empty = byId("workspace-empty");
    const title = byId("workspace-empty-title");
    const detail = byId("workspace-empty-detail");
    if (!empty || !title || !detail) return;
    if (!people.length) {
      title.textContent = t("workspace.no_accessible_persons");
      detail.textContent = t("workspace.no_accessible_persons_help");
      empty.hidden = false;
    } else if (!state.person) {
      title.textContent = t("workspace.no_active_person");
      detail.textContent = t("workspace.choose_person");
      empty.hidden = false;
    } else {
      empty.hidden = true;
    }
  }

  async function refreshPeople(selectedPerson = state.person) {
    const response = await request("/people");
    const people = Array.isArray(response.people) ? response.people : [];
    if (selectedPerson && !people.some((person) => person.person_id === selectedPerson.person_id)) state.person = null;
    renderPeople(people);
    renderSelectionEmptyState(people);
    renderPersonContext();
    if (!people.length) {
      enableWorkspace(false);
      updateShellPerson(null);
      status("");
    } else if (!state.person) {
      const activeId = byId("product-shell-person")?.dataset.activePersonId || "";
      if (activeId && people.some((person) => person.person_id === activeId)) {
        byId("person-selector").value = activeId;
        byId("load-workspace").disabled = false;
        void loadWorkspace();
      } else {
        status("");
      }
    }
  }

  function renderPersonContext() {
    const target = byId("selected-person");
    const detail = byId("selected-person-detail");
    byId("clear-workspace").disabled = !state.person;
    if (!state.person) {
      target.textContent = t("workspace.no_profile_selected");
      detail.textContent = t("workspace.profile_choice_help");
      updateShellPerson(null);
      return;
    }
    target.textContent = state.person.display_name;
    detail.textContent = state.person.date_of_birth
      ? `${t("workspace.viewing")} ${state.person.display_name} · ${t("workspace.date_of_birth")}: ${state.person.date_of_birth}`
      : `${t("workspace.viewing")} ${state.person.display_name}`;
    updateShellPerson(state.person);
  }

  async function loadWorkspace() {
    const personId = byId("person-selector").value;
    if (!personId) { status(t("workspace.select_before_load"), "error"); return; }
    state.controller?.abort();
    const generation = ++state.loadVersion;
    state.controller = new AbortController();
    Object.assign(state, { person: { person_id: personId, display_name: t("workspace.loading_person") }, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], conditionCandidates: [], labCandidates: [], conditionEnabled: false, labEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null });
    enableWorkspace(false);
    renderPersonContext();
    const personContext = { personId, generation, signal: state.controller.signal };
    status(t("workspace.loading_workspace"));
    try {
      await setActivePerson(personId, personContext);
      const [person, capabilityResponse] = await Promise.all([
        request(`/people/${encodeURIComponent(personId)}`, {}, personContext),
        request(`/people/${encodeURIComponent(personId)}/workspace-capabilities`, {}, personContext),
      ]);
      if (!OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion) || person.person_id !== personId || capabilityResponse.person_id !== personId) return;
      state.person = person;
      state.capabilities = capabilityResponse.capabilities;
      const capabilities = state.capabilities;
      const loads = [];
      const add = (key, path) => loads.push(request(path, {}, personContext).then((body) => [key, body]));
      if (capabilities.medication_read) {
        add("medicationCandidates", `/people/${encodeURIComponent(personId)}/candidates`);
        add("medications", `/people/${encodeURIComponent(personId)}/medications?include_inactive=true`);
      }
      if (capabilities.condition_read) {
        add("conditionCandidates", `/people/${encodeURIComponent(personId)}/condition-candidates`);
        add("conditions", `/people/${encodeURIComponent(personId)}/conditions?include_inactive=true`);
      }
      if (capabilities.lab_read) {
        add("labCandidates", `/people/${encodeURIComponent(personId)}/lab-candidates`);
        add("labs", `/people/${encodeURIComponent(personId)}/labs?include_inactive=true`);
      }
      if (capabilities.timeline_read) add("timeline", `/people/${encodeURIComponent(personId)}/timeline`);
      if (capabilities.visit_read) add("visits", `/people/${encodeURIComponent(personId)}/visits`);
      const loaded = Object.fromEntries(await Promise.all(loads));
      if (capabilities.document_read) {
        const documentResponse = await loadDocuments(personId);
        if (!OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion)) return;
        state.documents = documentResponse || state.documents;
      }
      if (!OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion)) return;
      Object.assign(state, {
        candidates: (loaded.medicationCandidates?.candidates || []).filter((item) => item.fact_type === "medication" && item.person_id === personId),
        medications: (loaded.medications?.medications || []).filter((item) => item.person_id === personId),
        conditions: (loaded.conditions?.conditions || []).filter((item) => item.person_id === personId),
        labs: (loaded.labs?.labs || []).filter((item) => item.person_id === personId),
        conditionCandidates: (loaded.conditionCandidates?.candidates || []).filter((item) => item.person_id === personId),
        labCandidates: (loaded.labCandidates?.candidates || []).filter((item) => item.person_id === personId),
        conditionEnabled: Boolean(capabilities.condition_read),
        labEnabled: Boolean(capabilities.lab_read),
        timeline: (loaded.timeline?.events || []).filter((item) => item.person_id === personId),
        visits: OpenCareWorkspaceState.sortVisits((loaded.visits?.visits || []).filter((item) => item.person_id === personId)),
      });
      const sourceIds = new Set([...visibleCandidates(), ...state.medications, ...state.conditions, ...state.labs].map((item) => item.source_id).filter(Boolean));
      const sources = await Promise.all([...sourceIds].map(async (sourceId) => [sourceId, await request(`/sources/${encodeURIComponent(sourceId)}`, {}, personContext)]));
      if (!OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion)) return;
      state.sources = new Map(sources);
      renderPersonContext(); renderSelectionEmptyState([state.person]); enableWorkspace(true); render(); status(t("workspace.workspace_loaded"), "success");
    } catch (error) {
      if (error.name !== "AbortError" && OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion)) {
        Object.assign(state, { person: null, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], conditionCandidates: [], labCandidates: [], timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null });
        byId("person-selector").value = "";
        renderPersonContext(); renderSelectionEmptyState([{}]); enableWorkspace(false); render();
        status(error.message, "error");
      }
    }
  }

  async function setActivePerson(personId, personContext = null) {
    const response = await fetch("/api/family-access/v1/active-person", {
      credentials: "same-origin",
      ...securedOptions({ method: "PUT", body: JSON.stringify({ person_id: personId }) }),
      ...(personContext?.signal ? { signal: personContext.signal } : {}),
    });
    if (personContext && (!OpenCareWorkspaceState.shouldApplyResponse(personContext.generation, state.loadVersion) || personContext.personId !== state.person?.person_id)) throw new DOMException("Stale workspace response", "AbortError");
    if (!response.ok) throw Error(t("workspace.person_not_available"));
  }

  function humanSourceLocator(locator) {
    if (!locator || typeof locator !== "object") return "Whole source";
    if (locator.kind === "structured_field" && typeof locator.path === "string") {
      const fields = {
        medication: "Medication name in a manual entry",
        "data.medication.display_name": "Medication name in a manual entry",
        "data.condition.display_name": "Recorded condition name in a manual entry",
        "data.lab.test_name": "Lab test name in a manual entry",
      };
      return fields[locator.path] || "Recorded field in a manual entry";
    }
    if (locator.kind === "document_text_span" && Number.isInteger(locator.page_number) && Number.isInteger(locator.start_codepoint) && Number.isInteger(locator.end_codepoint)) {
      return `Document page ${locator.page_number}, codepoints ${locator.start_codepoint}–${locator.end_codepoint}`;
    }
    if (locator.kind === "span" && Number.isInteger(locator.start) && Number.isInteger(locator.end) && locator.start >= 0 && locator.end > locator.start) {
      return `Source text characters ${locator.start + 1}–${locator.end}`;
    }
    return "Specific location recorded in the source";
  }

  function provenanceDetails(item) {
    const details = document.createElement("details"), summary = make("summary", "Source & provenance");
    const source = state.sources.get(item.source_id);
    details.append(summary, make("p", `Source ID: ${item.source_id}`));
    if (source) {
      const isDocument = source.source_type === "document" || item.provenance_locator?.kind === "document_text_span";
      const mediaLabel = source.media_type === "application/pdf" ? "PDF" : source.media_type === "text/plain" ? "Text" : "Source";
      details.append(
        make("p", isDocument ? `Document · ${mediaLabel}` : source.source_type === "manual_entry" ? "Manual entry" : "Source"),
        make("p", `Registered: ${source.created_at}`),
        make("p", `SHA-256: ${source.content_hash}`),
        make("p", `Size: ${source.size_bytes} bytes`),
        make("p", `Media type: ${source.media_type}`),
        make("p", source.integrity_verified ? "Integrity verified" : "Integrity not verified"),
      );
    } else details.append(make("p", "Source metadata unavailable."));
    details.append(make("p", `Source location: ${humanSourceLocator(item.provenance_locator)}`));
    if (item.predecessor_candidate_id) {
      const lineage = Object.hasOwn(item, "status")
        ? "Correction lineage: correction of an earlier reviewed candidate."
        : "Correction lineage: confirmed from a reviewed correction of an earlier record.";
      details.append(make("p", lineage));
    }
    if (item.superseded_by_record_id) details.append(make("p", "Correction lineage: superseded by a newer confirmed record."));
    return details;
  }

  function factCandidateCard(candidate, actions) {
    const card = make("article", "", "record");
    const name = candidate.fact_type === "lab" ? candidate.test_name : candidate.display_name;
    card.append(make("strong", name));
    card.append(make("p", `Fact: ${candidate.fact_type} · Status: ${candidate.status} · Created: ${candidate.created_at}`, "meta"));
    if (candidate.fact_type === "medication" && candidate.schedule_text) card.append(make("p", candidate.schedule_text));
    if (candidate.fact_type === "condition") { if (candidate.status_text) card.append(make("p", `Recorded status: ${candidate.status_text}`)); if (candidate.onset_date) card.append(make("p", `Recorded onset: ${candidate.onset_date}`)); }
    if (candidate.fact_type === "lab") { if (candidate.result_text) card.append(make("p", `Result as reported: ${candidate.result_text}`)); if (candidate.unit_text) card.append(make("p", `Unit as reported: ${candidate.unit_text}`)); if (candidate.reference_range_text) card.append(make("p", `Reference range as reported: ${candidate.reference_range_text}`)); if (candidate.observed_date) card.append(make("p", `Observed: ${candidate.observed_date}`)); if (candidate.source_flag_text) card.append(make("p", `Flag as reported: ${candidate.source_flag_text}`, "meta")); }
    if (candidate.note) card.append(make("p", candidate.note));
    card.append(provenanceDetails(candidate));
    if (actions) {
      const familyWrite = state.capabilities[`${candidate.fact_type}_write`];
      if (state.capabilities.candidate_review && familyWrite) {
        const confirm = make("button", "Confirm record"); confirm.type = "button"; confirm.addEventListener("click", () => transition(candidate, "confirm", confirm)); card.append(confirm);
      }
      if (state.capabilities.candidate_review && familyWrite) { const correct = make("button", "Create correction"); correct.type = "button"; correct.addEventListener("click", () => openCorrection(candidate, correct)); card.append(correct); }
      if (state.capabilities.candidate_review) {
        const reject = make("button", "Reject candidate"), unsupported = make("button", "Mark unsupported by source");
        reject.type = unsupported.type = "button"; reject.addEventListener("click", () => transition(candidate, "reject", reject)); unsupported.addEventListener("click", () => transition(candidate, "unsupported", unsupported)); card.append(reject, unsupported);
      }
    }
    return card;
  }

  function factRecordCard(record, factType, historical) {
    const card = make("article", "", "record");
    const name = factType === "lab" ? record.test_name : record.display_name;
    card.append(make("strong", name));
    card.append(make("p", `Confirmed: ${record.confirmed_at}${historical ? " · Superseded" : ""}`, "meta"));
    if (factType === "condition") { if (record.status_text) card.append(make("p", `Recorded status: ${record.status_text}`)); if (record.onset_date) card.append(make("p", `Recorded onset: ${record.onset_date}`)); }
    if (factType === "lab") { if (record.result_text) card.append(make("p", `Result as reported: ${record.result_text}`)); if (record.unit_text) card.append(make("p", `Unit as reported: ${record.unit_text}`)); if (record.reference_range_text) card.append(make("p", `Reference range as reported: ${record.reference_range_text}`)); if (record.observed_date) card.append(make("p", `Observed: ${record.observed_date}`)); if (record.source_flag_text) card.append(make("p", `Flag as reported: ${record.source_flag_text}`, "meta")); }
    if (record.note) card.append(make("p", record.note));
    card.append(provenanceDetails(record));
    return card;
  }

  function visibleCandidates() {
    const list = state.candidates.slice();
    if (state.conditionEnabled) list.push(...state.conditionCandidates);
    if (state.labEnabled) list.push(...state.labCandidates);
    return list;
  }

  function syncFactTypeFilters() {
    const facts = ["medication"];
    if (state.conditionEnabled) facts.push("condition");
    if (state.labEnabled) facts.push("lab");
    const select = byId("inbox-fact-filter");
    const current = select.value;
    clear(select);
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = "All fact types";
    select.append(all);
    facts.forEach((fact) => {
      const option = document.createElement("option");
      option.value = fact;
      option.textContent = fact === "condition" ? "Recorded condition" : fact[0].toUpperCase() + fact.slice(1);
      select.append(option);
    });
    select.value = facts.includes(current) ? current : "all";
  }

  async function submitCondition(event) {
    event.preventDefault();
    if (!state.person || !state.capabilities.condition_write || !state.capabilities.source_write || !state.capabilities.candidate_review) return;
    const submit = event.submitter;
    submit.disabled = true;
    const display_name = byId("condition-display-name").value, status_text = byId("condition-status-text").value || null, onset_date = byId("condition-onset-date").value || null, note = byId("condition-note").value || null;
    try {
      const source = await personRequest("/sources/manual-condition", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, condition: { display_name, status_text, onset_date, note } }) });
      await personRequest("/candidates/conditions", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, display_name, status_text, onset_date, note }) });
      event.target.reset();
      await loadWorkspace();
      status("Condition entry is waiting for review.", "success");
    } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; }
  }

  async function submitLab(event) {
    event.preventDefault();
    if (!state.person || !state.capabilities.lab_write || !state.capabilities.source_write || !state.capabilities.candidate_review) return;
    const submit = event.submitter;
    submit.disabled = true;
    const test_name = byId("lab-test-name").value, result_text = byId("lab-result-text").value, unit_text = byId("lab-unit-text").value || null, reference_range_text = byId("lab-reference-range-text").value || null, observed_date = byId("lab-observed-date").value || null, source_flag_text = byId("lab-source-flag-text").value || null, note = byId("lab-note").value || null;
    try {
      const source = await personRequest("/sources/manual-lab", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, lab: { test_name, result_text, unit_text, reference_range_text, observed_date, source_flag_text, note } }) });
      await personRequest("/candidates/labs", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, test_name, result_text, unit_text, reference_range_text, observed_date, source_flag_text, note }) });
      event.target.reset();
      await loadWorkspace();
      status("Lab entry is waiting for review.", "success");
    } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; }
  }

  function buildConditionSection() {
    const section = make("section", "");
    section.id = "condition-section";
    section.append(make("h2", "Recorded conditions"));
    section.append(make("p", "New entries wait for review before they become confirmed records.", "note"));
    const form = document.createElement("form");
    form.id = "condition-form";
    const displayName = document.createElement("input"); displayName.id = "condition-display-name"; displayName.maxLength = 200; displayName.required = true;
    const statusText = document.createElement("input"); statusText.id = "condition-status-text"; statusText.maxLength = 500;
    const onsetDate = document.createElement("input"); onsetDate.id = "condition-onset-date"; onsetDate.type = "date";
    const note = document.createElement("textarea"); note.id = "condition-note"; note.maxLength = 2000;
    const submit = make("button", "Add for review"); submit.type = "submit";
    form.append(make("h3", "Add condition for review"), labelled("Condition display name", displayName), labelled("Status text (optional, source text)", statusText), labelled("Onset date (optional)", onsetDate), labelled("Note (optional)", note), submit);
    form.addEventListener("submit", submitCondition);
    section.append(form, make("h3", "Waiting for review"), div("condition-pending"), make("h3", "Recorded conditions"), div("canonical-conditions"), make("h3", "Historical conditions"), div("historical-conditions"));
    return section;
  }

  function buildLabSection() {
    const section = make("section", "");
    section.id = "lab-section";
    section.append(make("h2", "Labs"));
    section.append(make("p", "New entries wait for review before they become confirmed records.", "note"));
    const form = document.createElement("form");
    form.id = "lab-form";
    const testName = document.createElement("input"); testName.id = "lab-test-name"; testName.maxLength = 200; testName.required = true;
    const resultText = document.createElement("textarea"); resultText.id = "lab-result-text"; resultText.maxLength = 2000; resultText.required = true;
    const unitText = document.createElement("input"); unitText.id = "lab-unit-text"; unitText.maxLength = 500;
    const referenceRangeText = document.createElement("input"); referenceRangeText.id = "lab-reference-range-text"; referenceRangeText.maxLength = 500;
    const observedDate = document.createElement("input"); observedDate.id = "lab-observed-date"; observedDate.type = "date";
    const sourceFlagText = document.createElement("input"); sourceFlagText.id = "lab-source-flag-text"; sourceFlagText.maxLength = 500;
    const note = document.createElement("textarea"); note.id = "lab-note"; note.maxLength = 2000;
    const submit = make("button", "Add for review"); submit.type = "submit";
    form.append(make("h3", "Add lab record for review"), labelled("Test name", testName), labelled("Result text (source text)", resultText), labelled("Unit text (optional)", unitText), labelled("Reference range text (optional)", referenceRangeText), labelled("Observed date (optional)", observedDate), labelled("Source flag text (optional, as reported)", sourceFlagText), labelled("Note (optional)", note), submit);
    form.addEventListener("submit", submitLab);
    section.append(form, make("h3", "Waiting for review"), div("lab-pending"), make("h3", "Recent/selected lab records"), div("canonical-labs"), make("h3", "Historical lab records"), div("historical-labs"));
    return section;
  }

  function renderFactSectionLists(factType) {
    const isCondition = factType === "condition";
    const pendingTarget = byId(isCondition ? "condition-pending" : "lab-pending");
    const activeTarget = byId(isCondition ? "canonical-conditions" : "canonical-labs");
    const historyTarget = byId(isCondition ? "historical-conditions" : "historical-labs");
    clear(pendingTarget); clear(activeTarget); clear(historyTarget);
    const candidates = isCondition ? state.conditionCandidates : state.labCandidates;
    const records = isCondition ? state.conditions : state.labs;
    const pending = candidates.filter((item) => item.status === "pending");
    if (!pending.length) pendingTarget.append(make("p", `No ${factType} entries are waiting for review.`, "meta"));
    pending.forEach((item) => pendingTarget.append(factCandidateCard(item, true)));
    const active = records.filter((item) => item.is_active);
    const historical = records.filter((item) => !item.is_active);
    if (!active.length) activeTarget.append(make("p", `No ${factType} records have been confirmed.`, "meta"));
    active.forEach((item) => activeTarget.append(factRecordCard(item, factType, false)));
    if (!historical.length) historyTarget.append(make("p", "No historical records.", "meta"));
    historical.forEach((item) => historyTarget.append(factRecordCard(item, factType, true)));
  }

  function renderFactSections() {
    const families = { medication: state.medications, condition: state.conditions, lab: state.labs };
    Object.entries(families).forEach(([factType, records]) => {
      const readable = Boolean(state.capabilities[`${factType}_read`]);
      const section = byId(`records-${factType}`);
      const addButton = section.querySelector("[data-toggle-form]");
      const activeTarget = byId(`${factType}-current`), historyTarget = byId(`${factType}-historical`);
      section.hidden = !readable;
      clear(activeTarget); clear(historyTarget);
      if (!readable) {
        addButton.hidden = true;
        byId(addButton.dataset.toggleForm).hidden = true;
        return;
      }
      addButton.hidden = !(state.capabilities[`${factType}_write`] && state.capabilities.source_write && state.capabilities.candidate_review);
      const active = records.filter((item) => item.is_active);
      const historical = records.filter((item) => !item.is_active);
      if (!active.length) activeTarget.append(make("p", "No current confirmed records.", "meta"));
      active.forEach((item) => activeTarget.append(factRecordCard(item, factType, false)));
      if (!historical.length) historyTarget.append(make("p", "No historical or superseded records.", "meta"));
      historical.forEach((item) => historyTarget.append(factRecordCard(item, factType, true)));
      byId(`${factType}-history-count`).textContent = `(${historical.length})`;
    });
  }

  function render() {
    const inbox = byId("review-inbox"), timeline = byId("timeline-list");
    [inbox, timeline].forEach(clear);
    renderOverview(); renderFactSections(); renderDocuments(); syncFactTypeFilters();
    const all = visibleCandidates(), inboxFact = byId("inbox-fact-filter").value, inboxStatus = byId("inbox-status-filter").value, search = byId("review-search").value.trim().toLocaleLowerCase();
    const inboxItems = all.filter((item) => (inboxFact === "all" || item.fact_type === inboxFact) && (inboxStatus === "all" || item.status === inboxStatus) && (!search || [item.display_name, item.test_name, item.note, item.result_text].some((value) => String(value || "").toLocaleLowerCase().includes(search))));
    if (!inboxItems.length) inbox.append(make("p", inboxStatus === "pending" ? t("workspace.pending_empty") : "No entries match this view.", "meta"));
    inboxItems.forEach((item) => inbox.append(factCandidateCard(item, item.status === "pending")));
    const timelineFilter = byId("timeline-filter").value, eventLabels = { medication_confirmed: "Medication record confirmed", condition_confirmed: "Condition record confirmed", lab_confirmed: "Lab record confirmed", medication_corrected: "Record superseded by reviewed correction", condition_corrected: "Record superseded by reviewed correction", lab_corrected: "Record superseded by reviewed correction" };
    const timelineItems = state.timeline.filter((item) => timelineFilter === "all" || item.fact_type === timelineFilter);
    if (!timelineItems.length) timeline.append(make("p", t("workspace.activity_empty"), "meta"));
    timelineItems.forEach((item) => { const card = make("article", `${item.title} — ${eventLabels[item.event_type] || item.event_type.replaceAll("_", " ")} · ${t("workspace.recorded_in_opencare", "Recorded in OpenCare")}: ${item.event_at}`, "record"); if (item.onset_date) card.append(make("p", `Onset date (as recorded): ${item.onset_date}`)); if (item.observed_date) card.append(make("p", `Observed date (as reported): ${item.observed_date}`)); timeline.append(card); });
    const chatNavigation = byId("chat-navigation"); if (chatNavigation) chatNavigation.hidden = !state.capabilities.chat_use;
    byId("timeline").hidden = !state.capabilities.timeline_read; byId("visits-brief").hidden = !state.capabilities.visit_read; byId("persisted-visit-brief").hidden = !(state.capabilities.visit_read && state.capabilities.brief_read); byId("export").hidden = !state.capabilities.vault_export; byId("edit-profile").hidden = !state.capabilities.person_update;
    renderVisitPlanning(); renderPersistedBrief();
  }

  function renderOverview() {
    const counts = byId("overview-counts"), latest = byId("overview-latest"), empty = byId("overview-empty"), actionLinks = byId("overview-action-links"), activity = byId("overview-activity-list");
    [counts, latest, actionLinks, activity].forEach(clear);
    const readableTypes = ["medication", "condition", "lab"].filter((type) => state.capabilities[`${type}_read`]);
    const records = [...state.medications, ...state.conditions, ...state.labs].filter((item) => item.is_active);
    const pending = visibleCandidates().filter((item) => item.status === "pending").length;
    const metric = (label, value) => {
      const card = make("article", "", "summary-item");
      card.append(make("strong", String(value)), make("span", label));
      counts.append(card);
    };
    if (readableTypes.length) metric(t("workspace.metric_records"), records.length);
    if (state.capabilities.document_read) metric(t("workspace.metric_documents"), state.documents.length);
    if (state.capabilities.medication_read) metric(t("workspace.metric_medications"), state.medications.filter((item) => item.is_active).length);
    if (state.capabilities.timeline_read) metric(t("workspace.metric_activity"), state.timeline.length);
    if (pending) metric(t("workspace.metric_pending"), pending);
    const hasData = records.length > 0 || state.documents.length > 0 || state.timeline.length > 0 || pending > 0;
    empty.hidden = hasData;
    if (records.length) {
      const newest = OpenCareWorkspaceState.sortNewest(records, "confirmed_at", "id")[0];
      latest.append(make("p", `${t("workspace.latest_record")}: ${newest.confirmed_at}`, "meta"));
    }
    if (state.capabilities.visit_read && state.visit) latest.append(make("p", `${t("workspace.selected_visit")}: ${state.visit.title}`, "meta"));

    const action = (href, label, id = "") => {
      const link = make("a", label, "action-link");
      link.href = href;
      if (id) link.id = id;
      actionLinks.append(link);
    };
    if (state.capabilities.document_read) action("#documents", t("workspace.add_document"));
    if (readableTypes.length) action("#records", t("workspace.open_records"));
    action("/genetics", t("workspace.open_genetics"));
    if (state.capabilities.chat_use) action("/chat", t("workspace.ask_opencare"), "chat-navigation");
    action("/family-access", t("workspace.family_access"));

    if (!state.capabilities.timeline_read || !state.timeline.length) {
      activity.append(make("p", t("workspace.no_recent_activity"), "meta"));
    } else {
      OpenCareWorkspaceState.sortNewest(state.timeline, "event_at", "id").slice(0, 3).forEach((item) => {
        const entry = make("article", "", "activity-item");
        entry.append(make("strong", item.title), make("p", item.event_at, "meta"));
        activity.append(entry);
      });
    }
  }

  function renderVisitPlanning() {
    const visits = byId("visits"), questions = byId("visit-questions"), canWrite = state.capabilities.visit_write;
    clear(visits); clear(questions); byId("open-visit-form").hidden = !canWrite;
    if (!state.visits.length) visits.append(make("p", "No visits have been created for this profile.", "meta"));
    state.visits.forEach((visit) => {
      const card = make("article", "", "record"), select = make("button", state.visit?.visit_id === visit.visit_id ? "Selected visit" : "Select visit");
      select.type = "button"; select.disabled = state.visit?.visit_id === visit.visit_id; select.addEventListener("click", () => selectVisit(visit, select));
      card.append(make("strong", visit.title), make("p", `${visit.specialist || "No specialist"} · ${visit.scheduled_date || "No scheduled date"}`, "meta"), select); visits.append(card);
    });
    const hasVisit = Boolean(state.visit);
    byId("edit-visit-form").hidden = !hasVisit || !canWrite; byId("visit-question-form").hidden = !hasVisit || !canWrite; byId("edit-visit-question-form").hidden = !hasVisit || !canWrite || state.editingQuestion === null;
    if (!hasVisit) return;
    byId("edit-visit-title").value = state.visit.title; byId("edit-visit-specialist").value = state.visit.specialist || ""; byId("edit-visit-date").value = state.visit.scheduled_date || ""; byId("selected-visit-label").textContent = `Questions for: ${state.visit.title}`;
    if (!state.questions.length) questions.append(make("p", "No questions have been added for this visit.", "meta"));
    OpenCareWorkspaceState.sortQuestions(state.questions).forEach((question, index, sorted) => {
      const card = make("article", "", "record"); card.append(make("strong", `Question ${index + 1}`), make("p", question.question_text));
      if (canWrite) {
        const actions = document.createElement("div"), edit = make("button", "Edit"), up = make("button", "Move question up"), down = make("button", "Move question down"), remove = make("button", "Remove");
        [edit, up, down, remove].forEach((button) => { button.type = "button"; }); up.disabled = index === 0; down.disabled = index === sorted.length - 1;
        edit.addEventListener("click", () => openQuestionEdit(question, edit)); up.addEventListener("click", () => moveQuestion(question, sorted[index - 1]?.position ?? question.position, up)); down.addEventListener("click", () => moveQuestion(question, sorted[index + 1]?.position ?? question.position, down)); remove.addEventListener("click", () => removeQuestion(question, remove)); actions.append(edit, up, down, remove); card.append(actions);
      }
      questions.append(card);
    });
  }
  async function refreshVisits() {
    if (!state.person) return;
    const response = await personRequest(`/people/${encodeURIComponent(state.person.person_id)}/visits`);
    state.visits = OpenCareWorkspaceState.sortVisits(response.visits.filter((visit) => visit.person_id === state.person.person_id));
  }

  async function selectVisit(visit, trigger) {
    if (visit.person_id !== state.person?.person_id) return;
    try {
      const response = await personRequest(`/visits/${encodeURIComponent(visit.visit_id)}/questions`);
      if (visit.person_id !== state.person?.person_id) return;
      state.visit = visit; state.questions = OpenCareWorkspaceState.sortQuestions(response.questions); state.editingQuestion = null; state.persistedBrief = null; state.briefRevision = null; state.briefEvidence = []; state.briefDirty = false; renderVisitPlanning(); await loadPersistedBrief();
      if (state.capabilities.visit_write) byId("new-visit-question").focus();
    } catch (error) { if (error.name !== "AbortError") { status(error.message, "error"); trigger.focus(); } }
  }

  function selectedEvidenceIds() {
    return [...document.querySelectorAll('input[name="brief-record"]:checked')].map((item) => item.value);
  }

  function stalenessLabel(staleness) {
    if (!staleness || staleness.state === "unavailable") return "Revision unavailable";
    if (staleness.state === "current") return "Current";
    return staleness.reasons?.includes("record_or_source_changed") ? "Selected record or source changed" : "Evidence changed since this revision";
  }
  function renderEvidenceGroup(factType, title, selectedIds) {
    const target = byId(`brief-${factType}-options`); clear(target); target.append(make("h4", title));
    const eligible = state.briefEvidence.filter((item) =>
      OpenCareWorkspaceState.evidenceFactType(item) === factType
      && (!Object.hasOwn(item, "person_id") || item.person_id === state.person?.person_id)
      && item.is_active !== false
      && (!item.status || item.status === "confirmed")
      && (!item.confirmation_status || item.confirmation_status === "confirmed")
    );
    if (!eligible.length) target.append(make("p", "No eligible confirmed evidence.", "meta"));
    eligible.forEach((item) => { const label = document.createElement("label"), input = document.createElement("input"); input.type = "checkbox"; input.name = "brief-record"; input.value = item.canonical_record_id || item.id; input.checked = selectedIds.includes(input.value); input.disabled = !state.capabilities.brief_write; label.append(input, document.createTextNode(` ${item.display_name || item.test_name || "Evidence record"}`)); target.append(label); });
  }
  function renderPersistedBrief() {
    const hasVisit = Boolean(state.visit), hasBrief = Boolean(state.persistedBrief), canWrite = state.capabilities.brief_write;
    byId("initialize-brief").hidden = !hasVisit || hasBrief || !canWrite; byId("initialize-brief").disabled = !hasVisit || !canWrite; byId("brief-workflow").hidden = !hasBrief;
    byId("brief-status").textContent = !hasVisit ? "Select a Visit to prepare its Brief." : !hasBrief ? (canWrite ? "Initialize a persistent Brief for this Visit." : "No persistent Brief is available for this Visit.") : state.briefRevision ? `Viewing revision ${state.briefRevision.revision_number}. ${stalenessLabel(state.briefRevision.staleness)}` : "Select confirmed evidence to generate the first revision.";
    const content = state.briefRevision?.content || {};
    const selectedIds = [...(content.medications || []), ...(content.conditions || []), ...(content.labs || []), ...(content.records || [])].map((record) => record.canonical_record_id || record.id).filter(Boolean);
    renderEvidenceGroup("medication", "Medications", selectedIds); renderEvidenceGroup("condition", "Recorded conditions", selectedIds); renderEvidenceGroup("lab", "Labs", selectedIds);
    byId("brief-evidence-selection").disabled = !hasBrief || !canWrite; byId("validate-brief-evidence").hidden = !canWrite; byId("generate-brief").hidden = !canWrite; byId("brief-preparation-notes").disabled = !state.briefRevision || !canWrite; byId("save-brief-notes").hidden = !canWrite; byId("save-brief-notes").disabled = !state.briefRevision || !state.briefDirty; byId("download-brief").hidden = !state.capabilities.brief_export; byId("brief-unsaved-warning").hidden = !state.briefDirty;
    if (state.briefRevision) { if (!state.briefDirty) byId("brief-preparation-notes").value = content.preparation_notes || ""; byId("brief-metadata").textContent = `Revision ${state.briefRevision.revision_number} · ${state.briefRevision.origin.replaceAll("_", " ")} · ${stalenessLabel(state.briefRevision.staleness)}`; byId("brief-markdown").textContent = state.briefRevision.markdown; byId("brief-result").hidden = false; } else byId("brief-result").hidden = true;
    renderBriefRevisions();
  }

  function renderBriefRevisions() {
    const target = byId("brief-revisions"); clear(target); const revisions = state.persistedBrief?.revisions || [];
    if (!state.persistedBrief || !revisions.length) { target.append(make("p", state.persistedBrief ? "No revisions have been created." : "", "meta")); return; }
    revisions.forEach((revision) => { const card = make("article", "", "record"), view = make("button", `View revision ${revision.revision_number}`); view.type = "button"; view.addEventListener("click", () => loadBriefRevision(revision.revision_number, view)); card.append(make("strong", `Revision ${revision.revision_number} · ${revision.origin.replaceAll("_", " ")}`), make("p", stalenessLabel(revision.staleness), "meta"), view); if (state.capabilities.brief_write) { const restore = make("button", `Restore revision ${revision.revision_number}`); restore.type = "button"; restore.disabled = revision.revision_number === state.persistedBrief.current_revision_number; restore.addEventListener("click", () => restoreBriefRevision(revision.revision_number, restore)); card.append(restore); } target.append(card); });
  }

  async function loadPersistedBrief() {
    if (!state.visit || !state.capabilities.brief_read) return;
    try { state.persistedBrief = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief`); await Promise.all([loadBriefEvidence(), loadBriefHistory()]); state.briefRevision = state.persistedBrief.current_revision; renderPersistedBrief(); }
    catch (error) { if (error.name === "AbortError") return; if (error.status === 404) { state.persistedBrief = null; renderPersistedBrief(); return; } status(error.message, "error"); }
  }

  async function loadBriefEvidence() { if (!state.visit) return; const response = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/evidence`); state.briefEvidence = response.evidence; }
  async function loadBriefHistory() { if (!state.visit || !state.persistedBrief) return; const response = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions`); state.persistedBrief.revisions = response.revisions; }
  async function loadBriefRevision(number, trigger) { if (!state.visit) return; try { state.briefRevision = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions/${number}`); state.briefDirty = false; renderPersistedBrief(); byId("brief-preparation-notes").focus(); } catch (error) { if (error.name !== "AbortError") { status(error.message, "error"); trigger.focus(); } } }

  async function moveQuestion(question, position, trigger) {
    trigger.disabled = true;
    try { await personRequest(`/visit-questions/${encodeURIComponent(question.question_id)}`, { method: "PATCH", body: JSON.stringify({ position }) }); await selectVisit(state.visit, trigger); status("Question order updated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); trigger.disabled = false; }
  }

  function openQuestionEdit(question, trigger) {
    state.editingQuestion = { question, trigger }; byId("edit-visit-question").value = question.question_text; byId("edit-visit-question-form").hidden = false; byId("edit-visit-question").focus();
  }

  async function removeQuestion(question, trigger) {
    trigger.disabled = true;
    try { await personRequest(`/visit-questions/${encodeURIComponent(question.question_id)}`, { method: "DELETE" }); await selectVisit(state.visit, trigger); status("Question removed.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); trigger.disabled = false; }
  }

  async function transition(candidate, action, button) {
    if (action === "confirm" && !(state.capabilities.candidate_review && state.capabilities[`${candidate.fact_type}_write`])) return;
    if (action !== "confirm" && !state.capabilities.candidate_review) return;
    if (action === "reject" && !window.confirm("Reject this candidate?")) return;
    button.disabled = true;
    try { await personRequest(`/candidates/${encodeURIComponent(candidate.id)}/${action}`, { method: "POST", body: "{}" }); await loadWorkspace(); status(action === "unsupported" ? "Candidate marked unsupported by source." : action === "confirm" ? "Record confirmed." : "Candidate rejected.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { button.disabled = false; }
  }

  const CORRECTION_FIELDS = {
    medication: [
      { key: "display_name", label: "Medication display name", input: true, maxLength: 200 },
      { key: "schedule_text", label: "Schedule text", input: true, maxLength: 500 },
      { key: "note", label: "Note", input: false, maxLength: 2000 },
    ],
    condition: [
      { key: "display_name", label: "Condition display name", input: true, maxLength: 200 },
      { key: "status_text", label: "Status text (source text)", input: true, maxLength: 500 },
      { key: "onset_date", label: "Onset date", input: true, date: true, maxLength: 0 },
      { key: "note", label: "Note", input: false, maxLength: 2000 },
    ],
    lab: [
      { key: "test_name", label: "Test name", input: true, maxLength: 200 },
      { key: "result_text", label: "Result text (source text)", input: false, maxLength: 2000 },
      { key: "unit_text", label: "Unit text", input: true, maxLength: 500 },
      { key: "reference_range_text", label: "Reference range text", input: true, maxLength: 500 },
      { key: "observed_date", label: "Observed date", input: true, date: true, maxLength: 0 },
      { key: "source_flag_text", label: "Source flag text", input: true, maxLength: 500 },
      { key: "note", label: "Note", input: false, maxLength: 2000 },
    ],
  };
  const CORRECTION_ENDPOINTS = { medication: "correct", condition: "correct:condition", lab: "correct:lab" };

  function openCorrection(candidate, trigger) {
    if (!(state.capabilities.candidate_review && state.capabilities[`${candidate.fact_type}_write`])) return;
    const form = document.createElement("form"); form.className = "record correction-form";
    const specs = CORRECTION_FIELDS[candidate.fact_type] || CORRECTION_FIELDS.medication;
    const controls = specs.map((spec) => {
      const control = document.createElement(spec.input ? "input" : "textarea");
      if (spec.date) control.type = "date"; else if (spec.maxLength) control.maxLength = spec.maxLength;
      control.value = candidate[spec.key] || "";
      return control;
    });
    const name = controls[0], error = make("p", "", "error"), save = make("button", "Save correction"), cancel = make("button", "Cancel");
    error.setAttribute("role", "alert"); save.type = "submit"; cancel.type = "button";
    const title = candidate.fact_type === "medication" ? "Correct medication entry" : candidate.fact_type === "condition" ? "Correct condition entry" : "Correct lab entry";
    form.append(make("h3", title));
    specs.forEach((spec, index) => form.append(labelled(spec.label, controls[index])));
    form.append(error, save, cancel);
    const close = () => { form.remove(); trigger.focus(); };
    cancel.addEventListener("click", close);
    form.addEventListener("submit", async (event) => { event.preventDefault(); save.disabled = true; error.textContent = ""; const payload = {}; specs.forEach((spec, index) => { payload[spec.key] = controls[index].value || null; }); try { await personRequest(`/candidates/${encodeURIComponent(candidate.id)}/${CORRECTION_ENDPOINTS[candidate.fact_type]}`, { method: "POST", body: JSON.stringify(payload) }); await loadWorkspace(); close(); status("Correction is waiting for review.", "success"); } catch (failure) { error.textContent = failure.message; } finally { save.disabled = false; } });
    trigger.closest("article").append(form); name.focus();
  }

  async function clearWorkspace() {
    state.controller?.abort();
    state.loadVersion += 1;
    try { await setActivePerson(null); } catch (error) { status(error.message, "error"); return; }
    Object.assign(state, { person: null, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], conditionCandidates: [], labCandidates: [], conditionEnabled: false, labEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null, controller: null });
    byId("person-selector").value = ""; byId("edit-profile-form").hidden = true; byId("edit-visit-form").hidden = true; byId("visit-question-form").hidden = true; byId("edit-visit-question-form").hidden = true; byId("vault-export-warning").hidden = true; renderPersonContext(); renderSelectionEmptyState([{}]); updateShellPerson(null); render(); enableWorkspace(false); byId("load-workspace").disabled = true; status(t("workspace.selection_cleared"));
  }

  byId("person-selector").addEventListener("change", () => { byId("load-workspace").disabled = !byId("person-selector").value; void loadWorkspace(); });
  byId("load-workspace").addEventListener("click", loadWorkspace);
  byId("clear-workspace").addEventListener("click", () => { void clearWorkspace(); });
  byId("open-vault-export").addEventListener("click", (event) => { if (!state.person || !state.capabilities.vault_export) return; state.vaultExportTrigger = event.currentTarget; byId("vault-export-warning").hidden = false; byId("confirm-vault-export").focus(); });
  byId("cancel-vault-export").addEventListener("click", () => { byId("vault-export-warning").hidden = true; state.vaultExportTrigger?.focus(); });
  byId("confirm-vault-export").addEventListener("click", async (event) => { if (!state.person || !state.capabilities.vault_export) return; const button = event.currentTarget, personContext = { personId: state.person.person_id, generation: state.loadVersion, signal: state.controller?.signal }; button.disabled = true; try { const { blob, response } = await requestBlob(`/people/${encodeURIComponent(state.person.person_id)}/vault-export`, { method: "POST", body: "{}" }, personContext); const serverName = OpenCareWorkspaceState.contentDispositionFilename(response.headers.get("Content-Disposition")); const filename = OpenCareWorkspaceState.sanitizeDownloadFilename(serverName, "opencare-person-vault-v4.zip"); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href); byId("vault-export-warning").hidden = true; state.vaultExportTrigger?.focus(); status("Vault download prepared.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { button.disabled = false; } });
  byId("inbox-fact-filter").addEventListener("change", render);
  byId("inbox-status-filter").addEventListener("change", render);
  byId("review-search").addEventListener("input", render);
  byId("timeline-filter").addEventListener("change", render);
  document.querySelectorAll("[data-toggle-form]").forEach((button) => {
    const form = byId(button.dataset.toggleForm);
    button.addEventListener("click", () => {
      if (button.hidden || button.disabled) return;
      form.hidden = !form.hidden;
      button.setAttribute("aria-expanded", String(!form.hidden));
      if (!form.hidden) form.querySelector("input, textarea, select")?.focus();
      else button.focus();
    });
  });
  document.querySelectorAll("[data-close-form]").forEach((button) => {
    const form = byId(button.dataset.closeForm);
    const trigger = document.querySelector(`[data-toggle-form="${button.dataset.closeForm}"]`);
    button.addEventListener("click", () => {
      form.reset(); form.hidden = true;
      trigger?.setAttribute("aria-expanded", "false");
      trigger?.focus();
    });
  });
  byId("open-visit-form").addEventListener("click", () => {
    if (!state.capabilities.visit_write) return;
    byId("visit-form").hidden = false;
    byId("new-visit-title").focus();
  });
  byId("cancel-visit-form").addEventListener("click", () => {
    byId("visit-form").reset(); byId("visit-form").hidden = true; byId("open-visit-form").focus();
  });
  byId("create-profile-form").addEventListener("submit", async (event) => { event.preventDefault(); const submit = event.submitter; submit.disabled = true; try { const person = await request("/people", { method: "POST", body: JSON.stringify({ display_name: byId("create-display-name").value, date_of_birth: byId("create-date-of-birth").value || null, confirm_owner_assignment: byId("create-owner-confirmation").checked }) }); state.person = person; await refreshPeople(person); byId("create-profile-form").reset(); await loadWorkspace(); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("edit-profile").addEventListener("click", () => { if (!state.person || !state.capabilities.person_update) return; byId("edit-display-name").value = state.person.display_name; byId("edit-date-of-birth").value = state.person.date_of_birth || ""; byId("edit-profile-form").hidden = false; byId("edit-display-name").focus(); });
  byId("cancel-edit-profile").addEventListener("click", () => { byId("edit-profile-form").hidden = true; byId("edit-profile").focus(); });
  byId("edit-profile-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person || !state.capabilities.person_update) return; const submit = event.submitter; submit.disabled = true; try { const person = await personRequest(`/people/${encodeURIComponent(state.person.person_id)}`, { method: "PATCH", body: JSON.stringify({ display_name: byId("edit-display-name").value, date_of_birth: byId("edit-date-of-birth").value || null }) }); state.person = person; await refreshPeople(person); renderPersonContext(); byId("edit-profile-form").hidden = true; status("Profile updated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("medication-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person || !state.capabilities.medication_write || !state.capabilities.source_write || !state.capabilities.candidate_review) return; const submit = event.submitter; submit.disabled = true; const display_name = byId("medication-name").value, schedule_text = byId("medication-schedule").value || null, note = byId("medication-note").value || null; try { const source = await personRequest("/sources/manual-medication", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, medication: { display_name, schedule_text, note } }) }); await personRequest("/candidates/medications", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, display_name, schedule_text, note }) }); event.target.reset(); await loadWorkspace(); status("Medication entry is waiting for review.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("condition-form").addEventListener("submit", submitCondition);
  byId("lab-form").addEventListener("submit", submitLab);
  byId("visit-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person || !state.capabilities.visit_write) return; const submit = event.submitter; submit.disabled = true; try { const visit = await personRequest("/visits", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, title: byId("new-visit-title").value, specialist: byId("new-visit-specialist").value || null, scheduled_date: byId("new-visit-date").value || null }) }); event.target.reset(); await refreshVisits(); await selectVisit(visit, submit); status("Visit created.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("edit-visit-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.visit || !state.capabilities.visit_write) return; const submit = event.submitter; submit.disabled = true; try { const visit = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}`, { method: "PATCH", body: JSON.stringify({ title: byId("edit-visit-title").value, specialist: byId("edit-visit-specialist").value || null, scheduled_date: byId("edit-visit-date").value || null }) }); state.visit = visit; await refreshVisits(); renderVisitPlanning(); status("Visit updated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("cancel-edit-visit").addEventListener("click", () => { if (!state.visit) return; byId("edit-visit-title").value = state.visit.title; byId("edit-visit-specialist").value = state.visit.specialist || ""; byId("edit-visit-date").value = state.visit.scheduled_date || ""; byId("edit-visit-title").focus(); });
  byId("visit-question-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.visit || !state.capabilities.visit_write) return; const submit = event.submitter; submit.disabled = true; try { await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/questions`, { method: "POST", body: JSON.stringify({ question_text: byId("new-visit-question").value }) }); event.target.reset(); await selectVisit(state.visit, submit); status("Question added.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("edit-visit-question-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.editingQuestion || !state.capabilities.visit_write) return; const submit = event.submitter, editing = state.editingQuestion; submit.disabled = true; try { await personRequest(`/visit-questions/${encodeURIComponent(editing.question.question_id)}`, { method: "PATCH", body: JSON.stringify({ question_text: byId("edit-visit-question").value }) }); state.editingQuestion = null; byId("edit-visit-question-form").hidden = true; await selectVisit(state.visit, submit); status("Question updated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("cancel-edit-visit-question").addEventListener("click", () => { const trigger = state.editingQuestion?.trigger; state.editingQuestion = null; byId("edit-visit-question-form").hidden = true; if (trigger) trigger.focus(); });
  byId("initialize-brief").addEventListener("click", async (event) => { if (!state.visit || !state.capabilities.brief_write) return; const button = event.currentTarget; button.disabled = true; try { state.persistedBrief = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief`, { method: "POST", body: "{}" }); state.persistedBrief.revisions = []; state.briefRevision = null; await loadBriefEvidence(); renderPersistedBrief(); status("Visit Brief initialized.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { button.disabled = false; } });
  byId("validate-brief-evidence").addEventListener("click", async (event) => { if (!state.visit || !state.capabilities.brief_write) return; const button = event.currentTarget; button.disabled = true; try { await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/evidence:validate`, { method: "POST", body: JSON.stringify({ selected_record_ids: selectedEvidenceIds() }) }); status("Selected evidence is valid.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { button.disabled = false; } });
  byId("generate-brief").addEventListener("click", async (event) => { if (!state.visit || !state.persistedBrief || !state.capabilities.brief_write) return; const button = event.currentTarget; button.disabled = true; try { state.briefRevision = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions:generate`, { method: "POST", body: JSON.stringify({ selected_record_ids: selectedEvidenceIds(), expected_current_revision_number: state.persistedBrief.current_revision_number }) }); state.persistedBrief.current_revision_number = state.briefRevision.revision_number; state.briefDirty = false; await loadBriefHistory(); renderPersistedBrief(); status("Visit Brief revision generated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { button.disabled = false; } });
  byId("brief-preparation-notes").addEventListener("input", () => { if (!state.capabilities.brief_write) return; state.briefDirty = true; byId("save-brief-notes").disabled = false; byId("brief-unsaved-warning").hidden = false; });
  byId("save-brief-notes").addEventListener("click", async (event) => { if (!state.visit || !state.persistedBrief?.current_revision_number || !state.capabilities.brief_write) return; const button = event.currentTarget; button.disabled = true; try { state.briefRevision = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions:user-edit`, { method: "POST", body: JSON.stringify({ preparation_notes: byId("brief-preparation-notes").value, expected_current_revision_number: state.persistedBrief.current_revision_number }) }); state.persistedBrief.current_revision_number = state.briefRevision.revision_number; state.briefDirty = false; await loadBriefHistory(); renderPersistedBrief(); status("Preparation notes saved as a new revision.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { button.disabled = false; } });
  async function restoreBriefRevision(number, trigger) { if (!state.visit || !state.persistedBrief?.current_revision_number || !state.capabilities.brief_write) return; trigger.disabled = true; try { state.persistedBrief = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/current`, { method: "POST", body: JSON.stringify({ revision_number: number, expected_current_revision_number: state.persistedBrief.current_revision_number }) }); await loadBriefHistory(); state.briefRevision = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions/${number}`); state.briefDirty = false; renderPersistedBrief(); status("Current Brief revision restored.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); trigger.disabled = false; } }
  byId("copy-brief").addEventListener("click", async () => { if (!state.briefRevision) return; try { await navigator.clipboard.writeText(state.briefRevision.markdown); status("Markdown copied.", "success"); } catch (_) { status("Copy is unavailable in this browser.", "error"); } });
  byId("download-brief").addEventListener("click", async () => { if (!state.visit || !state.capabilities.brief_export) return; try { const markdown = await requestText(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/current:export`, { method: "POST", body: "{}" }, currentPersonContext()); const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `opencare-visit-brief-r${state.persistedBrief.current_revision_number}.md`; link.click(); URL.revokeObjectURL(link.href); status("Markdown download prepared.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } });

  enableWorkspace(false); renderPeople([]); refreshPeople().catch((error) => { status(error.message, "error"); });
  byId("document-upload-form").addEventListener("submit", uploadDocument);
  byId("document-page-selector").addEventListener("change", (event) => {
    if (!state.selectedDocument) return;
    state.selectedPage = null; state.selectedSpan = null;
    void loadDocumentPage(state.selectedDocument, Number(event.target.value), event.target);
  });
  byId("document-page-text").addEventListener("select", () => {
    const text = byId("document-page-text"), start = text.selectionStart, end = text.selectionEnd;
    if (Number.isInteger(start) && Number.isInteger(end) && end > start) {
      state.selectedSpan = { start, end }; renderDocumentViewer();
    }
  });
  byId("document-candidate-form").addEventListener("submit", submitDocumentCandidate);
  byId("document-candidate-type").addEventListener("change", renderDocumentViewer);
})();
