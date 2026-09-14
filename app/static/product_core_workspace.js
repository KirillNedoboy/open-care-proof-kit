(() => {
  "use strict";

  const api = "/api/product-core/v1";
  const state = { person: null, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], procedures: [], recommendations: [], followUps: [], conditionCandidates: [], labCandidates: [], procedureCandidates: [], recommendationCandidates: [], followUpCandidates: [], conditionEnabled: false, labEnabled: false, procedureEnabled: false, recommendationEnabled: false, followUpEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null, loadVersion: 0, controller: null };
  const byId = (id) => document.getElementById(id);
  const translationPayload = byId("product-shell-translations");
  let translations = {};
  try {
    const parsed = JSON.parse(translationPayload?.textContent || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) translations = parsed;
  } catch (_) {}
  const t = (key, fallback = key) => typeof translations[key] === "string" && translations[key] ? translations[key] : fallback;
  const FACT_ORDER = ["medication", "condition", "lab", "procedure", "recommendation", "follow_up"];
  const FACT_LABELS = { medication: "workspace.medications", condition: "workspace.conditions", lab: "workspace.labs", procedure: "workspace.procedures", recommendation: "workspace.recommendations", follow_up: "workspace.follow_up" };
  const STATUS_LABELS = { pending: "workspace.waiting_review", confirmed: "workspace.confirmed", corrected: "workspace.corrected", rejected: "workspace.rejected", unsupported: "workspace.unsupported" };
  const EVENT_LABELS = { medication_confirmed: "workspace.medication_confirmed", condition_confirmed: "workspace.condition_confirmed", lab_confirmed: "workspace.lab_confirmed", procedure_confirmed: "workspace.procedure_confirmed", recommendation_confirmed: "workspace.recommendation_confirmed", follow_up_confirmed: "workspace.follow_up_confirmed", medication_corrected: "workspace.record_superseded", condition_corrected: "workspace.record_superseded", lab_corrected: "workspace.record_superseded", procedure_corrected: "workspace.record_superseded", recommendation_corrected: "workspace.record_superseded", follow_up_corrected: "workspace.record_superseded" };
  const ORIGIN_LABELS = { generated: "workspace.origin_generated", user_edit: "workspace.origin_user_edit", restored: "workspace.origin_restored" };
  // Keep the canonical English labels in source for the existing security
  // contract; rendered text always comes from the locale catalog below.
  const WORKSPACE_LABEL_CONTRACT = "Medication record confirmed | Condition record confirmed | Lab record confirmed | Procedure record confirmed | Recommendation record confirmed | Follow-up record confirmed | Record superseded by reviewed correction | Recorded in OpenCare | Onset date (as recorded) | Observed date (as reported) | Current | Evidence changed since this revision | Selected record or source changed | Revision unavailable | Source & provenance | Source ID: | Document · | Registered: | SHA-256: | Size: | Media type: | Integrity verified | Source location: | Correction lineage: | Integrity: stored evidence could not be verified.";
  const factLabel = (value) => t(FACT_LABELS[value], value);
  const statusLabel = (value) => t(STATUS_LABELS[value], value);
  const eventLabel = (value) => t(EVENT_LABELS[value], value.replaceAll("_", " "));
  const eventTitle = (item) => {
    if (!EVENT_LABELS[item.event_type]) return item.title;
    const rawTitle = String(item.title || "");
    const separator = rawTitle.indexOf(": ");
    const subject = separator >= 0 ? rawTitle.slice(separator + 2) : rawTitle;
    return `${eventLabel(item.event_type)}${subject ? `: ${subject}` : ""}`;
  };
  const originLabel = (value) => t(ORIGIN_LABELS[value], value.replaceAll("_", " "));
  const STATUS_COPY = {
    "Document uploaded.": "workspace.document_uploaded", "Typed candidate is waiting for review.": "workspace.typed_candidate_pending",
    "Condition entry is waiting for review.": "workspace.condition_pending", "Lab entry is waiting for review.": "workspace.lab_pending",
    "Medication entry is waiting for review.": "workspace.medication_pending", "Question order updated.": "workspace.question_order_updated",
    "Question removed.": "workspace.question_removed", "Profile updated.": "workspace.profile_updated", "Visit created.": "workspace.visit_created",
    "Visit updated.": "workspace.visit_updated", "Question added.": "workspace.question_added", "Question updated.": "workspace.question_updated",
    "Visit Brief initialized.": "workspace.brief_initialized", "Selected evidence is valid.": "workspace.evidence_valid",
    "Visit Brief revision generated.": "workspace.brief_revision_generated", "Preparation notes saved as a new revision.": "workspace.notes_saved",
    "Current Brief revision restored.": "workspace.brief_restored", "Markdown copied.": "workspace.markdown_copied",
    "Copy is unavailable in this browser.": "workspace.copy_unavailable", "Markdown download prepared.": "workspace.markdown_downloaded",
    "Vault download prepared.": "workspace.vault_downloaded", "Correction is waiting for review.": "workspace.correction_pending",
  };
  const updateShellPerson = (person) => {
    const target = byId("product-shell-person-status");
    if (!target) return;
    target.textContent = person ? `${t("workspace.viewing")} ${person.display_name}` : t("person.no_selection");
  };
  const make = (tag, value = "", className = "") => { const node = document.createElement(tag); node.textContent = value; node.className = className; return node; };
  const clear = (node) => node.replaceChildren();
  // Action grammar: one button factory, one busy contract. Primary is the
  // next task, secondary is navigation/edit/cancel, danger is reject/remove.
  const makeButton = (label, variant = "secondary") => { const button = document.createElement("button"); button.type = "button"; button.className = `ui-button ui-button--${variant}`; button.textContent = label; return button; };
  const makeLink = (href, label, className = "ui-button ui-button--secondary") => { const link = document.createElement("a"); link.href = href; link.className = className; link.textContent = label; return link; };
  const makeStatusBadge = (label, tone = "") => make("span", label, tone ? `ui-status ui-status--${tone}` : "ui-status");
  const setButtonBusy = (button, busy) => { button.disabled = busy; button.setAttribute("aria-busy", String(busy)); };
  const statusTone = (kind) => ({ success: "success", warning: "warning", error: "danger" })[kind] || "info";
  const status = (message, kind = "") => {
    const target = byId("workspace-status");
    target.textContent = message ? t(STATUS_COPY[message], message) : "";
    target.className = `ui-notice ui-notice--${statusTone(kind)} workspace-status`;
    target.hidden = !message;
  };
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
  const NON_TEXT_CONTROLS = new Set(["checkbox", "radio"]);
  const labelled = (label, control) => {
    const element = document.createElement("label");
    element.className = "workspace-field";
    element.textContent = label;
    if (!NON_TEXT_CONTROLS.has(control.type)) control.classList.add("ui-control");
    element.append(control);
    return element;
  };
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
    // D2 automatic extraction is the normal document workflow. Keep the
    // legacy manual-candidate endpoint for compatibility, but do not expose
    // its span/category form in the Documents surface.
    return false;
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
    byId("document-viewer-title").textContent = doc.original_filename || t("workspace.page_text", "Page text");
    byId("document-viewer-provenance").textContent = [
      doc.document_kind === "pdf" ? "PDF" : t("workspace.text", "Text"),
      `${t("workspace.page", "Page")}: ${doc.extraction.page_count}`,
      `${t("workspace.size", "Size")}: ${doc.size_bytes} ${t("workspace.bytes", "bytes")}`,
      `${t("workspace.registered", "Registered")}: ${doc.created_at}`,
    ].join(" · ");
    const select = byId("document-page-selector"); clear(select);
    for (let page = 1; page <= doc.extraction.page_count; page += 1) { const option = document.createElement("option"); option.value = page; option.textContent = `${t("workspace.page", "Page")} ${page}`; option.selected = page === state.selectedPage?.page_number; select.append(option); }
    byId("document-page-text").value = state.selectedPage?.normalized_text || t("workspace.choose_page", "Choose a page to inspect.");
    const span = state.selectedSpan, pageNumber = state.selectedPage?.page_number;
    byId("document-selection").textContent = span && Number.isInteger(pageNumber)
      ? humanSourceLocator({ kind: "document_text_span", page_number: pageNumber, start_codepoint: span.start, end_codepoint: span.end })
      : t("workspace.select_span", "Select text to attach a precise source span.");
    byId("document-candidate-form").hidden = !span || !documentCandidateAllowed();
  }

  // One exhaustive document fact-run presentation map, shared by the
  // Documents rows and the Overview attention rows. Recovery actions exist
  // only where the service actually supports re-execution.
  const DOCUMENT_RUN_PRESENTATION = {
    prepared: { labelKey: "workspace.analysis_prepared", tone: "info", action: "continue" },
    consent_required: { labelKey: "workspace.analysis_consent_required", tone: "warning", action: "continue" },
    consented: { labelKey: "workspace.analysis_consented", tone: "info", action: "continue" },
    executing: { labelKey: "workspace.analysis_in_progress", tone: "info", action: "wait" },
    partial: { labelKey: "workspace.ai_partial", tone: "warning", action: "review" },
    // Runtime evidence: consent(approve) is a no-op unless the run is
    // consent_required, so a failed external run cannot be re-executed.
    failed: { labelKey: "workspace.analysis_failed", tone: "danger", action: "none" },
    declined: { labelKey: "workspace.analysis_declined", tone: "", action: "none" },
    unavailable: { labelKey: "workspace.ai_unavailable", tone: "warning", action: "none" },
  };
  const DOCUMENT_RUN_HELP = { wait: "workspace.analysis_wait_help", none: "workspace.analysis_source_only_help" };
  const DOCUMENT_ATTENTION_STATES = ["not_analyzed", "prepared", "consent_required", "consented", "partial", "failed", "unavailable"];

  function documentRunStatus(run) {
    return run?.status || "not_analyzed";
  }
  function documentRunPresentation(run) {
    const runStatus = documentRunStatus(run);
    const newCandidates = Number.isInteger(run?.new_candidates) ? run.new_candidates : 0;
    if (runStatus === "not_analyzed") return { labelKey: "workspace.ai_not_analyzed", tone: "", action: "analyze", helpKey: "" };
    if (runStatus === "completed") {
      return newCandidates > 0
        ? { labelKey: "workspace.analysis_ready_for_review", tone: "success", action: "review", helpKey: "workspace.analysis_review_help" }
        : { labelKey: "workspace.analysis_complete", tone: "success", action: "open", helpKey: "" };
    }
    const known = DOCUMENT_RUN_PRESENTATION[runStatus];
    if (!known) return { labelKey: "workspace.ai_not_analyzed", tone: "", action: "none", helpKey: "workspace.analysis_source_only_help" };
    if (runStatus === "partial") {
      return { ...known, action: newCandidates > 0 ? "review" : "open", helpKey: newCandidates > 0 ? "workspace.analysis_review_help" : "" };
    }
    return { ...known, helpKey: DOCUMENT_RUN_HELP[known.action] || "" };
  }
  function openDocument(doc, trigger) {
    state.selectedDocument = doc;
    state.selectedPage = null;
    state.selectedSpan = null;
    renderDocumentViewer();
    void loadDocumentPage(doc, 1, trigger);
  }
  function documentRunActions(doc, presentation) {
    const actions = [];
    const canWrite = Boolean(state.capabilities.document_write && state.capabilities.source_write);
    if (["analyze", "continue"].includes(presentation.action)) {
      if (!canWrite) return actions;
      const labelKey = presentation.action === "analyze" ? "workspace.analyze_document" : "workspace.continue_analysis";
      const button = makeButton(t(labelKey), "primary");
      button.addEventListener("click", () => { void analyzeDocumentFromCard(doc, button); });
      actions.push(button);
    } else if (presentation.action === "review") {
      actions.push(makeLink("#review", t("workspace.section_review")));
    } else if (presentation.action === "open") {
      const button = makeButton(t("workspace.open_document"), "secondary");
      button.addEventListener("click", () => { openDocument(doc, button); });
      actions.push(button);
    }
    return actions;
  }
  function documentProvenance(doc, presentation) {
    const details = document.createElement("details");
    details.className = "ui-disclosure workspace-provenance";
    details.append(make("summary", t("workspace.source_provenance", "Source & provenance")));
    details.append(
      make("p", `Source ID: ${doc.source_id}`, "workspace-technical"),
      make("p", `SHA-256: ${doc.content_hash}`, "workspace-technical"),
      make("p", `${t("workspace.size", "Size")}: ${doc.size_bytes} ${t("workspace.bytes", "bytes")}`, "workspace-meta"),
      make("p", `${t("workspace.media_type", "Media type")}: ${doc.media_type}`, "workspace-meta"),
      make("p", `${t("workspace.registered", "Registered")}: ${doc.created_at}`, "workspace-meta"),
      make("p", `${t("workspace.text_extraction", "Text extraction")}: ${doc.extraction.extraction_id} · ${doc.extraction.extractor_version} · ${doc.extraction.status}`, "workspace-technical"),
    );
    const run = doc.fact_extraction;
    if (run) {
      details.append(make("p", `${t("workspace.review_state", "Review state")}: ${t(presentation.labelKey)}`, "workspace-meta"));
      const technical = [];
      if (run.provider_id) technical.push(`${t("workspace.document_provider", "Provider")}: ${run.provider_id}`);
      if (run.model_id) technical.push(`${t("workspace.document_model", "Model")}: ${run.model_id}`);
      if (run.contract_version) technical.push(`${t("workspace.analysis_contract", "Contract")}: ${run.contract_version}`);
      if (run.reason_code) technical.push(`${t("workspace.analysis_reason", "Reason code")}: ${run.reason_code}`);
      if (technical.length) details.append(make("p", technical.join(" · "), "workspace-technical"));
    }
    return details;
  }
  function documentRow(doc) {
    const run = doc.fact_extraction, presentation = documentRunPresentation(run);
    const { row, main } = rowShell("");
    main.append(make("h4", doc.original_filename || t("workspace.page_text", "Untitled document"), "ui-row__title"));
    const statusLine = make("p", "", "ui-row__status");
    statusLine.append(makeStatusBadge(t(presentation.labelKey), presentation.tone));
    statusLine.append(makeStatusBadge(`${t("workspace.text_extraction", "Text extraction")}: ${t("workspace.text_ready", "Text ready")}`));
    statusLine.append(make("span", doc.document_kind === "pdf" ? "PDF" : t("workspace.text", "Text"), "ui-row__meta"));
    statusLine.append(make("span", `${t("workspace.page", "Page")}: ${doc.extraction.page_count}`, "ui-row__meta"));
    statusLine.append(make("span", `${t("workspace.registered", "Registered")}: ${doc.created_at}`, "ui-row__meta"));
    main.append(statusLine);
    if (presentation.helpKey) main.append(make("p", t(presentation.helpKey), "ui-row__detail"));
    if (run) {
      const counters = [
        Number.isInteger(run.valid_facts) ? `${t("workspace.valid", "Valid")}: ${run.valid_facts}` : "",
        Number.isInteger(run.invalid_facts) ? `${t("workspace.invalid", "Invalid")}: ${run.invalid_facts}` : "",
        Number.isInteger(run.new_candidates) ? `${t("workspace.new", "New")}: ${run.new_candidates}` : "",
        Number.isInteger(run.reused_candidates) ? `${t("workspace.reused", "Reused")}: ${run.reused_candidates}` : "",
      ].filter(Boolean);
      if (counters.length) main.append(make("p", counters.join(" · "), "ui-row__detail"));
    }
    const staleRun = run?.contract_version === "opencare-document-facts/1" && (run.status === "completed" || run.status === "partial");
    if (staleRun) main.append(make("p", t("workspace.previous_version_notice", "Analyzed with previous extraction version"), "ui-row__meta"));
    main.append(documentProvenance(doc, presentation));
    const actions = documentRunActions(doc, presentation);
    if (staleRun && state.capabilities.document_write && state.capabilities.source_write) {
      const more = makeButton(t("workspace.analyze_more_categories", "Analyze additional categories"), "secondary");
      more.addEventListener("click", () => { void analyzeDocumentFromCard(doc, more); });
      actions.unshift(more);
    }
    if (actions.length) { const group = make("div", "", "ui-row__actions"); group.append(...actions); row.append(group); }
    return row;
  }
  function renderDocuments() {
    const section = byId("documents"), list = byId("document-list"); section.hidden = !state.capabilities.document_read; clear(list);
    byId("document-upload-panel").hidden = !(state.capabilities.document_write && state.capabilities.source_write);
    byId("documents-empty").hidden = state.documents.length > 0;
    state.documents.forEach((doc) => list.append(documentRow(doc)));
    renderDocumentViewer();
  }
  async function loadDocuments(personIdContext) {
    if (!state.capabilities.document_read) { state.documents = []; return []; }
    const response = await request(`/people/${encodeURIComponent(personIdContext)}/documents`, {}, documentContext());
    if (response.documents.some((doc) => doc.person_id !== personIdContext)) return [];
    return Promise.all(response.documents.map(async (doc) => { try { doc.fact_extraction = await request(`/people/${encodeURIComponent(personIdContext)}/documents/${encodeURIComponent(doc.source_id)}/fact-extraction`, {}, documentContext()); } catch (_) { doc.fact_extraction = { status: "not_analyzed" }; } return doc; }));
  }
  function documentDisclosureMessage(prepared) {
    const disclosure = prepared?.preview || prepared || {};
    const categories = Array.isArray(disclosure.enabled_categories)
      ? disclosure.enabled_categories.map((category) => factLabel(category)).join(", ")
      : "";
    return [
      t("workspace.document_external_disclosure", "Analyze this document with the external provider?"),
      `${t("workspace.document_filename", "Filename")}: ${disclosure.safe_filename || disclosure.filename || t("workspace.document", "Document")}`,
      `${t("workspace.document_provider", "Provider")}: ${disclosure.provider_id || t("workspace.value_configured", "Configured")}`,
      `${t("workspace.document_model", "Model")}: ${disclosure.model_id || t("workspace.value_configured", "Configured")}`,
      `${t("workspace.document_external", "External provider")}: ${disclosure.external === true ? t("workspace.value_yes", "Yes") : t("workspace.value_no", "No")}`,
      `${t("workspace.document_pages", "Pages")}: ${Number.isInteger(disclosure.page_count) ? disclosure.page_count : t("workspace.value_none", "None")}`,
      `${t("workspace.document_characters", "Characters")}: ${Number.isInteger(disclosure.character_count) ? disclosure.character_count : t("workspace.value_none", "None")}`,
      `${t("workspace.document_categories", "Enabled categories")}: ${categories || t("workspace.value_none", "None")}`,
      `${t("workspace.document_retention", "Retention")}: ${disclosure.retention === "request_only" ? t("workspace.retention_request_only", "Request only") : t("workspace.retention_provider_policy", "Provider policy")}`,
    ].join("\n");
  }
  async function uploadDocument(event) {
    event.preventDefault();
    if (!state.person || !state.capabilities.document_write || !state.capabilities.source_write) return;
    const file = byId("document-file").files[0], submit = event.submitter;
    if (!file) return;
    setButtonBusy(submit, true);
    try {
      const body = await file.arrayBuffer();
      const filename = OpenCareWorkspaceState.sanitizeDocumentFilename(file.name);
      const uploaded = await personRequest(`/people/${encodeURIComponent(state.person.person_id)}/documents`, { method: "POST", body, headers: { "Content-Type": file.type === "application/pdf" ? "application/pdf" : "text/plain", "X-OpenCare-Filename": filename } });
      const analyzed = await analyzeDocument(uploaded.document.source_id);
      if (!analyzed) { event.target.reset(); await loadWorkspace(); status(t("workspace.document_analysis_declined", "Document stored; analysis was declined."), "success"); return; }
      event.target.reset(); await loadWorkspace(); status(t("workspace.document_uploaded", "Document uploaded."), "success");
    } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); }
  }
  async function analyzeDocumentFromCard(doc, button) {
    if (!state.person || !state.capabilities.document_write || !state.capabilities.source_write) return;
    setButtonBusy(button, true);
    try {
      const analyzed = await analyzeDocument(doc.source_id);
      await loadWorkspace();
      if (!analyzed) status(t("workspace.document_analysis_declined", "Document stored; analysis was declined."), "success");
    } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); setButtonBusy(button, false); }
  }
  async function analyzeDocument(sourceId) {
    const base = `/people/${encodeURIComponent(state.person.person_id)}/documents/${encodeURIComponent(sourceId)}/fact-extractions`;
    const prepared = await personRequest(`${base}/prepare`, { method: "POST", body: "{}" });
    if (prepared.status === "consent_required") {
      const approved = window.confirm(documentDisclosureMessage(prepared));
      await personRequest(`${base}/${encodeURIComponent(prepared.run_id)}/consent`, { method: "POST", body: JSON.stringify({ decision: approved ? "approve" : "decline" }) });
      if (!approved) return false;
    }
    if (!["unavailable", "declined"].includes(prepared.status)) await personRequest(`${base}/${encodeURIComponent(prepared.run_id)}/execute`, { method: "POST", body: "{}" });
    return true;
  }
  async function submitDocumentCandidate(event) {
    event.preventDefault();
    const span = state.selectedSpan, type = byId("document-candidate-type").value;
    if (!state.person || !state.selectedDocument || !state.selectedPage || !span || !documentCandidateAllowed(type)) return;
    const submit = event.submitter; setButtonBusy(submit, true);
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
      event.target.reset(); state.selectedSpan = null; await loadWorkspace(); status(t("workspace.typed_candidate_pending", "Typed candidate is waiting for review."), "success");
    } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); }
  }

  function pruneWorkspaceToCapabilities() {
    if (!state.capabilities.medication_read) Object.assign(state, { candidates: [], medications: [] });
    if (!state.capabilities.condition_read) Object.assign(state, { conditionCandidates: [], conditions: [] });
    if (!state.capabilities.lab_read) Object.assign(state, { labCandidates: [], labs: [] });
    if (!state.capabilities.procedure_read) Object.assign(state, { procedureCandidates: [], procedures: [] });
    if (!state.capabilities.recommendation_read) Object.assign(state, { recommendationCandidates: [], recommendations: [] });
    if (!state.capabilities.follow_up_read) Object.assign(state, { followUpCandidates: [], followUps: [] });
    state.conditionEnabled = Boolean(state.capabilities.condition_read);
    state.labEnabled = Boolean(state.capabilities.lab_read);
    state.procedureEnabled = Boolean(state.capabilities.procedure_read);
    state.recommendationEnabled = Boolean(state.capabilities.recommendation_read);
    state.followUpEnabled = Boolean(state.capabilities.follow_up_read);
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

  // Loading is owned by the Person generation that started it: an aborted or
// stale request can neither show nor hide another Person's loading state.
  function setWorkspaceLoading(loading, generation = state.loadVersion) {
    if (generation !== state.loadVersion) return;
    const skeleton = byId("workspace-loading");
    if (skeleton) skeleton.hidden = !loading;
    byId("workspace-content").setAttribute("aria-busy", loading ? "true" : "false");
  }

  function enableWorkspace(enabled) {
    byId("workspace-content").hidden = !enabled;
    byId("section-navigation").hidden = !enabled;
    byId("workspace-content").setAttribute("aria-disabled", String(!enabled));
    byId("workspace-content").setAttribute("aria-busy", "false");
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
      setWorkspaceLoading(false);
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
    Object.assign(state, { person: { person_id: personId, display_name: t("workspace.loading_person") }, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], procedures: [], recommendations: [], followUps: [], conditionCandidates: [], labCandidates: [], procedureCandidates: [], recommendationCandidates: [], followUpCandidates: [], conditionEnabled: false, labEnabled: false, procedureEnabled: false, recommendationEnabled: false, followUpEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null });
    enableWorkspace(false);
    renderPersonContext();
    const personContext = { personId, generation, signal: state.controller.signal };
    status(t("workspace.loading_workspace"));
    setWorkspaceLoading(true, generation);
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
      if (capabilities.procedure_read) {
        add("procedureCandidates", `/people/${encodeURIComponent(personId)}/procedure-candidates`);
        add("procedures", `/people/${encodeURIComponent(personId)}/procedures?include_inactive=true`);
      }
      if (capabilities.recommendation_read) {
        add("recommendationCandidates", `/people/${encodeURIComponent(personId)}/recommendation-candidates`);
        add("recommendations", `/people/${encodeURIComponent(personId)}/recommendations?include_inactive=true`);
      }
      if (capabilities.follow_up_read) {
        add("followUpCandidates", `/people/${encodeURIComponent(personId)}/follow-up-candidates`);
        add("followUps", `/people/${encodeURIComponent(personId)}/follow-ups?include_inactive=true`);
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
        procedures: (loaded.procedures?.procedures || []).filter((item) => item.person_id === personId),
        recommendations: (loaded.recommendations?.recommendations || []).filter((item) => item.person_id === personId),
        followUps: (loaded.followUps?.follow_ups || []).filter((item) => item.person_id === personId),
        conditionCandidates: (loaded.conditionCandidates?.candidates || []).filter((item) => item.person_id === personId),
        labCandidates: (loaded.labCandidates?.candidates || []).filter((item) => item.person_id === personId),
        procedureCandidates: (loaded.procedureCandidates?.candidates || []).filter((item) => item.person_id === personId),
        recommendationCandidates: (loaded.recommendationCandidates?.candidates || []).filter((item) => item.person_id === personId),
        followUpCandidates: (loaded.followUpCandidates?.candidates || []).filter((item) => item.person_id === personId),
        conditionEnabled: Boolean(capabilities.condition_read),
        labEnabled: Boolean(capabilities.lab_read),
        procedureEnabled: Boolean(capabilities.procedure_read),
        recommendationEnabled: Boolean(capabilities.recommendation_read),
        followUpEnabled: Boolean(capabilities.follow_up_read),
        timeline: (loaded.timeline?.events || []).filter((item) => item.person_id === personId),
        visits: OpenCareWorkspaceState.sortVisits((loaded.visits?.visits || []).filter((item) => item.person_id === personId)),
      });
      const sourceIds = new Set([...visibleCandidates(), ...state.medications, ...state.conditions, ...state.labs, ...state.procedures, ...state.recommendations, ...state.followUps].map((item) => item.source_id).filter(Boolean));
      const sources = await Promise.all([...sourceIds].map(async (sourceId) => [sourceId, await request(`/sources/${encodeURIComponent(sourceId)}`, {}, personContext)]));
      if (!OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion)) return;
      state.sources = new Map(sources);
      renderPersonContext(); renderSelectionEmptyState([state.person]); enableWorkspace(true); render(); setWorkspaceLoading(false, generation); status(t("workspace.workspace_loaded"), "success");
    } catch (error) {
      if (error.name !== "AbortError" && OpenCareWorkspaceState.shouldApplyResponse(generation, state.loadVersion)) {
        Object.assign(state, { person: null, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], procedures: [], recommendations: [], followUps: [], conditionCandidates: [], labCandidates: [], procedureCandidates: [], recommendationCandidates: [], followUpCandidates: [], timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null });
        byId("person-selector").value = "";
        renderPersonContext(); renderSelectionEmptyState([{}]); enableWorkspace(false); render();
        status(error.message, "error");
        setWorkspaceLoading(false, generation);
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
    if (!locator || typeof locator !== "object") return t("workspace.whole_source", "Whole source");
    if (locator.kind === "structured_field" && typeof locator.path === "string") {
      const fields = {
        medication: "workspace.manual_medication_name",
        "data.medication.display_name": "workspace.manual_medication_name",
        "data.condition.display_name": "workspace.manual_condition_name",
        "data.lab.test_name": "workspace.manual_lab_name",
      };
      return t(fields[locator.path], t("workspace.manual_field", "Recorded field in a manual entry"));
    }
    if (locator.kind === "document_text_span" && Number.isInteger(locator.page_number) && Number.isInteger(locator.start_codepoint) && Number.isInteger(locator.end_codepoint)) {
      return `${t("workspace.document_page", "Document page")} ${locator.page_number}, ${t("workspace.codepoints", "codepoints")} ${locator.start_codepoint}–${locator.end_codepoint}`;
    }
    if (locator.kind === "span" && Number.isInteger(locator.start) && Number.isInteger(locator.end) && locator.start >= 0 && locator.end > locator.start) {
      return `${t("workspace.source_text_characters", "Source text characters")} ${locator.start + 1}–${locator.end}`;
    }
    return t("workspace.specific_source_location", "Specific location recorded in the source");
  }

  function provenanceDetails(item) {
    const details = document.createElement("details"), summary = make("summary", t("workspace.source_provenance", "Source & provenance"));
    details.className = "ui-disclosure workspace-provenance";
    const source = state.sources.get(item.source_id);
    details.append(summary, make("p", `Source ID: ${item.source_id}`, "workspace-technical"));
    if (source) {
      const isDocument = source.source_type === "document" || item.provenance_locator?.kind === "document_text_span";
      const mediaLabel = source.media_type === "application/pdf" ? "PDF" : source.media_type === "text/plain" ? t("workspace.text", "Text") : t("workspace.source", "Source");
      details.append(
        make("p", isDocument ? `${t("workspace.document", "Document")} · ${mediaLabel}` : source.source_type === "manual_entry" ? t("workspace.manual_entry", "Manual entry") : t("workspace.source", "Source"), "workspace-meta"),
        make("p", `${t("workspace.registered", "Registered")}: ${source.created_at}`, "workspace-meta"),
        make("p", `SHA-256: ${source.content_hash}`, "workspace-technical"),
        make("p", `${t("workspace.size", "Size")}: ${source.size_bytes} ${t("workspace.bytes", "bytes")}`, "workspace-meta"),
        make("p", `${t("workspace.media_type", "Media type")}: ${source.media_type}`, "workspace-meta"),
        make("p", source.integrity_verified ? t("workspace.integrity_verified", "Integrity verified") : t("workspace.integrity_not_verified", "Integrity not verified"), "workspace-meta"),
      );
    } else details.append(make("p", t("workspace.source_metadata_unavailable", "Source metadata unavailable."), "workspace-meta"));
    details.append(make("p", `Source location: ${humanSourceLocator(item.provenance_locator)}`, "workspace-meta"));
    if (item.predecessor_candidate_id) {
      const lineage = Object.hasOwn(item, "status")
        ? "Correction lineage: correction of an earlier reviewed candidate."
        : "Correction lineage: confirmed from a reviewed correction of an earlier record.";
      details.append(make("p", lineage, "workspace-meta"));
    }
    if (item.superseded_by_record_id) details.append(make("p", t("workspace.correction_superseded", "Correction lineage: superseded by a newer confirmed record."), "workspace-meta"));
    return details;
  }

  function rowShell(rowClass) {
    const row = make("article", "", rowClass ? `ui-row workspace-row ${rowClass}` : "ui-row workspace-row");
    const main = make("div", "", "ui-row__main");
    row.append(main);
    return { row, main };
  }

  function factCandidateCard(candidate, actions) {
    const { row, main } = rowShell("");
    const name = candidate.fact_type === "lab" ? candidate.test_name : candidate.display_name || candidate.instruction_text || candidate.action_text;
    main.append(make("h4", name, "ui-row__title"));
    const statusLine = make("p", "", "ui-row__status");
    if (candidate.status === "pending" && candidate.provenance_locator?.kind === "document_text_span") statusLine.append(makeStatusBadge(`${t("workspace.from_document", "From document")} · ${t("workspace.ai_extracted", "AI extracted")} · ${t("workspace.not_confirmed", "Not confirmed")}`, "info"));
    const lifecycleTone = candidate.status === "confirmed" || candidate.status === "corrected" ? "success" : candidate.status === "rejected" || candidate.status === "unsupported" ? "danger" : "warning";
    statusLine.append(makeStatusBadge(`${t("workspace.status", "Status")}: ${statusLabel(candidate.status)}`, lifecycleTone));
    statusLine.append(make("span", `${t("workspace.fact", "Fact")}: ${factLabel(candidate.fact_type)}`, "ui-row__meta"));
    statusLine.append(make("span", `${t("workspace.created", "Created")}: ${candidate.created_at}`, "ui-row__meta"));
    main.append(statusLine);
    if (candidate.fact_type === "medication" && candidate.schedule_text) main.append(make("p", candidate.schedule_text, "ui-row__detail"));
    if (candidate.fact_type === "condition") { if (candidate.status_text) main.append(make("p", `${t("workspace.recorded_status", "Recorded status")}: ${candidate.status_text}`, "ui-row__detail")); if (candidate.onset_date) main.append(make("p", `${t("workspace.recorded_onset", "Recorded onset")}: ${candidate.onset_date}`, "ui-row__detail")); }
    if (candidate.fact_type === "lab") { if (candidate.result_text) main.append(make("p", `${t("workspace.result_reported", "Result as reported")}: ${candidate.result_text}`, "ui-row__detail")); if (candidate.unit_text) main.append(make("p", `${t("workspace.unit_reported", "Unit as reported")}: ${candidate.unit_text}`, "ui-row__detail")); if (candidate.reference_range_text) main.append(make("p", `${t("workspace.reference_range_reported", "Reference range as reported")}: ${candidate.reference_range_text}`, "ui-row__detail")); if (candidate.observed_date) main.append(make("p", `${t("workspace.observed", "Observed")}: ${candidate.observed_date}`, "ui-row__detail")); if (candidate.source_flag_text) main.append(make("p", `${t("workspace.flag_reported", "Flag as reported")}: ${candidate.source_flag_text}`, "ui-row__detail")); }
    if (candidate.fact_type === "procedure") { if (candidate.status_text) main.append(make("p", `${t("workspace.recorded_status", "Recorded status")}: ${candidate.status_text}`, "ui-row__detail")); if (candidate.date_text) main.append(make("p", `${t("workspace.recorded_date", "Recorded date")}: ${candidate.date_text}`, "ui-row__detail")); }
    if (candidate.fact_type === "recommendation") { if (candidate.context_text) main.append(make("p", `${t("workspace.context", "Context")}: ${candidate.context_text}`, "ui-row__detail")); }
    if (candidate.fact_type === "follow_up") { if (candidate.timing_text) main.append(make("p", `${t("workspace.timing", "Timing")}: ${candidate.timing_text}`, "ui-row__detail")); if (candidate.destination_text) main.append(make("p", `${t("workspace.destination", "Destination")}: ${candidate.destination_text}`, "ui-row__detail")); }
    if (candidate.note) main.append(make("p", candidate.note, "ui-row__detail"));
    main.append(provenanceDetails(candidate));
    const buttons = [];
    if (actions) {
      const familyWrite = state.capabilities[`${candidate.fact_type}_write`];
      if (state.capabilities.candidate_review && familyWrite) {
        const confirm = makeButton(t("workspace.confirm_record", "Confirm record"), "primary");
        confirm.addEventListener("click", () => transition(candidate, "confirm", confirm));
        buttons.push(confirm);
      }
      if (state.capabilities.candidate_review && familyWrite) {
        const correct = makeButton(t("workspace.correct_record", "Create correction"), "secondary");
        correct.addEventListener("click", () => openCorrection(candidate, correct));
        buttons.push(correct);
      }
      if (state.capabilities.candidate_review) {
        const reject = makeButton(t("workspace.reject_candidate", "Reject candidate"), "danger"), unsupported = makeButton(t("workspace.mark_unsupported", "Mark unsupported by source"), "secondary");
        reject.addEventListener("click", () => transition(candidate, "reject", reject));
        unsupported.addEventListener("click", () => transition(candidate, "unsupported", unsupported));
        buttons.push(reject, unsupported);
      }
    }
    if (buttons.length) { const group = make("div", "", "ui-row__actions"); group.append(...buttons); row.append(group); }
    return row;
  }

  function factRecordCard(record, factType, historical) {
    const { row, main } = rowShell(historical ? "workspace-row--historical" : "");
    const name = factType === "lab" ? record.test_name : record.display_name || record.instruction_text || record.action_text;
    main.append(make("h4", name, "ui-row__title"));
    const statusLine = make("p", "", "ui-row__status");
    statusLine.append(makeStatusBadge(historical ? t("workspace.superseded", "Superseded") : t("workspace.confirmed", "Confirmed"), historical ? "" : "success"));
    statusLine.append(make("span", `${t("workspace.confirmed_at", "Confirmed")}: ${record.confirmed_at}`, "ui-row__meta"));
    main.append(statusLine);
    if (factType === "condition") { if (record.status_text) main.append(make("p", `${t("workspace.recorded_status", "Recorded status")}: ${record.status_text}`, "ui-row__detail")); if (record.onset_date) main.append(make("p", `${t("workspace.recorded_onset", "Recorded onset")}: ${record.onset_date}`, "ui-row__detail")); }
    if (factType === "lab") { if (record.result_text) main.append(make("p", `${t("workspace.result_reported", "Result as reported")}: ${record.result_text}`, "ui-row__detail")); if (record.unit_text) main.append(make("p", `${t("workspace.unit_reported", "Unit as reported")}: ${record.unit_text}`, "ui-row__detail")); if (record.reference_range_text) main.append(make("p", `${t("workspace.reference_range_reported", "Reference range as reported")}: ${record.reference_range_text}`, "ui-row__detail")); if (record.observed_date) main.append(make("p", `${t("workspace.observed", "Observed")}: ${record.observed_date}`, "ui-row__detail")); if (record.source_flag_text) main.append(make("p", `${t("workspace.flag_reported", "Flag as reported")}: ${record.source_flag_text}`, "ui-row__detail")); }
    if (factType === "procedure") { if (record.status_text) main.append(make("p", `${t("workspace.recorded_status", "Recorded status")}: ${record.status_text}`, "ui-row__detail")); if (record.date_text) main.append(make("p", `${t("workspace.recorded_date", "Recorded date")}: ${record.date_text}`, "ui-row__detail")); }
    if (factType === "recommendation") { if (record.context_text) main.append(make("p", `${t("workspace.context", "Context")}: ${record.context_text}`, "ui-row__detail")); }
    if (factType === "follow_up") { if (record.timing_text) main.append(make("p", `${t("workspace.timing", "Timing")}: ${record.timing_text}`, "ui-row__detail")); if (record.destination_text) main.append(make("p", `${t("workspace.destination", "Destination")}: ${record.destination_text}`, "ui-row__detail")); }
    if (record.note) main.append(make("p", record.note, "ui-row__detail"));
    main.append(provenanceDetails(record));
    return row;
  }

  function visibleCandidates() {
    const list = state.candidates.slice();
    if (state.conditionEnabled) list.push(...state.conditionCandidates);
    if (state.labEnabled) list.push(...state.labCandidates);
    if (state.procedureEnabled) list.push(...state.procedureCandidates);
    if (state.recommendationEnabled) list.push(...state.recommendationCandidates);
    if (state.followUpEnabled) list.push(...state.followUpCandidates);
    return list;
  }

  function syncFactTypeFilters() {
    const facts = FACT_ORDER.filter((fact) => state.capabilities[`${fact}_read`]);
    const select = byId("inbox-fact-filter");
    const current = select.value;
    clear(select);
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = t("workspace.all_fact_types", "All fact types");
    select.append(all);
    facts.forEach((fact) => {
      const option = document.createElement("option");
      option.value = fact;
      option.textContent = factLabel(fact);
      select.append(option);
    });
    select.value = facts.includes(current) ? current : "all";
  }

  async function submitCondition(event) {
    event.preventDefault();
    if (!state.person || !state.capabilities.condition_write || !state.capabilities.source_write || !state.capabilities.candidate_review) return;
    const submit = event.submitter;
    setButtonBusy(submit, true);
    const display_name = byId("condition-display-name").value, status_text = byId("condition-status-text").value || null, onset_date = byId("condition-onset-date").value || null, note = byId("condition-note").value || null;
    try {
      const source = await personRequest("/sources/manual-condition", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, condition: { display_name, status_text, onset_date, note } }) });
      await personRequest("/candidates/conditions", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, display_name, status_text, onset_date, note }) });
      event.target.reset();
      await loadWorkspace();
      status(t("workspace.condition_pending", "Condition entry is waiting for review."), "success");
    } catch (error) { status(error.message, "error"); } finally { setButtonBusy(submit, false); }
  }

  async function submitLab(event) {
    event.preventDefault();
    if (!state.person || !state.capabilities.lab_write || !state.capabilities.source_write || !state.capabilities.candidate_review) return;
    const submit = event.submitter;
    setButtonBusy(submit, true);
    const test_name = byId("lab-test-name").value, result_text = byId("lab-result-text").value, unit_text = byId("lab-unit-text").value || null, reference_range_text = byId("lab-reference-range-text").value || null, observed_date = byId("lab-observed-date").value || null, source_flag_text = byId("lab-source-flag-text").value || null, note = byId("lab-note").value || null;
    try {
      const source = await personRequest("/sources/manual-lab", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, lab: { test_name, result_text, unit_text, reference_range_text, observed_date, source_flag_text, note } }) });
      await personRequest("/candidates/labs", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, test_name, result_text, unit_text, reference_range_text, observed_date, source_flag_text, note }) });
      event.target.reset();
      await loadWorkspace();
      status(t("workspace.lab_pending", "Lab entry is waiting for review."), "success");
    } catch (error) { status(error.message, "error"); } finally { setButtonBusy(submit, false); }
  }

  function renderFactSections() {
    const families = { medication: state.medications, condition: state.conditions, lab: state.labs, procedure: state.procedures, recommendation: state.recommendations, follow_up: state.followUps };
    Object.entries(families).forEach(([factType, records]) => {
      const readable = Boolean(state.capabilities[`${factType}_read`]);
      const section = byId(`records-${factType.replaceAll("_", "-")}`);
      const addButton = section.querySelector("[data-toggle-form]");
      const activeTarget = byId(`${factType}-current`), historyTarget = byId(`${factType}-historical`);
      section.hidden = !readable;
      clear(activeTarget); clear(historyTarget);
      if (!readable) {
        if (addButton) {
          addButton.hidden = true;
          byId(addButton.dataset.toggleForm).hidden = true;
        }
        return;
      }
      if (addButton) addButton.hidden = !(state.capabilities[`${factType}_write`] && state.capabilities.source_write && state.capabilities.candidate_review);
      const active = records.filter((item) => item.is_active);
      const historical = records.filter((item) => !item.is_active);
      if (!active.length) activeTarget.append(make("p", t("workspace.no_current_records", "No current confirmed records."), "workspace-note"));
      active.forEach((item) => activeTarget.append(factRecordCard(item, factType, false)));
      if (!historical.length) historyTarget.append(make("p", t("workspace.no_historical_records", "No historical or superseded records."), "workspace-note"));
      historical.forEach((item) => historyTarget.append(factRecordCard(item, factType, true)));
      const historyCount = byId(`${factType}-history-count`);
      historyCount.textContent = `(${historical.length})`;
    });
  }
  function localizeWorkspaceChrome() {
    const sections = [
      ["review-title", "workspace.section_review", "workspace.review_summary"],
      ["documents-title", "nav.documents", "workspace.documents_summary"],
      ["records-title", "workspace.section_records", "workspace.records_summary"],
      ["timeline-title", "workspace.section_timeline", "workspace.timeline_summary"],
      ["visits-title", "workspace.section_visits", "workspace.visits_summary"],
      ["export-title", "workspace.section_export", "workspace.export_summary"],
    ];
    sections.forEach(([id, titleKey, summaryKey]) => {
      const title = byId(id);
      if (!title) return;
      title.textContent = t(titleKey);
      const summary = title.closest(".workspace-section__heading")?.querySelector("p");
      if (summary) summary.textContent = t(summaryKey);
    });
    [
      ["records-medication", "workspace.medications"],
      ["records-condition", "workspace.conditions"],
      ["records-lab", "workspace.labs"],
      ["records-procedure", "workspace.procedures"],
      ["records-recommendation", "workspace.recommendations"],
      ["records-follow-up", "workspace.follow_up"],
    ].forEach(([id, key]) => {
      const title = byId(id)?.querySelector(".workspace-family__heading h3");
      if (title) title.textContent = t(key);
    });
  }


  function render() {
    const inbox = byId("review-inbox"), timeline = byId("timeline-list");
    clear(inbox); clear(timeline);
    localizeWorkspaceChrome(); renderOverview(); renderFactSections(); renderDocuments(); syncFactTypeFilters();
    const all = visibleCandidates(), inboxFact = byId("inbox-fact-filter").value, inboxStatus = byId("inbox-status-filter").value, search = byId("review-search").value.trim().toLocaleLowerCase();
    const inboxItems = all.filter((item) => (inboxFact === "all" || item.fact_type === inboxFact) && (inboxStatus === "all" || item.status === inboxStatus) && (!search || [item.display_name, item.test_name, item.note, item.result_text].some((value) => String(value || "").toLocaleLowerCase().includes(search))));
    if (!inboxItems.length) inbox.append(make("p", inboxStatus === "pending" ? t("workspace.pending_empty") : t("workspace.no_entries_match", "No entries match this view."), "meta"));
    inboxItems.forEach((item) => inbox.append(factCandidateCard(item, item.status === "pending")));
    const timelineFilter = byId("timeline-filter").value;
    const timelineItems = state.timeline.filter((item) => timelineFilter === "all" || item.fact_type === timelineFilter);
    if (!timelineItems.length) timeline.append(make("p", t("workspace.activity_empty"), "workspace-note"));
    timelineItems.forEach((item) => {
      const { row, main } = rowShell("");
      main.append(make("h4", eventTitle(item), "ui-row__title"));
      const time = document.createElement("time");
      time.dateTime = item.event_at;
      time.textContent = item.event_at;
      time.className = "ui-row__meta";
      const statusLine = make("p", "", "ui-row__status");
      statusLine.append(time);
      if (item.fact_type) statusLine.append(make("span", `${t("workspace.fact", "Fact")}: ${factLabel(item.fact_type)}`, "ui-row__meta"));
      statusLine.append(make("span", t("workspace.recorded_in_opencare", "Recorded in OpenCare"), "ui-row__meta"));
      main.append(statusLine);
      if (item.onset_date) main.append(make("p", `${t("workspace.onset_date", "Onset date (as recorded)")}: ${item.onset_date}`, "ui-row__detail"));
      if (item.observed_date) main.append(make("p", `${t("workspace.observed_date", "Observed date (as reported)")}: ${item.observed_date}`, "ui-row__detail"));
      if (item.fact_type && state.capabilities[`${item.fact_type}_read`]) {
        const actions = make("div", "", "ui-row__actions");
        actions.append(makeLink("#records", `${t("workspace.open_records", "Open records")}: ${factLabel(item.fact_type)}`));
        row.append(actions);
      }
      timeline.append(row);
    });
    const chatNavigation = byId("chat-navigation"); if (chatNavigation) chatNavigation.hidden = !state.capabilities.chat_use;
    byId("timeline").hidden = !state.capabilities.timeline_read; byId("visits-brief").hidden = !state.capabilities.visit_read; byId("persisted-visit-brief").hidden = !(state.capabilities.visit_read && state.capabilities.brief_read); byId("export").hidden = !state.capabilities.vault_export; byId("edit-profile").hidden = !state.capabilities.person_update;
    renderVisitPlanning(); renderPersistedBrief();
  }

  function renderOverview() {
    const attentionList = byId("overview-attention-list"), counts = byId("overview-counts"), latest = byId("overview-latest"), empty = byId("overview-empty"), actionLinks = byId("overview-action-links"), activity = byId("overview-activity-list");
    [attentionList, counts, latest, actionLinks, activity].forEach(clear);
    const readableTypes = FACT_ORDER.filter((type) => state.capabilities[`${type}_read`]);
    const records = [...state.medications, ...state.conditions, ...state.labs, ...state.procedures, ...state.recommendations, ...state.followUps].filter((item) => item.is_active);
    const pending = visibleCandidates().filter((item) => item.status === "pending").length;
    const canAddDocuments = Boolean(state.capabilities.document_write && state.capabilities.source_write);

    // Attention first: only states the API actually reports, with the
    // recovery action the service actually supports.
    const attentionRow = (label, meta, linkHref, linkLabel) => {
      const { row, main } = rowShell("");
      main.append(make("h4", label, "ui-row__title"));
      if (meta) main.append(make("p", meta, "ui-row__meta"));
      if (linkHref) { const actions = make("div", "", "ui-row__actions"); actions.append(makeLink(linkHref, linkLabel)); row.append(actions); }
      attentionList.append(row);
    };
    if (pending) attentionRow(t("workspace.metric_pending"), `${pending} ${t("workspace.pending_count", "waiting for review")}`, "#review", t("workspace.section_review"));
    state.documents.forEach((doc) => {
      const run = doc.fact_extraction, runStatus = documentRunStatus(run);
      if (!DOCUMENT_ATTENTION_STATES.includes(runStatus)) return;
      if (runStatus === "not_analyzed" && !canAddDocuments) return;
      const presentation = documentRunPresentation(run);
      const { row, main } = rowShell("");
      main.append(make("h4", doc.original_filename || t("workspace.page_text", "Untitled document"), "ui-row__title"));
      const statusLine = make("p", "", "ui-row__status");
      statusLine.append(makeStatusBadge(t(presentation.labelKey), presentation.tone));
      main.append(statusLine);
      if (presentation.helpKey) main.append(make("p", t(presentation.helpKey), "ui-row__detail"));
      row.append(main);
      const actions = documentRunActions(doc, presentation);
      if (actions.length) { const group = make("div", "", "ui-row__actions"); group.append(...actions); row.append(group); }
      attentionList.append(row);
    });
    if (!attentionList.childElementCount) attentionRow(t("workspace.attention_clear"), "", "", "");

    const summaryRow = (label, value, href) => {
      const { row, main } = rowShell("");
      main.append(makeLink(href, label, "ui-row__title workspace-row-link"), make("p", value, "ui-row__meta"));
      counts.append(row);
    };
    if (readableTypes.length) summaryRow(t("workspace.metric_records"), `${records.length} ${t("workspace.records_count", "records")}`, "#records");
    if (state.capabilities.document_read) summaryRow(t("workspace.metric_documents"), `${state.documents.length} ${t("workspace.documents_count", "documents")}`, "#documents");
    if (state.capabilities.timeline_read) summaryRow(t("workspace.metric_activity"), `${state.timeline.length} ${t("workspace.activity_count", "events")}`, "#timeline");
    if (state.capabilities.visit_read && state.visit) summaryRow(t("workspace.selected_visit"), state.visit.title, "#visits-brief");

    const hasData = records.length > 0 || state.documents.length > 0 || state.timeline.length > 0 || pending > 0;
    empty.hidden = hasData;
    if (records.length) {
      const newest = OpenCareWorkspaceState.sortNewest(records, "confirmed_at", "id")[0];
      latest.append(make("p", `${t("workspace.latest_record")}: ${newest.confirmed_at}`, "workspace-meta"));
    }
    latest.hidden = !latest.childElementCount;

    const action = (href, label, id = "") => {
      const link = makeLink(href, label);
      if (id) link.id = id;
      actionLinks.append(link);
    };
    if (state.capabilities.document_read && state.capabilities.document_write && state.capabilities.source_write) action("#documents", t("workspace.add_document"));
    if (readableTypes.length) action("#records", t("workspace.open_records"));
    action("/genetics", t("workspace.open_genetics"));
    if (state.capabilities.chat_use) action("/chat", t("workspace.ask_opencare"), "chat-navigation");
    action("/family-access", t("workspace.family_access"));

    if (!state.capabilities.timeline_read || !state.timeline.length) {
      activity.append(make("p", t("workspace.no_recent_activity"), "workspace-note"));
    } else {
      OpenCareWorkspaceState.sortNewest(state.timeline, "event_at", "id").slice(0, 3).forEach((item) => {
        const { row, main } = rowShell("");
        const time = document.createElement("time");
        time.dateTime = item.event_at;
        time.textContent = item.event_at;
        time.className = "ui-row__meta";
        main.append(make("h4", eventTitle(item), "ui-row__title"), time);
        activity.append(row);
      });
    }
  }

  function renderVisitPlanning() {
    const visits = byId("visits"), questions = byId("visit-questions"), canWrite = state.capabilities.visit_write;
    clear(visits); clear(questions); byId("open-visit-form").hidden = !canWrite;
    if (!state.visits.length) visits.append(make("p", t("workspace.no_visits", "No visits have been created for this profile."), "workspace-note"));
    state.visits.forEach((visit) => {
      const selected = state.visit?.visit_id === visit.visit_id;
      const { row, main } = rowShell("workspace-row--visit");
      if (selected) row.setAttribute("aria-current", "true");
      main.append(make("h4", visit.title, "ui-row__title"));
      const statusLine = make("p", "", "ui-row__status");
      if (selected) statusLine.append(makeStatusBadge(t("workspace.selected_visit_button", "Selected visit"), "info"));
      statusLine.append(make("span", visit.specialist || t("workspace.no_specialist", "No specialist"), "ui-row__meta"));
      statusLine.append(make("span", visit.scheduled_date || t("workspace.no_scheduled_date", "No scheduled date"), "ui-row__meta"));
      main.append(statusLine);
      if (!selected) {
        const select = makeButton(t("workspace.select_visit", "Select visit"), "secondary");
        select.addEventListener("click", () => selectVisit(visit, select));
        const actions = make("div", "", "ui-row__actions");
        actions.append(select);
        row.append(actions);
      }
      visits.append(row);
    });
    const hasVisit = Boolean(state.visit);
    byId("edit-visit-form").hidden = !hasVisit || !canWrite; byId("visit-question-form").hidden = !hasVisit || !canWrite; byId("edit-visit-question-form").hidden = !hasVisit || !canWrite || state.editingQuestion === null;
    if (!hasVisit) return;
    byId("edit-visit-title").value = state.visit.title; byId("edit-visit-specialist").value = state.visit.specialist || ""; byId("edit-visit-date").value = state.visit.scheduled_date || ""; byId("selected-visit-label").textContent = `${t("workspace.questions_for", "Questions for")}: ${state.visit.title}`;
    if (!state.questions.length) questions.append(make("p", t("workspace.no_questions", "No questions have been added for this visit."), "workspace-note"));
    OpenCareWorkspaceState.sortQuestions(state.questions).forEach((question, index, sorted) => {
      const { row, main } = rowShell("");
      main.append(make("h4", `${t("workspace.question", "Question")} ${index + 1}`, "ui-row__title"), make("p", question.question_text, "ui-row__detail"));
      if (canWrite) {
        const edit = makeButton(t("workspace.edit", "Edit"), "secondary"), up = makeButton(t("workspace.move_question_up", "Move question up"), "secondary"), down = makeButton(t("workspace.move_question_down", "Move question down"), "secondary"), remove = makeButton(t("workspace.remove", "Remove"), "danger");
        up.disabled = index === 0; down.disabled = index === sorted.length - 1;
        edit.addEventListener("click", () => openQuestionEdit(question, edit)); up.addEventListener("click", () => moveQuestion(question, sorted[index - 1]?.position ?? question.position, up)); down.addEventListener("click", () => moveQuestion(question, sorted[index + 1]?.position ?? question.position, down)); remove.addEventListener("click", () => removeQuestion(question, remove));
        const actions = make("div", "", "ui-row__actions");
        actions.append(edit, up, down, remove);
        row.append(actions);
      }
      questions.append(row);
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
    if (!staleness || staleness.state === "unavailable") return t("workspace.revision_unavailable", "Revision unavailable");
    if (staleness.state === "current") return t("workspace.current", "Current");
    return staleness.reasons?.includes("record_or_source_changed") ? t("workspace.selected_record_changed", "Selected record or source changed") : t("workspace.evidence_changed", "Evidence changed since this revision");
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
    if (!eligible.length) target.append(make("p", t("workspace.no_eligible_evidence", "No eligible confirmed evidence."), "workspace-note"));
    eligible.forEach((item) => { const label = document.createElement("label"), input = document.createElement("input"); input.type = "checkbox"; input.name = "brief-record"; input.value = item.canonical_record_id || item.id; input.checked = selectedIds.includes(input.value); input.disabled = !state.capabilities.brief_write; label.append(input, document.createTextNode(` ${item.display_name || item.test_name || t("workspace.evidence_record", "Evidence record")}`)); target.append(label); });
  }
  function renderPersistedBrief() {
    const hasVisit = Boolean(state.visit), hasBrief = Boolean(state.persistedBrief), canWrite = state.capabilities.brief_write;
    byId("initialize-brief").hidden = !hasVisit || hasBrief || !canWrite; byId("initialize-brief").disabled = !hasVisit || !canWrite; byId("brief-workflow").hidden = !hasBrief;
    byId("brief-status").textContent = !hasVisit ? t("workspace.select_visit_brief", "Select a Visit to prepare its Brief.") : !hasBrief ? (canWrite ? t("workspace.initialize_persistent_brief", "Initialize a persistent Brief for this Visit.") : t("workspace.no_persistent_brief", "No persistent Brief is available for this Visit.")) : state.briefRevision ? `${t("workspace.revision_viewing", "Viewing revision")} ${state.briefRevision.revision_number}. ${stalenessLabel(state.briefRevision.staleness)}` : t("workspace.select_confirmed_evidence", "Select confirmed evidence");
    const content = state.briefRevision?.content || {};
    const selectedIds = [...(content.medications || []), ...(content.conditions || []), ...(content.labs || []), ...(content.procedures || []), ...(content.recommendations || []), ...(content.follow_ups || []), ...(content.records || [])].map((record) => record.canonical_record_id || record.id).filter(Boolean);
    renderEvidenceGroup("medication", factLabel("medication"), selectedIds); renderEvidenceGroup("condition", factLabel("condition"), selectedIds); renderEvidenceGroup("lab", factLabel("lab"), selectedIds); renderEvidenceGroup("procedure", factLabel("procedure"), selectedIds); renderEvidenceGroup("recommendation", factLabel("recommendation"), selectedIds); renderEvidenceGroup("follow_up", factLabel("follow_up"), selectedIds);
    byId("brief-evidence-selection").disabled = !hasBrief || !canWrite; byId("validate-brief-evidence").hidden = !canWrite; byId("generate-brief").hidden = !canWrite; byId("brief-preparation-notes").disabled = !state.briefRevision || !canWrite; byId("save-brief-notes").hidden = !canWrite; byId("save-brief-notes").disabled = !state.briefRevision || !state.briefDirty; byId("download-brief").hidden = !state.capabilities.brief_export; byId("brief-unsaved-warning").hidden = !state.briefDirty;
    if (state.briefRevision) { if (!state.briefDirty) byId("brief-preparation-notes").value = content.preparation_notes || ""; byId("brief-metadata").textContent = `${t("workspace.revision", "Revision")} ${state.briefRevision.revision_number} · ${originLabel(state.briefRevision.origin)} · ${stalenessLabel(state.briefRevision.staleness)}`; byId("brief-markdown").textContent = state.briefRevision.markdown; byId("brief-result").hidden = false; } else byId("brief-result").hidden = true;
    renderBriefRevisions();
  }

  function renderBriefRevisions() {
    const target = byId("brief-revisions"); clear(target); const revisions = state.persistedBrief?.revisions || [];
    if (!state.persistedBrief || !revisions.length) { target.append(make("p", state.persistedBrief ? t("workspace.no_revisions", "No revisions have been created.") : "", "workspace-note")); return; }
    revisions.forEach((revision) => {
      const { row, main } = rowShell("");
      main.append(make("h4", `${t("workspace.revision", "Revision")} ${revision.revision_number} · ${originLabel(revision.origin)}`, "ui-row__title"));
      const statusLine = make("p", "", "ui-row__status");
      statusLine.append(makeStatusBadge(stalenessLabel(revision.staleness), revision.staleness?.state === "stale" ? "warning" : ""));
      main.append(statusLine);
      const actions = make("div", "", "ui-row__actions");
      const view = makeButton(`${t("workspace.view_revision", "View revision")} ${revision.revision_number}`, "secondary");
      view.addEventListener("click", () => loadBriefRevision(revision.revision_number, view));
      actions.append(view);
      if (state.capabilities.brief_write) {
        const restore = makeButton(`${t("workspace.restore_revision", "Restore revision")} ${revision.revision_number}`, "secondary");
        restore.disabled = revision.revision_number === state.persistedBrief.current_revision_number;
        restore.addEventListener("click", () => restoreBriefRevision(revision.revision_number, restore));
        actions.append(restore);
      }
      row.append(actions);
      target.append(row);
    });
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
    setButtonBusy(trigger, true);
    try { await personRequest(`/visit-questions/${encodeURIComponent(question.question_id)}`, { method: "PATCH", body: JSON.stringify({ position }) }); await selectVisit(state.visit, trigger); status(t("workspace.question_order_updated", "Question order updated."), "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); setButtonBusy(trigger, false); }
  }

  function openQuestionEdit(question, trigger) {
    state.editingQuestion = { question, trigger }; byId("edit-visit-question").value = question.question_text; byId("edit-visit-question-form").hidden = false; byId("edit-visit-question").focus();
  }

  async function removeQuestion(question, trigger) {
    setButtonBusy(trigger, true);
    try { await personRequest(`/visit-questions/${encodeURIComponent(question.question_id)}`, { method: "DELETE" }); await selectVisit(state.visit, trigger); status(t("workspace.question_removed", "Question removed."), "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); setButtonBusy(trigger, false); }
  }

  async function transition(candidate, action, button) {
    if (action === "confirm" && !(state.capabilities.candidate_review && state.capabilities[`${candidate.fact_type}_write`])) return;
    if (action !== "confirm" && !state.capabilities.candidate_review) return;
    if (action === "reject" && !window.confirm(t("workspace.reject_confirm", "Reject this candidate?"))) return;
    setButtonBusy(button, true);
    try { await personRequest(`/candidates/${encodeURIComponent(candidate.id)}/${action}`, { method: "POST", body: "{}" }); await loadWorkspace(); status(action === "unsupported" ? t("workspace.candidate_marked_unsupported", "Candidate marked unsupported by source.") : action === "confirm" ? t("workspace.record_confirmed", "Record confirmed.") : t("workspace.candidate_rejected", "Candidate rejected."), "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(button, false); }
  }

  const CORRECTION_FIELDS = {
    medication: [
      { key: "display_name", label: "workspace.medication_name", input: true, maxLength: 200 },
      { key: "schedule_text", label: "workspace.schedule_optional", input: true, maxLength: 500 },
      { key: "note", label: "workspace.note_optional", input: false, maxLength: 2000 },
    ],
    condition: [
      { key: "display_name", label: "workspace.recorded_condition_name", input: true, maxLength: 200 },
      { key: "status_text", label: "workspace.status_optional_source", input: true, maxLength: 500 },
      { key: "onset_date", label: "workspace.onset_optional", input: true, date: true, maxLength: 0 },
      { key: "note", label: "workspace.note_optional", input: false, maxLength: 2000 },
    ],
    lab: [
      { key: "test_name", label: "workspace.test_name", input: true, maxLength: 200 },
      { key: "result_text", label: "workspace.result_as_reported", input: false, maxLength: 2000 },
      { key: "unit_text", label: "workspace.unit_as_reported", input: true, maxLength: 500 },
      { key: "reference_range_text", label: "workspace.reference_range_as_reported", input: true, maxLength: 500 },
      { key: "observed_date", label: "workspace.observed_date_as_reported", input: true, date: true, maxLength: 0 },
      { key: "source_flag_text", label: "workspace.flag_as_reported", input: true, maxLength: 500 },
      { key: "note", label: "workspace.note_optional", input: false, maxLength: 2000 },
    ],
    procedure: [
      { key: "display_name", label: "workspace.procedure_name", input: true, maxLength: 200 },
      { key: "status_text", label: "workspace.status_optional_source", input: true, maxLength: 500 },
      { key: "date_text", label: "workspace.date_optional_source", input: true, maxLength: 500 },
      { key: "note", label: "workspace.note_optional", input: false, maxLength: 2000 },
    ],
    recommendation: [
      { key: "instruction_text", label: "workspace.instruction", input: false, maxLength: 2000 },
      { key: "context_text", label: "workspace.context_optional", input: false, maxLength: 2000 },
      { key: "note", label: "workspace.note_optional", input: false, maxLength: 2000 },
    ],
    follow_up: [
      { key: "action_text", label: "workspace.action", input: false, maxLength: 2000 },
      { key: "timing_text", label: "workspace.timing_optional", input: true, maxLength: 500 },
      { key: "destination_text", label: "workspace.destination_optional", input: true, maxLength: 500 },
      { key: "note", label: "workspace.note_optional", input: false, maxLength: 2000 },
    ],
  };
  const CORRECTION_ENDPOINTS = { medication: "correct", condition: "correct:condition", lab: "correct:lab", procedure: "correct:procedure", recommendation: "correct:recommendation", follow_up: "correct:follow-up" };

  function openCorrection(candidate, trigger) {
    if (!(state.capabilities.candidate_review && state.capabilities[`${candidate.fact_type}_write`])) return;
    const form = document.createElement("form"); form.className = "workspace-form-surface workspace-correction";
    const specs = CORRECTION_FIELDS[candidate.fact_type] || CORRECTION_FIELDS.medication;
    const controls = specs.map((spec) => {
      const control = document.createElement(spec.input ? "input" : "textarea");
      if (spec.date) control.type = "date"; else if (spec.maxLength) control.maxLength = spec.maxLength;
      control.value = candidate[spec.key] || "";
      return control;
    });
    const name = controls[0], error = make("p", "", "workspace-error"), save = makeButton(t("workspace.save_correction", "Save correction"), "primary"), cancel = makeButton(t("workspace.cancel", "Cancel"), "secondary");
    error.setAttribute("role", "alert");
    const correctionTitles = {
      medication: ["workspace.correct_medication", "Correct medication entry"],
      condition: ["workspace.correct_condition", "Correct condition entry"],
      lab: ["workspace.correct_lab", "Correct lab entry"],
      procedure: ["workspace.correct_procedure", "Correct procedure entry"],
      recommendation: ["workspace.correct_recommendation", "Correct recommendation entry"],
      follow_up: ["workspace.correct_follow_up", "Correct follow-up entry"],
    };
    const titleKey = correctionTitles[candidate.fact_type] || correctionTitles.medication;
    const title = t(titleKey[0], titleKey[1]);
    form.append(make("h3", title));
    specs.forEach((spec, index) => form.append(labelled(t(spec.label, spec.label), controls[index])));
    const actions = make("div", "", "workspace-actions");
    actions.append(save, cancel);
    form.append(error, actions);
    const close = () => { form.remove(); trigger.focus(); };
    cancel.addEventListener("click", close);
    form.addEventListener("submit", async (event) => { event.preventDefault(); setButtonBusy(save, true); error.textContent = ""; const payload = {}; specs.forEach((spec, index) => { payload[spec.key] = controls[index].value || null; }); try { await personRequest(`/candidates/${encodeURIComponent(candidate.id)}/${CORRECTION_ENDPOINTS[candidate.fact_type]}`, { method: "POST", body: JSON.stringify(payload) }); await loadWorkspace(); close(); status(t("workspace.correction_pending", "Correction is waiting for review."), "success"); } catch (failure) { error.textContent = failure.message; } finally { setButtonBusy(save, false); } });
    const host = trigger.closest("article")?.querySelector(".ui-row__main") || trigger.closest("article");
    if (!host) return;
    host.append(form); name.focus();
  }

  async function clearWorkspace() {
    state.controller?.abort();
    state.loadVersion += 1;
    setWorkspaceLoading(false);
    try { await setActivePerson(null); } catch (error) { status(error.message, "error"); return; }
    Object.assign(state, { person: null, capabilities: {}, candidates: [], medications: [], conditions: [], labs: [], procedures: [], recommendations: [], followUps: [], conditionCandidates: [], labCandidates: [], procedureCandidates: [], recommendationCandidates: [], followUpCandidates: [], conditionEnabled: false, labEnabled: false, procedureEnabled: false, recommendationEnabled: false, followUpEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, sources: new Map(), documents: [], selectedDocument: null, selectedPage: null, selectedSpan: null, documentDraft: null, vaultExportTrigger: null, controller: null });
    byId("person-selector").value = ""; byId("edit-profile-form").hidden = true; byId("edit-visit-form").hidden = true; byId("visit-question-form").hidden = true; byId("edit-visit-question-form").hidden = true; byId("vault-export-warning").hidden = true; renderPersonContext(); renderSelectionEmptyState([{}]); updateShellPerson(null); render(); enableWorkspace(false); byId("load-workspace").disabled = true; status(t("workspace.selection_cleared"));
  }

  byId("person-selector").addEventListener("change", () => { byId("load-workspace").disabled = !byId("person-selector").value; void loadWorkspace(); });
  byId("load-workspace").addEventListener("click", loadWorkspace);
  byId("clear-workspace").addEventListener("click", () => { void clearWorkspace(); });
  byId("open-vault-export").addEventListener("click", (event) => { if (!state.person || !state.capabilities.vault_export) return; state.vaultExportTrigger = event.currentTarget; byId("vault-export-warning").hidden = false; byId("confirm-vault-export").focus(); });
  byId("cancel-vault-export").addEventListener("click", () => { byId("vault-export-warning").hidden = true; state.vaultExportTrigger?.focus(); });
  byId("confirm-vault-export").addEventListener("click", async (event) => { if (!state.person || !state.capabilities.vault_export) return; const button = event.currentTarget, personContext = { personId: state.person.person_id, generation: state.loadVersion, signal: state.controller?.signal }; setButtonBusy(button, true); try { const { blob, response } = await requestBlob(`/people/${encodeURIComponent(state.person.person_id)}/vault-export`, { method: "POST", body: "{}" }, personContext); const serverName = OpenCareWorkspaceState.contentDispositionFilename(response.headers.get("Content-Disposition")); const filename = OpenCareWorkspaceState.sanitizeDownloadFilename(serverName, "opencare-person-vault-v5.zip"); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = filename; link.click(); URL.revokeObjectURL(link.href); byId("vault-export-warning").hidden = true; state.vaultExportTrigger?.focus(); status(t("workspace.vault_downloaded", "Vault download prepared."), "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(button, false); } });
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
  byId("create-profile-form").addEventListener("submit", async (event) => { event.preventDefault(); const submit = event.submitter; setButtonBusy(submit, true); try { const person = await request("/people", { method: "POST", body: JSON.stringify({ display_name: byId("create-display-name").value, date_of_birth: byId("create-date-of-birth").value || null, confirm_owner_assignment: byId("create-owner-confirmation").checked }) }); state.person = person; await refreshPeople(person); byId("create-profile-form").reset(); await loadWorkspace(); } catch (error) { status(error.message, "error"); } finally { setButtonBusy(submit, false); } });
  byId("edit-profile").addEventListener("click", () => { if (!state.person || !state.capabilities.person_update) return; byId("edit-display-name").value = state.person.display_name; byId("edit-date-of-birth").value = state.person.date_of_birth || ""; byId("edit-profile-form").hidden = false; byId("edit-display-name").focus(); });
  byId("cancel-edit-profile").addEventListener("click", () => { byId("edit-profile-form").hidden = true; byId("edit-profile").focus(); });
  byId("edit-profile-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person || !state.capabilities.person_update) return; const submit = event.submitter; setButtonBusy(submit, true); try { const person = await personRequest(`/people/${encodeURIComponent(state.person.person_id)}`, { method: "PATCH", body: JSON.stringify({ display_name: byId("edit-display-name").value, date_of_birth: byId("edit-date-of-birth").value || null }) }); state.person = person; await refreshPeople(person); renderPersonContext(); byId("edit-profile-form").hidden = true; status(t("workspace.profile_updated", "Profile updated."), "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); } });
  byId("medication-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person || !state.capabilities.medication_write || !state.capabilities.source_write || !state.capabilities.candidate_review) return; const submit = event.submitter; setButtonBusy(submit, true); const display_name = byId("medication-name").value, schedule_text = byId("medication-schedule").value || null, note = byId("medication-note").value || null; try { const source = await personRequest("/sources/manual-medication", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, medication: { display_name, schedule_text, note } }) }); await personRequest("/candidates/medications", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, display_name, schedule_text, note }) }); event.target.reset(); await loadWorkspace(); status(t("workspace.medication_pending", "Medication entry is waiting for review."), "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); } });
  byId("condition-form").addEventListener("submit", submitCondition);
  byId("lab-form").addEventListener("submit", submitLab);
  byId("visit-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person || !state.capabilities.visit_write) return; const submit = event.submitter; setButtonBusy(submit, true); try { const visit = await personRequest("/visits", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, title: byId("new-visit-title").value, specialist: byId("new-visit-specialist").value || null, scheduled_date: byId("new-visit-date").value || null }) }); event.target.reset(); await refreshVisits(); await selectVisit(visit, submit); status("Visit created.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); } });
  byId("edit-visit-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.visit || !state.capabilities.visit_write) return; const submit = event.submitter; setButtonBusy(submit, true); try { const visit = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}`, { method: "PATCH", body: JSON.stringify({ title: byId("edit-visit-title").value, specialist: byId("edit-visit-specialist").value || null, scheduled_date: byId("edit-visit-date").value || null }) }); state.visit = visit; await refreshVisits(); renderVisitPlanning(); status("Visit updated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); } });
  byId("cancel-edit-visit").addEventListener("click", () => { if (!state.visit) return; byId("edit-visit-title").value = state.visit.title; byId("edit-visit-specialist").value = state.visit.specialist || ""; byId("edit-visit-date").value = state.visit.scheduled_date || ""; byId("edit-visit-title").focus(); });
  byId("visit-question-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.visit || !state.capabilities.visit_write) return; const submit = event.submitter; setButtonBusy(submit, true); try { await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/questions`, { method: "POST", body: JSON.stringify({ question_text: byId("new-visit-question").value }) }); event.target.reset(); await selectVisit(state.visit, submit); status("Question added.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); } });
  byId("edit-visit-question-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.editingQuestion || !state.capabilities.visit_write) return; const submit = event.submitter, editing = state.editingQuestion; setButtonBusy(submit, true); try { await personRequest(`/visit-questions/${encodeURIComponent(editing.question.question_id)}`, { method: "PATCH", body: JSON.stringify({ question_text: byId("edit-visit-question").value }) }); state.editingQuestion = null; byId("edit-visit-question-form").hidden = true; await selectVisit(state.visit, submit); status("Question updated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(submit, false); } });
  byId("cancel-edit-visit-question").addEventListener("click", () => { const trigger = state.editingQuestion?.trigger; state.editingQuestion = null; byId("edit-visit-question-form").hidden = true; if (trigger) trigger.focus(); });
  byId("initialize-brief").addEventListener("click", async (event) => { if (!state.visit || !state.capabilities.brief_write) return; const button = event.currentTarget; setButtonBusy(button, true); try { state.persistedBrief = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief`, { method: "POST", body: "{}" }); state.persistedBrief.revisions = []; state.briefRevision = null; await loadBriefEvidence(); renderPersistedBrief(); status("Visit Brief initialized.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(button, false); } });
  byId("validate-brief-evidence").addEventListener("click", async (event) => { if (!state.visit || !state.capabilities.brief_write) return; const button = event.currentTarget; setButtonBusy(button, true); try { await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/evidence:validate`, { method: "POST", body: JSON.stringify({ selected_record_ids: selectedEvidenceIds() }) }); status("Selected evidence is valid.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(button, false); } });
  byId("generate-brief").addEventListener("click", async (event) => { if (!state.visit || !state.persistedBrief || !state.capabilities.brief_write) return; const button = event.currentTarget; setButtonBusy(button, true); try { state.briefRevision = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions:generate`, { method: "POST", body: JSON.stringify({ selected_record_ids: selectedEvidenceIds(), expected_current_revision_number: state.persistedBrief.current_revision_number }) }); state.persistedBrief.current_revision_number = state.briefRevision.revision_number; state.briefDirty = false; await loadBriefHistory(); renderPersistedBrief(); status("Visit Brief revision generated.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(button, false); } });
  byId("brief-preparation-notes").addEventListener("input", () => { if (!state.capabilities.brief_write) return; state.briefDirty = true; byId("save-brief-notes").disabled = false; byId("brief-unsaved-warning").hidden = false; });
  byId("save-brief-notes").addEventListener("click", async (event) => { if (!state.visit || !state.persistedBrief?.current_revision_number || !state.capabilities.brief_write) return; const button = event.currentTarget; setButtonBusy(button, true); try { state.briefRevision = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions:user-edit`, { method: "POST", body: JSON.stringify({ preparation_notes: byId("brief-preparation-notes").value, expected_current_revision_number: state.persistedBrief.current_revision_number }) }); state.persistedBrief.current_revision_number = state.briefRevision.revision_number; state.briefDirty = false; await loadBriefHistory(); renderPersistedBrief(); status("Preparation notes saved as a new revision.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); } finally { setButtonBusy(button, false); } });
  async function restoreBriefRevision(number, trigger) { if (!state.visit || !state.persistedBrief?.current_revision_number || !state.capabilities.brief_write) return; setButtonBusy(trigger, true); try { state.persistedBrief = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/current`, { method: "POST", body: JSON.stringify({ revision_number: number, expected_current_revision_number: state.persistedBrief.current_revision_number }) }); await loadBriefHistory(); state.briefRevision = await personRequest(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions/${number}`); state.briefDirty = false; renderPersistedBrief(); status("Current Brief revision restored.", "success"); } catch (error) { if (error.name !== "AbortError") status(error.message, "error"); setButtonBusy(trigger, false); } }
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
