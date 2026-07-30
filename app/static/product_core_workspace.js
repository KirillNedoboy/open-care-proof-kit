(() => {
  "use strict";

  const api = "/api/product-core/v1";
  const state = { person: null, candidates: [], medications: [], timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, brief: null, loadVersion: 0 };
  const byId = (id) => document.getElementById(id);
  const make = (tag, value = "", className = "") => { const node = document.createElement(tag); node.textContent = value; node.className = className; return node; };
  const clear = (node) => node.replaceChildren();
  const status = (message, kind = "") => { const target = byId("workspace-status"); target.textContent = message; target.className = kind; };
  const safeError = (response, body) => response.status === 422 ? "Check the entered values and try again." : response.status === 404 ? "That profile or record is not available." : response.status === 409 ? "This record changed. Refresh and try again." : body?.error?.code === "product_core_storage_unavailable" ? "Local storage is temporarily unavailable." : "The request could not be completed. Try again.";

  async function request(path, options = {}) {
    const response = await fetch(api + path, { credentials: "same-origin", headers: { "Content-Type": "application/json" }, ...options });
    let body;
    try { body = await response.json(); } catch (_) {}
    if (!response.ok) throw Error(safeError(response, body));
    return body;
  }

  function enableWorkspace(enabled) {
    byId("workspace-content").setAttribute("aria-disabled", String(!enabled));
    byId("workspace-content").querySelectorAll("input, textarea, select, button").forEach((item) => { item.disabled = !enabled; });
    byId("include-all").checked = true;
    byId("medication-selection").disabled = true;
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
      const [person, candidates, medications, timeline, visits] = await Promise.all([
        request(`/people/${encodeURIComponent(personId)}`),
        request(`/people/${encodeURIComponent(personId)}/candidates`),
        request(`/people/${encodeURIComponent(personId)}/medications`),
        request(`/people/${encodeURIComponent(personId)}/timeline`),
        request(`/people/${encodeURIComponent(personId)}/visits`),
      ]);
      if (version !== state.loadVersion) return;
      Object.assign(state, { person, candidates: candidates.candidates, medications: medications.medications, timeline: timeline.events, visits: visits.visits, visit: null, questions: [], editingQuestion: null, brief: null });
      renderPersonContext(); render(); enableWorkspace(true); status("Workspace loaded.", "success");
    } catch (error) { status(error.message, "error"); }
  }

  function candidateCard(candidate, actions) {
    const card = make("article", "", "record");
    card.append(make("strong", candidate.display_name), make("p", `Status: ${candidate.status} · Source: ${candidate.source_id} · Created: ${candidate.created_at}`, "meta"));
    if (candidate.schedule_text) card.append(make("p", candidate.schedule_text));
    if (candidate.note) card.append(make("p", candidate.note));
    if (candidate.predecessor_candidate_id) card.append(make("p", `Corrects: ${candidate.predecessor_candidate_id}`, "meta"));
    if (actions) {
      const confirmButton = make("button", "Confirm"), correctButton = make("button", "Correct"), rejectButton = make("button", "Reject");
      confirmButton.type = correctButton.type = rejectButton.type = "button";
      confirmButton.addEventListener("click", () => transition(candidate, "confirm", confirmButton));
      correctButton.addEventListener("click", () => openCorrection(candidate, correctButton));
      rejectButton.addEventListener("click", () => transition(candidate, "reject", rejectButton));
      card.append(confirmButton, correctButton, rejectButton);
    }
    return card;
  }

  function render() {
    const inbox = byId("review-inbox"), history = byId("candidate-history"), medications = byId("canonical-medications"), timeline = byId("timeline");
    [inbox, history, medications, timeline].forEach(clear);
    const pending = state.candidates.filter((item) => item.status === "pending");
    if (!pending.length) inbox.append(make("p", "No medication entries are waiting for review.", "meta"));
    pending.forEach((item) => inbox.append(candidateCard(item, true)));
    const filter = byId("history-filter").value;
    (filter === "all" ? state.candidates : state.candidates.filter((item) => item.status === filter)).forEach((item) => history.append(candidateCard(item, false)));
    if (!history.childElementCount) history.append(make("p", "No candidates match this view.", "meta"));
    if (!state.medications.length) medications.append(make("p", "No medication records have been confirmed.", "meta"));
    state.medications.forEach((item) => medications.append(make("article", `${item.display_name} — Confirmed: ${item.confirmed_at} · Source: ${item.source_id}`, "record")));
    if (!state.timeline.length) timeline.append(make("p", "No Product Core timeline events are available.", "meta"));
    state.timeline.forEach((item) => timeline.append(make("article", `${item.title} — ${item.event_at} · ${item.event_type}`, "record")));
    const options = byId("brief-medication-options"); clear(options);
    state.medications.filter((item) => item.is_active).forEach((item) => { const label = document.createElement("label"), input = document.createElement("input"); input.type = "checkbox"; input.name = "record"; input.value = item.id; label.append(input, document.createTextNode(` ${item.display_name}`)); options.append(label); });
    renderVisitPlanning();
  }

  function renderVisitPlanning() {
    const visits = byId("visits"), questions = byId("visit-questions");
    clear(visits); clear(questions);
    if (!state.visits.length) visits.append(make("p", "No visits have been created for this profile.", "meta"));
    state.visits.forEach((visit) => {
      const card = make("article", "", "record"), select = make("button", state.visit?.visit_id === visit.visit_id ? "Selected visit" : "Select visit");
      select.type = "button"; select.disabled = state.visit?.visit_id === visit.visit_id;
      select.addEventListener("click", () => selectVisit(visit, select));
      card.append(make("strong", visit.title), make("p", `${visit.specialist || "No specialist"} В· ${visit.scheduled_date || "No scheduled date"}`, "meta"), select);
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
      state.visit = visit; state.questions = response.questions; state.editingQuestion = null; renderVisitPlanning();
      byId("new-visit-question").focus();
    } catch (error) { status(error.message, "error"); trigger.focus(); }
  }

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
    try { await request(`/candidates/${encodeURIComponent(candidate.id)}/${action}`, { method: "POST", body: "{}" }); await loadWorkspace(); status(`Candidate ${action}ed.`, "success"); } catch (error) { status(error.message, "error"); } finally { button.disabled = false; }
  }

  function openCorrection(candidate, trigger) {
    const form = document.createElement("form"); form.className = "record correction-form";
    const name = document.createElement("input"), schedule = document.createElement("input"), note = document.createElement("textarea"), error = make("p", "", "error"), save = make("button", "Save correction"), cancel = make("button", "Cancel");
    name.value = candidate.display_name; schedule.value = candidate.schedule_text || ""; note.value = candidate.note || ""; name.maxLength = 200; schedule.maxLength = 500; note.maxLength = 2000; error.setAttribute("role", "alert"); save.type = "submit"; cancel.type = "button";
    const labelled = (label, control) => { const element = document.createElement("label"); element.textContent = label; element.append(control); return element; };
    form.append(make("h3", "Correct medication entry"), labelled("Medication display name", name), labelled("Schedule text", schedule), labelled("Note", note), error, save, cancel);
    const close = () => { form.remove(); trigger.focus(); };
    cancel.addEventListener("click", close);
    form.addEventListener("submit", async (event) => { event.preventDefault(); save.disabled = true; error.textContent = ""; try { await request(`/candidates/${encodeURIComponent(candidate.id)}/correct`, { method: "POST", body: JSON.stringify({ display_name: name.value, schedule_text: schedule.value || null, note: note.value || null }) }); await loadWorkspace(); close(); status("Correction is waiting for review.", "success"); } catch (failure) { error.textContent = failure.message; } finally { save.disabled = false; } });
    trigger.closest("article").append(form); name.focus();
  }

  function clearWorkspace() {
    Object.assign(state, { person: null, candidates: [], medications: [], timeline: [], visits: [], visit: null, questions: [], editingQuestion: null, brief: null });
    byId("person-selector").value = ""; byId("edit-profile-form").hidden = true; byId("edit-visit-form").hidden = true; byId("visit-question-form").hidden = true; byId("edit-visit-question-form").hidden = true; renderPersonContext(); render(); enableWorkspace(false); byId("load-workspace").disabled = true; status("Profile selection cleared.");
  }

  byId("person-selector").addEventListener("change", () => { byId("load-workspace").disabled = !byId("person-selector").value; });
  byId("load-workspace").addEventListener("click", loadWorkspace);
  byId("clear-workspace").addEventListener("click", clearWorkspace);
  byId("history-filter").addEventListener("change", render);
  byId("include-all").addEventListener("change", () => { byId("medication-selection").disabled = byId("include-all").checked; });
  byId("create-profile-form").addEventListener("submit", async (event) => { event.preventDefault(); const submit = event.submitter; submit.disabled = true; try { const person = await request("/people", { method: "POST", body: JSON.stringify({ display_name: byId("create-display-name").value, date_of_birth: byId("create-date-of-birth").value || null }) }); state.person = person; await refreshPeople(person); byId("create-profile-form").reset(); await loadWorkspace(); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
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
  byId("visit-brief-form").addEventListener("submit", async (event) => { event.preventDefault(); if (!state.person) return; const submit = event.submitter; submit.disabled = true; const selected = byId("include-all").checked ? null : [...document.querySelectorAll('input[name="record"]:checked')].map((item) => item.value); try { const brief = await request(`/people/${encodeURIComponent(state.person.person_id)}/visit-briefs:generate`, { method: "POST", body: JSON.stringify({ visit_title: byId("visit-title").value, generated_at: new Date().toISOString(), scheduled_date: byId("scheduled-date").value || null, selected_record_ids: selected }) }); state.brief = brief; byId("brief-metadata").textContent = `Generated: ${brief.generated_at}`; byId("brief-markdown").textContent = brief.markdown; byId("brief-result").hidden = false; status("Visit Brief generated.", "success"); } catch (error) { status(error.message, "error"); } finally { submit.disabled = false; } });
  byId("copy-brief").addEventListener("click", async () => { if (!state.brief) return; try { await navigator.clipboard.writeText(state.brief.markdown); status("Markdown copied.", "success"); } catch (_) { status("Copy is unavailable in this browser.", "error"); } });
  byId("download-brief").addEventListener("click", () => { if (!state.brief) return; const blob = new Blob([state.brief.markdown], { type: "text/markdown;charset=utf-8" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = "opencare-visit-brief.md"; link.click(); URL.revokeObjectURL(link.href); });

  enableWorkspace(false); renderPeople([]); refreshPeople().catch((error) => { status(error.message, "error"); });
})();
