(() => {
  const form = document.querySelector("#chat-form");
  const textarea = document.querySelector("#chat-question");
  const stream = document.querySelector("#message-stream");
  const emptyState = document.querySelector("#empty-state");
  const sendButton = document.querySelector("#send-button");
  const status = document.querySelector("#chat-status");
  const sidebar = document.querySelector("#chat-sidebar");
  const toggle = document.querySelector("#sidebar-toggle");
  const addText = (parent, tag, value) => { const element = document.createElement(tag); element.textContent = value; parent.append(element); return element; };
  const addList = (card, title, values) => { if (!values.length) return; const section = document.createElement("section"); section.className = "answer-section"; addText(section, "h3", title); const list = document.createElement("ul"); values.forEach((value) => addText(list, "li", value)); section.append(list); card.append(section); };
  const addAnswer = (answer) => { const message = document.createElement("article"); message.className = "message"; const card = document.createElement("div"); card.className = "answer-card"; addText(card, "p", answer.answer); if (answer.citations.length) { const section = document.createElement("section"); section.className = "answer-section"; addText(section, "h3", "Sources"); answer.citations.forEach((citation) => { const item = document.createElement("div"); item.className = "citation-card"; addText(item, "strong", citation.source_id); addText(item, "span", citation.claim); section.append(item); }); card.append(section); } addList(card, "Unknown information", answer.unknowns); addList(card, "Questions for a clinician", answer.doctor_questions); addList(card, "Boundaries", answer.boundary_notices); message.append(card); stream.append(message); };
  const send = async (question) => { emptyState?.remove(); const message = document.createElement("article"); message.className = "message message-user"; const bubble = document.createElement("div"); bubble.className = "user-bubble"; bubble.textContent = question; message.append(bubble); stream.append(message); textarea.value = ""; sendButton.disabled = true; status.textContent = "Checking vault context and sources…"; try { const response = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ question }) }); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || "OpenCare could not process this request."); addAnswer(payload); } catch (error) { const messageText = error instanceof Error ? error.message : "OpenCare could not process this request."; addAnswer({ answer: messageText, citations: [], unknowns: [], doctor_questions: [], boundary_notices: ["No provider output was displayed."], status: "validation_failed" }); } finally { sendButton.disabled = false; status.textContent = ""; textarea.focus(); stream.scrollTop = stream.scrollHeight; } };
  form.addEventListener("submit", (event) => { event.preventDefault(); const question = textarea.value.trim(); if (question) send(question); });
  textarea.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
  document.querySelectorAll(".prompt-button").forEach((button) => button.addEventListener("click", () => { textarea.value = button.textContent; textarea.focus(); }));
  document.querySelector("#new-chat").addEventListener("click", () => { stream.replaceChildren(); stream.append(emptyState || document.createElement("div")); });
  toggle?.addEventListener("click", () => { const open = sidebar.classList.toggle("is-open"); toggle.setAttribute("aria-expanded", String(open)); });
})();
