(() => {
  "use strict";
  const form = document.querySelector("#chat-form");
  const textarea = document.querySelector("#chat-question");
  const stream = document.querySelector("#message-stream");
  const emptyState = document.querySelector("#empty-state");
  const sendButton = document.querySelector("#send-button");
  const newChat = document.querySelector("#new-chat");
  const status = document.querySelector("#chat-status");
  const endpoint = document.body.dataset.chatEndpoint;
  const live = endpoint === "/api/chat";
  let translations = {};
  try { translations = JSON.parse(document.querySelector("#product-shell-translations")?.textContent || "{}"); } catch (_) { translations = {}; }
  const t = (key, fallback) => typeof translations[key] === "string" ? translations[key] : (fallback || key);
  const csrfToken = () => document.cookie.split("; ").find((item) => item.startsWith("opencare_csrf="))?.split("=").slice(1).join("=") || "";
  let consentPending = false;
  let disclosureCounter = 0;
  const addText = (parent, tag, value) => { const element = document.createElement(tag); element.textContent = value == null ? "" : String(value); parent.append(element); return element; };
  const revealLatest = () => { const last = stream.lastElementChild; if (last && typeof last.scrollIntoView === "function") last.scrollIntoView({ block: "nearest" }); };
  /* Rows before cards: a definition row (dt term + dd value) on the
     shared .ui-row grammar. Returns the dd so callers can refine it. */
  const addDefRow = (list, term) => { const row = document.createElement("div"); row.className = "ui-row"; addText(row, "dt", term).className = "ui-row__title"; const value = document.createElement("dd"); value.className = "ui-row__meta"; row.append(value); list.append(row); return value; };
  const addFieldRows = (list, fields) => { const value = addDefRow(list, t("chat.fields", "Fields")); const names = Array.isArray(fields) && fields.length ? fields : null; if (!names) { value.textContent = t("chat.none", "none"); return; } const items = document.createElement("ul"); names.forEach((name) => addText(items, "li", name)); value.append(items); };
  const addList = (card, title, values) => { if (!Array.isArray(values) || !values.length) return; const section = document.createElement("section"); section.className = "answer-section"; addText(section, "h3", title); const list = document.createElement("ul"); values.forEach((value) => addText(list, "li", value)); section.append(list); card.append(section); };
  const addAnswer = (answer) => { const content = answer && typeof answer.answer === "object" ? { ...answer, ...answer.answer } : answer; const refused = Boolean(content && content.status === "refused"); const declined = Boolean(content && content.status === "declined"); const failed = Boolean(content && content.status === "error"); const message = document.createElement("article"); message.className = "message"; const card = document.createElement("div"); card.className = refused ? "chat-refusal ui-notice ui-notice--warning" : declined ? "chat-declined ui-notice ui-notice--info" : failed ? "chat-error ui-notice ui-notice--danger" : "chat-answer"; if (refused) addText(card, "h3", t("chat.refusal_heading", "OpenCare refused this request before contacting a provider")); if (declined) addText(card, "h3", t("chat.declined_heading", "Disclosure was not approved")); if (failed) addText(card, "h3", t("chat.error_heading", "This request did not complete")); addText(card, "p", content.answer || t("chat.answer_fallback", "No answer was returned.")); if (Array.isArray(content.citations) && content.citations.length) { const section = document.createElement("section"); section.className = "answer-section chat-evidence"; addText(section, "h3", t("chat.sources", "Sources")); content.citations.forEach((citation) => { const row = document.createElement("div"); row.className = "ui-row"; addText(row, "span", citation.source_id).className = "ui-row__title"; addText(row, "span", citation.claim).className = "ui-row__meta"; section.append(row); }); card.append(section); } addList(card, t("chat.unknown_information", "Unknown information"), content.unknowns); addList(card, t("chat.questions_clinician", "Questions for a clinician"), content.doctor_questions); addList(card, t("chat.boundaries", "Boundaries"), content.boundary_notices); if (refused) addText(card, "p", t("chat.refusal_next_step", "Safe next step: review the recorded sources in Workspace or ask a source-backed question instead.")).className = "chat-state__next"; message.append(card); stream.append(message); revealLatest(); };
  const localizeRetention = (value) => { const normalized = typeof value === "string" ? value.replace(/[.]$/, "") : value; return normalized === "provider policy; OpenCare does not retain provider payloads" ? t("chat.retention_provider_policy", value) : value; };
  const headers = () => ({ "content-type": "application/json", ...(live ? { "X-OpenCare-CSRF": csrfToken() } : {}) });
  const request = async (path, body) => { const response = await fetch(path, { method: "POST", credentials: "same-origin", headers: headers(), body: JSON.stringify(body) }); let payload = {}; try { payload = await response.json(); } catch (_) { throw new Error(t("chat.error", "OpenCare could not process this request.")); } if (!response.ok) throw new Error(t("chat.error", payload.detail || t("chat.error", "OpenCare could not process this request."))); return payload; };
  /* Permanent record of what was approved, rendered adjacent to the answer. */
  const addPreview = (preview) => { const section = document.createElement("section"); section.className = "answer-section disclosure-preview"; addText(section, "h3", t("chat.disclosure_preview", "Disclosure preview")); const grid = document.createElement("dl"); grid.className = "chat-detail-grid"; addDefRow(grid, t("chat.provider", "Provider")).textContent = preview.provider_id || t("chat.provider", "Provider"); addDefRow(grid, t("chat.model", "Model")).textContent = preview.model_id || t("chat.not_specified", "not specified"); addDefRow(grid, t("chat.boundaries", "Boundaries")).textContent = preview.external ? t("chat.external_provider", "Selected authorized data may leave this OpenCare installation") : t("chat.local_provider", "Runs on this OpenCare installation"); const evidence = addDefRow(grid, t("chat.evidence_items", "Evidence items")); evidence.textContent = String(preview.evidence_count || 0); evidence.className = "ui-row__meta chat-count"; addDefRow(grid, t("chat.retention", "Retention")).textContent = localizeRetention(preview.retention) || t("chat.not_specified", "not specified"); addFieldRows(grid, preview.fields); section.append(grid); return section; };
  /* Inline disclosure confirmation stage. Resolves true on explicit
     approval, false on decline. Performs no network calls itself. */
  const showDisclosureConsent = (preview) => new Promise((resolve) => {
    consentPending = true;
    disclosureCounter += 1;
    const headingId = `chat-consent-title-${disclosureCounter}`;
    const message = document.createElement("article");
    message.className = "message";
    const stage = document.createElement("section");
    stage.className = "chat-consent";
    stage.setAttribute("role", "region");
    stage.setAttribute("aria-labelledby", headingId);
    const heading = addText(stage, "h3", t("chat.allow_disclosure", "Allow this exact disclosure?"));
    heading.id = headingId;
    heading.tabIndex = -1;
    addText(stage, "p", t("chat.consent_help", "Nothing is sent before you approve this exact disclosure.")).className = "chat-consent__help";
    const grid = document.createElement("dl");
    grid.className = "chat-detail-grid";
    addDefRow(grid, t("chat.provider", "Provider")).textContent = preview.provider_id || t("chat.provider", "Provider");
    addDefRow(grid, t("chat.model", "Model")).textContent = preview.model_id || t("chat.not_specified", "not specified");
    addDefRow(grid, t("chat.boundaries", "Boundaries")).textContent = preview.external ? t("chat.external", "External provider") : t("chat.local_only", "Local only");
    const evidence = addDefRow(grid, t("chat.evidence_items", "Evidence items"));
    evidence.textContent = String(preview.evidence_count || 0);
    evidence.className = "ui-row__meta chat-count";
    addDefRow(grid, t("chat.retention", "Retention")).textContent = localizeRetention(preview.retention) || t("chat.not_specified", "not specified");
    addFieldRows(grid, preview.fields);
    stage.append(grid);
    const actions = document.createElement("div");
    actions.className = "chat-consent__actions";
    const approve = addText(actions, "button", t("chat.approve_disclosure", "Approve this disclosure"));
    approve.type = "button";
    approve.className = "ui-button ui-button--primary";
    const cancel = addText(actions, "button", t("button.cancel", "Cancel"));
    cancel.type = "button";
    cancel.className = "ui-button ui-button--secondary";
    let settled = false;
    const settle = (decision) => { if (settled) return; settled = true; consentPending = false; approve.disabled = true; cancel.disabled = true; message.remove(); resolve(decision); };
    approve.addEventListener("click", () => { approve.setAttribute("aria-busy", "true"); settle(true); });
    cancel.addEventListener("click", () => settle(false));
    actions.append(approve, cancel);
    stage.append(actions);
    message.append(stage);
    stream.append(message);
    revealLatest();
    heading.focus();
  });
  const addReceipt = (metadata) => { const message = document.createElement("article"); message.className = "message"; const section = document.createElement("section"); section.className = "chat-receipt"; addText(section, "h3", t("chat.receipt", "Receipt")); const grid = document.createElement("dl"); grid.className = "chat-detail-grid"; const receiptId = addDefRow(grid, t("chat.receipt_id", "Receipt id")); receiptId.textContent = metadata.receipt_id || t("chat.recorded", "recorded"); receiptId.className = "ui-row__meta chat-receipt__id"; const statusValue = addDefRow(grid, t("chat.status", "status")); const badge = document.createElement("span"); badge.className = "ui-status"; badge.textContent = metadata.status || "unknown"; statusValue.append(badge); section.append(grid); message.append(section); stream.append(message); revealLatest(); };
  const sendLive = async (question) => { const prepared = await request("/api/chat/prepare", { question }); if (prepared.status === "refused") { addAnswer(prepared); return; } const preview = prepared.preview || {}; status.textContent = t("chat.status_await_consent", "Waiting for your explicit approval…"); const approved = await showDisclosureConsent(preview); if (!approved) { status.textContent = ""; addAnswer({ status: "declined", answer: t("chat.consent_declined", "No provider call was made because disclosure was not approved."), boundary_notices: [t("chat.consent_not_granted", "Consent was not granted.")], citations: [], unknowns: [], doctor_questions: [] }); return; } textarea.focus(); status.textContent = t("chat.status_execute", "Executing the approved request…"); const previewMessage = document.createElement("article"); previewMessage.className = "message"; previewMessage.append(addPreview(preview)); stream.append(previewMessage); await request(`/api/chat/executions/${prepared.execution_id}/consent`, { fields: preview.fields || [] }); const executed = await request(`/api/chat/executions/${prepared.execution_id}/execute`, { question }); addAnswer(executed); if (executed.receipt_id) { status.textContent = t("chat.status_receipt", "Finalizing the execution receipt…"); const receipt = await fetch(`/api/chat/executions/${prepared.execution_id}/receipt`, { credentials: "same-origin", headers: { "X-OpenCare-CSRF": csrfToken() } }); if (receipt.ok) { addReceipt(await receipt.json()); } } };
  const sendDemo = async (question) => request(endpoint, { question }).then(addAnswer);
  const send = async (question) => { emptyState?.remove(); const message = document.createElement("article"); message.className = "message message-user"; const bubble = document.createElement("div"); bubble.className = "user-bubble"; addText(message, "h2", t("chat.ask_label", "Your question")).className = "sr-only"; bubble.textContent = question; message.append(bubble); stream.append(message); revealLatest(); textarea.value = ""; sendButton.disabled = true; if (newChat) newChat.disabled = true; status.textContent = live ? t("chat.status_prepare", "Preparing an exact disclosure…") : t("chat.status_check", "Checking vault context and sources…"); try { if (live) await sendLive(question); else await sendDemo(question); } catch (error) { addAnswer({ status: "error", answer: error instanceof Error ? error.message : t("chat.error", "OpenCare could not process this request."), citations: [], unknowns: [], doctor_questions: [], boundary_notices: [t("chat.no_provider_output", "No provider output was displayed.")] }); } finally { sendButton.disabled = false; if (newChat) newChat.disabled = false; consentPending = false; status.textContent = ""; textarea.focus(); revealLatest(); } };
  form?.addEventListener("submit", (event) => { event.preventDefault(); const question = textarea.value.trim(); if (question && !sendButton.disabled && !consentPending) send(question); });
  textarea?.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
  document.querySelectorAll(".prompt-button").forEach((button) => button.addEventListener("click", () => { textarea.value = button.textContent; textarea.focus(); }));
  newChat?.addEventListener("click", () => { if (newChat.disabled || consentPending) return; stream.replaceChildren(); const fresh = document.createElement("section"); fresh.className = "empty-state ui-empty-state"; fresh.id = "empty-state"; addText(fresh, "h2", t("chat.empty_title", "Ask about your recorded vault")); addText(fresh, "p", t("chat.empty_intro", "OpenCare summarizes source-backed records, identifies unknown information, and prepares clinician discussion questions.")); addText(fresh, "p", t("chat.empty_safety", "Answers are policy-checked and validated before display. Validation cannot guarantee medical correctness.")); stream.append(fresh); textarea.value = ""; status.textContent = ""; });
})();
