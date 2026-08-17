(() => {
  "use strict";

  const api = "/api/product-core/v1";
  const state = { person: null, candidates: [], medications: [], conditions: [], labs: [], conditionCandidates: [], labCandidates: [], conditionEnabled: false, labEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, vaultExportTrigger: null, loadVersion: 0 };
  const byId = (id) => document.getElementById(id);
  const make = (tag, value = "", className = "") => { const node = document.createElement(tag); node.textContent = value; node.className = className; return node; };
  const div = (id) => { const node = document.createElement("div"); node.id = id; return node; };
  const clear = (node) => node.replaceChildren();
  const status = (message, kind = "") => { const target = byId("workspace-status"); target.textContent = message; target.className = kind; };
  const safeError = (response, body) => response.status === 422 ? "Check the entered values and try again." : response.status === 404 ? "That profile or record is not available." : response.status === 409 ? "This record changed. Refresh and try again." : body?.error?.code === "product_core_storage_unavailable" ? "Local storage is temporarily unavailable." : "The request could not be completed. Try again.";
  const csrfToken = () => document.cookie.split("; ").find((item) => item.startsWith("opencare_csrf="))?.split("=").slice(1).join("=") || "";
  const securedOptions = (options = {}) => {
    const method = (options.method || "GET").toUpperCase();
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) headers["X-OpenCare-CSRF"] = csrfToken();
    return { ...options, headers };
  };
  const labelled = (label, control) => { const element = document.createElement("label"); element.textContent = label; element.append(control); return element; };

  async function request(path, options = {}) {
    const response = await fetch(api + path, { credentials: "same-origin", ...securedOptions(options) });
    let body;
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) throw Error(safeError(response, body));
    return body;
  }

  async function requestText(path, options = {}) {
    const response = await fetch(api + path, { credentials: "same-origin", ...securedOptions(options) });
    if (!response.ok) { let body; try { body = await response.json(); } catch (_) {} throw Error(safeError(response, body)); }
    return response.text();
  }

  async function requestBlob(path, options = {}) {
    const response = await fetch(api + path, { credentials: "same-origin", ...securedOptions(options) });
    if (!response.ok) { let body; try { body = await response.json(); } catch (_) {} throw Error(safeError(response, body)); }
    return response.blob();
  }

  // Fact-type-scoped list probe: the server enforces scopes with 401/403/404.
  // Any of those statuses means this actor may not see the fact family, so the
  // probe resolves to null and the UI never renders the section (no leak).
  async function probePersonList(path) {
    const response = await fetch(api + path, { credentials: "same-origin", ...securedOptions() });
    if (response.status === 401 || response.status === 403 || response.status === 404) return null;
    let body;
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) throw Error(safeError(response, body));
    return body;
  }

  function enableWorkspace(enabled) {
    byId("workspace-content").setAttribute("aria-disabled", String(!enabled));
    byId("workspace-content").querySelectorAll("input, textarea, select, button").forEach((item) => { item.disabled = !enabled; });
    byId("edit-profile").disabled = !enabled;
  }

  function renderPeople(people) {
    const selector = byId("person-selector");
    const selectedId = state.person?.person_id || "";
    clear(selector);
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = people.length ? "Select a profile" : "No active profiles yet";
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

  async function refreshPeople(selectedPerson = state.person) {
    const response = await request("/people");
    if (selectedPerson && !response.people.some((person) => person.person_id === selectedPerson.person_id)) state.person = null;
    renderPeople(response.people);
  }

  function renderPersonContext() {
    const target = byId("selected-person");
    if (!state.person) { target.textContent = "No profile selected."; return; }
    target.textContent = state.person.date_of_birth ? `${state.person.display_name} · Date of birth: ${state.person.date_of_birth}` : state.person.display_name;
  }

  async function loadWorkspace() {
    const personId = byId("person-selector").value;
    if (!personId) { status("Select a profile before loading the workspace.", "error"); return; }
    const version = ++state.loadVersion;
    status("Loading workspace…");
    try {
      await setActivePerson(personId);
      const [person, candidates, medications, timeline, visits, conditionProbe, labProbe] = await Promise.all([
        request(`/people/${encodeURIComponent(personId)}`),
        request(`/people/${encodeURIComponent(personId)}/candidates`),
        request(`/people/${encodeURIComponent(personId)}/medications`),
        request(`/people/${encodeURIComponent(personId)}/timeline`),
        request(`/people/${encodeURIComponent(personId)}/visits`),
        probePersonList(`/people/${encodeURIComponent(personId)}/conditions`),
        probePersonList(`/people/${encodeURIComponent(personId)}/labs`),
      ]);
      if (version !== state.loadVersion) return;
      const conditionEnabled = conditionProbe !== null;
      const labEnabled = labProbe !== null;
      const conditionCandidates = conditionEnabled ? (await request(`/people/${encodeURIComponent(personId)}/condition-candidates`)).candidates : [];
      const labCandidates = labEnabled ? (await request(`/people/${encodeURIComponent(personId)}/lab-candidates`)).candidates : [];
      if (version !== state.loadVersion) return;
      Object.assign(state, {
        person,
        candidates: candidates.candidates.filter((item) => item.fact_type === "medication"),
        medications: medications.medications,
        timeline: timeline.events,
        visits: visits.visits,
        conditions: conditionEnabled ? conditionProbe.conditions : [],
        labs: labEnabled ? labProbe.labs : [],
        conditionCandidates,
        labCandidates,
        conditionEnabled,
        labEnabled,
        visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false,
      });
      renderPersonContext(); render(); enableWorkspace(true); status("Workspace loaded.", "success");
    } catch (error) { status(error.message, "error"); }
  }

  async function setActivePerson(personId) {
    const response = await fetch("/api/family-access/v1/active-person", {
      credentials: "same-origin",
      ...securedOptions({ method: "PUT", body: JSON.stringify({ person_id: personId }) }),
    });
    if (!response.ok) throw Error("That profile is not available.");
  }

  function provenanceLabel(candidate) {
    const locator = candidate.provenance_locator;
    return locator ? `Provenance: ${JSON.stringify(locator)}` : "Provenance: whole source";
  }

  function factCandidateCard(candidate, actions) {
    const card = make("article", "", "record");
    const name = candidate.fact_type === "lab" ? candidate.test_name : candidate.display_name;
    card.append(make("strong", name));
    card.append(make("p", `Fact: ${candidate.fact_type} · Status: ${candidate.status} · Person: ${state.person?.display_name || ""} · Source: ${candidate.source_id} · Created: ${candidate.created_at}`, "meta"));
    if (candidate.fact_type === "medication") {
      if (candidate.schedule_text) card.append(make("p", candidate.schedule_text));
    } else if (candidate.fact_type === "condition") {
      if (candidate.status_text) card.append(make("p", `Status: ${candidate.status_text}`));
      if (candidate.onset_date) card.append(make("p", `Onset: ${candidate.onset_date}`));
    } else {
      if (candidate.result_text) card.append(make("p", `Result: ${candidate.result_text}`));
      if (candidate.unit_text) card.append(make("p", `Unit: ${candidate.unit_text}`));
      if (candidate.reference_range_text) card.append(make("p", `Reference range: ${candidate.reference_range_text}`));
      if (candidate.observed_date) card.append(make("p", `Observed: ${candidate.observed_date}`));
      if (candidate.source_flag_text) card.append(make("p", `Flag: ${candidate.source_flag_text} (as reported)`, "meta"));
    }
    if (candidate.note) card.append(make("p", candidate.note));
    if (candidate.predecessor_candidate_id) card.append(make("p", `Corrects: ${candidate.predecessor_candidate_id}`, "meta"));
    card.append(make("p", provenanceLabel(candidate), "meta"));
    if (actions) {
      const confirmButton = make("button", "Confirm"), correctButton = make("button", "Correct"), rejectButton = make("button", "Reject"), unsupportedButton = make("button", "Unsupported");
      confirmButton.type = correctButton.type = rejectButton.type = unsupportedButton.type = "button";
      confirmButton.addEventListener("click", () => transition(candidate, "confirm", confirmButton));
      correctButton.addEventListener("click", () => openCorrection(candidate, correctButton));
      rejectButton.addEventListener("click", () => transition(candidate, "reject", rejectButton));
      unsupportedButton.addEventListener("click", () => transition(candidate, "unsupported", unsupportedButton));
      card.append(confirmButton, correctButton, rejectButton, unsupportedButton);
    }
    return card;
  }

  function factRecordCard(record, factType, historical) {
    const card = make("article", "", "record");
    const name = factType === "lab" ? record.test_name : record.display_name;
    card.append(make("strong", name));
    card.append(make("p", `Confirmed: ${record.confirmed_at} · Source: ${record.source_id}${historical ? " · Superseded" : ""}`, "meta"));
    if (factType === "condition") {
      if (record.status_text) card.append(make("p", `Status: ${record.status_text}`));
      if (record.onset_date) card.append(make("p", `Onset: ${record.onset_date}`));
    } else if (factType === "lab") {
      if (record.result_text) card.append(make("p", `Result: ${record.result_text}`));
      if (record.unit_text) card.append(make("p", `Unit: ${record.unit_text}`));
      if (record.reference_range_text) card.append(make("p", `Reference range: ${record.reference_range_text}`));
      if (record.observed_date) card.append(make("p", `Observed: ${record.observed_date}`));
      if (record.source_flag_text) card.append(make("p", `Flag: ${record.source_flag_text} (as reported)`, "meta"));
    }
    if (record.note) card.append(make("p", record.note));
    if (record.superseded_by_record_id) card.append(make("p", `Superseded by: ${record.superseded_by_record_id}`, "meta"));
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
    for (const id of ["inbox-fact-filter", "history-fact-filter"]) {
      const select = byId(id);
      const current = select.value;
      clear(select);
      const all = document.createElement("option");
      all.value = "all";
      all.textContent = "All fact types";
      select.append(all);
      facts.forEach((fact) => {
        const option = document.createElement("option");
        option.value = fact;
        option.textContent = fact;
        select.append(option);
      });
      select.value = facts.includes(current) ? current : "all";
    }
  }

  async function submitCondition(event) {
    event.preventDefault();
    if (!state.person) return;
    const submit = event.submitter;
    submit.disabled = true;
    const display_name = byId("condition-display-name").value, status_text = byId("condition-status-text").value || null, onset_date = byId("condition-onset-date").value || null, note = byId("condition-note").value || null;
    try {
      const source = await request("/sources/manual-condition", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, condition: { display_name, status_text, onset_date, note } }) });
      await request("/candidates/conditions", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, display_name, status_text, onset_date, note }) });
      event.target.reset();
      await loadWorkspace();
      status("Condition entry is waiting for review.", "success");
    } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; }
  }

  async function submitLab(event) {
    event.preventDefault();
    if (!state.person) return;
    const submit = event.submitter;
    submit.disabled = true;
    const test_name = byId("lab-test-name").value, result_text = byId("lab-result-text").value, unit_text = byId("lab-unit-text").value || null, reference_range_text = byId("lab-reference-range-text").value || null, observed_date = byId("lab-observed-date").value || null, source_flag_text = byId("lab-source-flag-text").value || null, note = byId("lab-note").value || null;
    try {
      const source = await request("/sources/manual-lab", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, lab: { test_name, result_text, unit_text, reference_range_text, observed_date, source_flag_text, note } }) });
      await request("/candidates/labs", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, test_name, result_text, unit_text, reference_range_text, observed_date, source_flag_text, note }) });
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
    const container = byId("fact-sections");
    const condition = byId("condition-section");
    if (state.conditionEnabled && !condition) container.append(buildConditionSection());
    if (!state.conditionEnabled && condition) condition.remove();
    const lab = byId("lab-section");
    if (state.labEnabled && !lab) container.append(buildLabSection());
    if (!state.labEnabled && lab) lab.remove();
    syncFactTypeFilters();
    if (state.conditionEnabled) renderFactSectionLists("condition");
    if (state.labEnabled) renderFactSectionLists("lab");
  }

  function render() {
    const inbox = byId("review-inbox"), history = byId("candidate-history"), medications = byId("canonical-medications"), timeline = byId("timeline");
    [inbox, history, medications, timeline].forEach(clear);
    renderFactSections();
    const all = visibleCandidates();
    const inboxFact = byId("inbox-fact-filter").value, inboxStatus = byId("inbox-status-filter").value;
    const inboxItems = all.filter((item) => (inboxFact === "all" || item.fact_type === inboxFact) && (inboxStatus === "all" || item.status === inboxStatus));
    if (!inboxItems.length) {
      const factLabel = inboxFact === "all" ? "" : `${inboxFact} `;
      inbox.append(make("p", inboxStatus === "pending" ? `No ${factLabel}entries are waiting for review.` : "No entries match this view.", "meta"));
    }
    inboxItems.forEach((item) => inbox.append(factCandidateCard(item, item.status === "pending")));
    const historyFact = byId("history-fact-filter").value, historyStatus = byId("history-filter").value;
    const historyItems = all.filter((item) => (historyFact === "all" || item.fact_type === historyFact) && (historyStatus === "all" || item.status === historyStatus));
    if (!historyItems.length) history.append(make("p", "No candidates match this view.", "meta"));
    historyItems.forEach((item) => history.append(factCandidateCard(item, false)));
    if (!state.medications.length) medications.append(make("p", "No medication records have been confirmed.", "meta"));
    state.medications.forEach((item) => medications.append(make("article", `${item.display_name} — Confirmed: ${item.confirmed_at} · Source: ${item.source_id}`, "record")));
    if (!state.timeline.length) timeline.append(make("p", "No Product Core timeline events are available.", "meta"));
    state.timeline.forEach((item) => timeline.append(make("article", `${item.title} — ${item.event_at} · ${item.event_type} · ${item.fact_type}`, "record")));
    renderVisitPlanning(); renderPersistedBrief();
  }

  function renderVisitPlanning() {
    const visits = byId("visits"), questions = byId("visit-questions");
    clear(visits); clear(questions);
    if (!state.visits.length) visits.append(make("p", "No visits have been created for this profile.", "meta"));
    state.visits.forEach((visit) => {
      const card = make("article", "", "record"), select = make("button", state.visit?.visit_id === visit.visit_id ? "Selected visit" : "Select visit");
      select.type = "button"; select.disabled = state.visit?.visit_id === visit.visit_id;
      select.addEventListener("click", () => selectVisit(visit, select));
      card.append(make("strong", visit.title), make("p", `${visit.specialist || "No specialist"} · ${visit.scheduled_date || "No scheduled date"}`, "meta"), select);
      visits.append(card);
    });
    const hasVisit = Boolean(state.visit);
    byId("edit-visit-form").hidden = !hasVisit;
    byId("visit-question-form").hidden = !hasVisit;
    byId("edit-visit-question-form").hidden = state.editingQuestion === null;
    if (!hasVisit) { byId("edit-visit-question-form").hidden = true; return; }
    byId("edit-visit-title").value = state.visit.title;
    byId("edit-visit-specialist").value = state.visit.specialist || "";
    byId("edit-visit-date").value = state.visit.scheduled_date || "";
    byId("selected-visit-label").textContent = `Questions for: ${state.visit.title}`;
    if (!state.questions.length) questions.append(make("p", "No questions have been added for this visit.", "meta"));
    state.questions.forEach((question) => {
      const card = make("article", "", "record"), actions = document.createElement("div");
      const edit = make("button", "Edit"), up = make("button", "Move question up"), down = make("button", "Move question down"), remove = make("button", "Remove");
      [edit, up, down, remove].forEach((button) => { button.type = "button"; });
      up.disabled = question.position === 0; down.disabled = question.position === state.questions.length - 1;
      edit.addEventListener("click", () => openQuestionEdit(question, edit));
      up.addEventListener("click", () => moveQuestion(question, question.position - 1, up));
      down.addEventListener("click", () => moveQuestion(question, question.position + 1, down));
      remove.addEventListener("click", () => removeQuestion(question, remove));
      actions.append(edit, up, down, remove);
      card.append(make("strong", `Question ${question.position + 1}`), make("p", question.question_text), actions);
      questions.append(card);
    });
  }

  async function refreshVisits() {
    if (!state.person) return;
    const response = await request(`/people/${encodeURIComponent(state.person.person_id)}/visits`);
    state.visits = response.visits;
  }

  async function selectVisit(visit, trigger) {
    try {
      const response = await request(`/visits/${encodeURIComponent(visit.visit_id)}/questions`);
      state.visit = visit; state.questions = response.questions; state.editingQuestion = null; state.persistedBrief = null; state.briefRevision = null; state.briefEvidence = []; state.briefDirty = false; renderVisitPlanning(); await loadPersistedBrief();
      byId("new-visit-question").focus();
    } catch (error) { status(error.message, "error"); trigger.focus(); }
  }

  function selectedEvidenceIds() {
    return [...document.querySelectorAll('input[name="brief-record"]:checked')].map((item) => item.value);
  }

  function renderPersistedBrief() {
    const hasVisit = Boolean(state.visit), hasBrief = Boolean(state.persistedBrief);
    byId("initialize-brief").hidden = !hasVisit || hasBrief;
    byId("initialize-brief").disabled = !hasVisit;
    byId("brief-workflow").hidden = !hasBrief;
    byId("brief-status").textContent = !hasVisit ? "Select a Visit to prepare its Brief." : !hasBrief ? "Initialize a persistent Brief for this Visit." : state.briefRevision ? `Viewing revision ${state.briefRevision.revision_number}.` : "Choose evidence and generate the first revision.";
    const options = byId("brief-medication-options"); clear(options);
    const briefRecords = [...(state.briefRevision?.content?.medications || []), ...(state.briefRevision?.content?.records || [])];
    state.briefEvidence.forEach((item) => { const label = document.createElement("label"), input = document.createElement("input"); input.type = "checkbox"; input.name = "brief-record"; input.value = item.canonical_record_id; input.checked = briefRecords.some((record) => record.canonical_record_id === item.canonical_record_id); label.append(input, document.createTextNode(` ${item.display_name || item.test_name || "Evidence record"}`)); options.append(label); });
    byId("brief-evidence-selection").disabled = !hasBrief;
    byId("validate-brief-evidence").disabled = !hasBrief;
    byId("generate-brief").disabled = !hasBrief;
    byId("brief-preparation-notes").disabled = !state.briefRevision;
    byId("save-brief-notes").disabled = !state.briefRevision || !state.briefDirty;
    byId("brief-unsaved-warning").hidden = !state.briefDirty;
    if (state.briefRevision) {
      byId("brief-preparation-notes").value = state.briefRevision.content.preparation_notes || "";
      byId("brief-metadata").textContent = `Revision ${state.briefRevision.revision_number} · ${state.briefRevision.origin} · ${state.briefRevision.staleness.state}`;
      byId("brief-markdown").textContent = state.briefRevision.markdown;
      byId("brief-result").hidden = false;
    } else { byId("brief-result").hidden = true; }
    renderBriefRevisions();
  }

  function renderBriefRevisions() {
    const target = byId("brief-revisions"); clear(target);
    const revisions = state.persistedBrief?.revisions || [];
    if (!state.persistedBrief || !revisions.length) { target.append(make("p", state.persistedBrief ? "No revisions have been created." : "", "meta")); return; }
    revisions.forEach((revision) => { const card = make("article", "", "record"), view = make("button", `View revision ${revision.revision_number}`), restore = make("button", `Restore revision ${revision.revision_number}`); view.type = restore.type = "button"; view.addEventListener("click", () => loadBriefRevision(revision.revision_number, view)); restore.disabled = revision.revision_number === state.persistedBrief.current_revision_number; restore.addEventListener("click", () => restoreBriefRevision(revision.revision_number, restore)); card.append(make("strong", `Revision ${revision.revision_number} · ${revision.origin}`), make("p", `State: ${revision.staleness.state}`, "meta"), view, restore); target.append(card); });
  }

  async function loadPersistedBrief() {
    if (!state.visit) return;
    try { state.persistedBrief = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief`); await Promise.all([loadBriefEvidence(), loadBriefHistory()]); state.briefRevision = state.persistedBrief.current_revision; renderPersistedBrief(); }
    catch (error) { if (error.message === "That profile or record is not available.") { state.persistedBrief = null; renderPersistedBrief(); return; } status(error.message, "error"); }
  }

  async function loadBriefEvidence() { if (!state.visit) return; const response = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/evidence`); state.briefEvidence = response.evidence; }
  async function loadBriefHistory() { if (!state.visit || !state.persistedBrief) return; const response = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions`); state.persistedBrief.revisions = response.revisions; }
  async function loadBriefRevision(number, trigger) { if (!state.visit) return; try { state.briefRevision = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions/${number}`); state.briefDirty = false; renderPersistedBrief(); byId("brief-preparation-notes").focus(); } catch (error) { status(error.message, "error"); trigger.focus(); } }

  async function moveQuestion(question, position, trigger) {
    trigger.disabled = true;
    try { await request(`/visit-questions/${encodeURIComponent(question.question_id)}`, { method: "PATCH", body: JSON.stringify({ position }) }); await selectVisit(state.visit, trigger); status("Question order updated.", "success"); } catch (error) { status(error.message, "error"); trigger.disabled = false; }
  }

  function openQuestionEdit(question, trigger) {
    state.editingQuestion = { question, trigger }; byId("edit-visit-question").value = question.question_text; byId("edit-visit-question-form").hidden = false; byId("edit-visit-question").focus();
  }

  async function removeQuestion(question, trigger) {
    trigger.disabled = true;
    try { await request(`/visit-questions/${encodeURIComponent(question.question_id)}`, { method: "DELETE" }); await selectVisit(state.visit, trigger); status("Question removed.", "success"); } catch (error) { status(error.message, "error"); trigger.disabled = false; }
  }

  async function transition(candidate, action, button) {
    if (action === "reject" && !window.confirm("Reject this candidate?")) return;
    button.disabled = true;
    try { await request(`/candidates/${encodeURIComponent(candidate.id)}/${action}`, { method: "POST", body: "{}" }); await loadWorkspace(); status(action === "unsupported" ? "Candidate marked unsupported." : `Candidate ${action}ed.`, "success"); } catch (error) { status(error.message, "error"); } finally { button.disabled = false; }
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
    form.addEventListener("submit", async (event) => { event.preventDefault(); save.disabled = true; error.textContent = ""; const payload = {}; specs.forEach((spec, index) => { payload[spec.key] = controls[index].value || null; }); try { await request(`/candidates/${encodeURIComponent(candidate.id)}/${CORRECTION_ENDPOINTS[candidate.fact_type]}`, { method: "POST", body: JSON.stringify(payload) }); await loadWorkspace(); close(); status("Correction is waiting for review.", "success"); } catch (failure) { error.textContent = failure.message; } finally { save.disabled = false; } });
    trigger.closest("article").append(form); name.focus();
  }

  async function clearWorkspace() {
    try { await setActivePerson(null); } catch (error) { status(error.message, "error"); return; }
    Object.assign(state, { person: null, candidates: [], medications: [], conditions: [], labs: [], conditionCandidates: [], labCandidates: [], conditionEnabled: false, labEnabled: false, timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, persistedBrief: null, briefRevision: null, briefEvidence: [], briefDirty: false, vaultExportTrigger: null });
    byId("person-selector").value = ""; byId("edit-profile-form").hidden = true; byId("edit-visit-form").hidden = true; byId("visit-question-form").hidden = true; byId("edit-visit-question-form").hidden = true; renderPersonContext(); render(); enableWorkspace(false); byId("load-workspace").disabled = true; status("Profile selection cleared.");
  }

  byId("person-selector").addEventListener("change", () => { byId("load-workspace").disabled = !byId("person-selector").value; });
  byId("load-workspace").addEventListener("click", loadWorkspace);
  byId("clear-workspace").addEventListener("click", () => { void clearWorkspace(); });
  byId("open-vault-export").addEventListener("click", (event) => { if (!state.person) return; state.vaultExportTrigger = event.currentTarget; byId("vault-export-warning").hidden = false; byId("confirm-vault-export").focus(); });
  byId("cancel-vault-export").addEventListener("click", () => { byId("vault-export-warning").hidden = true; state.vaultExportTrigger?.focus(); });
  byId("confirm-vault-export").addEventListener("click", async (event) => { if (!state.person) return; const button = event.currentTarget; button.disabled = true; try { const payload = await requestBlob(`/people/${encodeURIComponent(state.person.person_id)}/vault-export`, { method: "POST", body: "{}" }); const link = document.createElement("a"); link.href = URL.createObjectURL(payload); link.download = "opencare-person-vault-v2.zip"; link.click(); URL.revokeObjectURL(link.href); byId("vault-export-warning").hidden = true; state.vaultExportTrigger?.focus(); status("Vault download prepared.", "success"); } catch (error) { status(error.message, "error"); } finally { button.disabled = false; } });
  byId("inbox-fact-filter").addEventListener("change", render);
  byId("inbox-status-filter").addEventListener("change", render);
  byId("history-fact-filter").addEventListener("change", render);
  byId("history-filter").addEventListener("change", render);
  byId("create-profile-form").addEventListener("submit", async (event) => { event.preventDefault(); const submit = event.submitter; submit.disabled = true; try { const person = await request("/people", { method: "POST", body: JSON.stringify({ display_name: byId("create-display-name").value, date_of_birth: byId("create-date-of-birth").value || null, confirm_owner_assignment: byId("create-owner-confirmation").checked }) }); state.person = person; await refreshPeople(person); byId("create-profile-form").reset(); await loadWorkspace(); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("edit-profile").addEventListener("click", () => { if (!state.person) return; byId("edit-display-name").value = state.person.display_name; byId("edit-date-of-birth").value = state.person.date_of_birth || ""; byId("edit-profile-form").hidden = false; byId("edit-display-name").focus(); });
  byId("cancel-edit-profile").addEventListener("click", () => { byId("edit-profile-form").hidden = true; });
  byId("edit-profile-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person) return; const submit = event.submitter; submit.disabled = true; try { const person = await request(`/people/${encodeURIComponent(state.person.person_id)}`, { method: "PATCH", body: JSON.stringify({ display_name: byId("edit-display-name").value, date_of_birth: byId("edit-date-of-birth").value || null }) }); state.person = person; await refreshPeople(person); renderPersonContext(); byId("edit-profile-form").hidden = true; status("Profile updated.", "success"); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("medication-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person) return; const submit = event.submitter; submit.disabled = true; const display_name = byId("medication-name").value, schedule_text = byId("medication-schedule").value || null, note = byId("medication-note").value || null; try { const source = await request("/sources/manual-medication", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, medication: { display_name, schedule_text, note } }) }); await request("/candidates/medications", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, source_id: source.source.source_id, display_name, schedule_text, note }) }); event.target.reset(); await loadWorkspace(); status("Medication entry is waiting for review.", "success"); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("visit-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person) return; const submit = event.submitter; submit.disabled = true; try { const visit = await request("/visits", { method: "POST", body: JSON.stringify({ person_id: state.person.person_id, title: byId("new-visit-title").value, specialist: byId("new-visit-specialist").value || null, scheduled_date: byId("new-visit-date").value || null }) }); event.target.reset(); await refreshVisits(); await selectVisit(visit, submit); status("Visit created.", "success"); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("edit-visit-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.visit) return; const submit = event.submitter; submit.disabled = true; try { const visit = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}`, { method: "PATCH", body: JSON.stringify({ title: byId("edit-visit-title").value, specialist: byId("edit-visit-specialist").value || null, scheduled_date: byId("edit-visit-date").value || null }) }); state.visit = visit; await refreshVisits(); renderVisitPlanning(); status("Visit updated.", "success"); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("cancel-edit-visit").addEventListener("click", () => { if (!state.visit) return; byId("edit-visit-title").value = state.visit.title; byId("edit-visit-specialist").value = state.visit.specialist || ""; byId("edit-visit-date").value = state.visit.scheduled_date || ""; byId("edit-visit-title").focus(); });
  byId("visit-question-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.visit) return; const submit = event.submitter; submit.disabled = true; try { await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/questions`, { method: "POST", body: JSON.stringify({ question_text: byId("new-visit-question").value }) }); event.target.reset(); await selectVisit(state.visit, submit); status("Question added.", "success"); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("edit-visit-question-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.editingQuestion) return; const submit = event.submitter, editing = state.editingQuestion; submit.disabled = true; try { await request(`/visit-questions/${encodeURIComponent(editing.question.question_id)}`, { method: "PATCH", body: JSON.stringify({ question_text: byId("edit-visit-question").value }) }); state.editingQuestion = null; byId("edit-visit-question-form").hidden = true; await selectVisit(state.visit, submit); status("Question updated.", "success"); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("cancel-edit-visit-question").addEventListener("click", () => { const trigger = state.editingQuestion?.trigger; state.editingQuestion = null; byId("edit-visit-question-form").hidden = true; if (trigger) trigger.focus(); });
  byId("initialize-brief").addEventListener("click", async (event) => { if (!state.visit) return; const button = event.currentTarget; button.disabled = true; try { state.persistedBrief = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief`, { method: "POST", body: "{}" }); state.persistedBrief.revisions = []; state.briefRevision = null; await loadBriefEvidence(); renderPersistedBrief(); status("Visit Brief initialized.", "success"); } catch (error) { status(error.message, "error"); } finally { button.disabled = false; } });
  byId("validate-brief-evidence").addEventListener("click", async (event) => { if (!state.visit) return; const button = event.currentTarget; button.disabled = true; try { await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/evidence:validate`, { method: "POST", body: JSON.stringify({ selected_record_ids: selectedEvidenceIds() }) }); status("Selected evidence is valid.", "success"); } catch (error) { status(error.message, "error"); } finally { button.disabled = false; } });
  byId("generate-brief").addEventListener("click", async (event) => { if (!state.visit || !state.persistedBrief) return; const button = event.currentTarget; button.disabled = true; try { state.briefRevision = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions:generate`, { method: "POST", body: JSON.stringify({ selected_record_ids: selectedEvidenceIds(), expected_current_revision_number: state.persistedBrief.current_revision_number }) }); state.persistedBrief.current_revision_number = state.briefRevision.revision_number; state.briefDirty = false; await loadBriefHistory(); renderPersistedBrief(); status("Visit Brief revision generated.", "success"); } catch (error) { status(error.message, "error"); } finally { button.disabled = false; } });
  byId("brief-preparation-notes").addEventListener("input", () => { state.briefDirty = true; byId("save-brief-notes").disabled = false; byId("brief-unsaved-warning").hidden = false; });
  byId("save-brief-notes").addEventListener("click", async (event) => { if (!state.visit || !state.persistedBrief?.current_revision_number) return; const button = event.currentTarget; button.disabled = true; try { state.briefRevision = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions:user-edit`, { method: "POST", body: JSON.stringify({ preparation_notes: byId("brief-preparation-notes").value, expected_current_revision_number: state.persistedBrief.current_revision_number }) }); state.persistedBrief.current_revision_number = state.briefRevision.revision_number; state.briefDirty = false; await loadBriefHistory(); renderPersistedBrief(); status("Preparation notes saved as a new revision.", "success"); } catch (error) { status(error.message, "error"); } finally { button.disabled = false; } });
  async function restoreBriefRevision(number, trigger) { if (!state.visit || !state.persistedBrief?.current_revision_number) return; trigger.disabled = true; try { state.persistedBrief = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/current`, { method: "POST", body: JSON.stringify({ revision_number: number, expected_current_revision_number: state.persistedBrief.current_revision_number }) }); await loadBriefHistory(); state.briefRevision = await request(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/revisions/${number}`); state.briefDirty = false; renderPersistedBrief(); status("Current Brief revision restored.", "success"); } catch (error) { status(error.message, "error"); trigger.disabled = false; } }
  byId("copy-brief").addEventListener("click", async () => { if (!state.briefRevision) return; try { await navigator.clipboard.writeText(state.briefRevision.markdown); status("Markdown copied.", "success"); } catch (_) { status("Copy is unavailable in this browser.", "error"); } });
  byId("download-brief").addEventListener("click", async () => { if (!state.visit) return; try { const markdown = await requestText(`/visits/${encodeURIComponent(state.visit.visit_id)}/brief/current:export`, { method: "POST", body: "{}" }); const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `opencare-visit-brief-r${state.persistedBrief.current_revision_number}.md`; link.click(); URL.revokeObjectURL(link.href); status("Markdown download prepared.", "success"); } catch (error) { status(error.message, "error"); } });

  enableWorkspace(false); renderPeople([]); refreshPeople().catch((error) => { status(error.message, "error"); });
})();
