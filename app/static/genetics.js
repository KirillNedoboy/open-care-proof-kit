(() => {
  "use strict";

  const GENETICS_API_ENDPOINTS = Object.freeze({
    WORKSPACE_SUMMARY: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics`,
    IMPORT: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics/import`,
    FAMILY_COMPARISON: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics/compare`,
    RESEARCH_RUN: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics/research`,
    VISIT_QUESTION_HANDOFF: "/api/product-core/v1/visit-questions"
  });

  const SYNTHETIC_VARIANTS = Object.freeze([
    { id: "rs-demo-001", gene: "CYP2C19", category: "pgx", categoryLabel: "Pharmacogenomics", coverage: "present", coverageLabel: "Present", observation: "A/G", evidence: "Clinical", evidenceClass: "clinical" },
    { id: "rs-demo-014", gene: "SYN-LIPID", category: "health", categoryLabel: "Health association", coverage: "present", coverageLabel: "Present", observation: "C/T", evidence: "Moderate", evidenceClass: "moderate" },
    { id: "rs-demo-027", gene: "SYN-NEURO", category: "trait", categoryLabel: "Trait", coverage: "present", coverageLabel: "Present", observation: "G/G", evidence: "Low", evidenceClass: "low" },
    { id: "rs-demo-035", gene: "SYN-SLEEP", category: "trait", categoryLabel: "Trait", coverage: "no-call", coverageLabel: "No-call", observation: "No call", evidence: "Exploratory", evidenceClass: "exploratory" },
    { id: "rs-demo-048", gene: "SYN-MET", category: "health", categoryLabel: "Health association", coverage: "not-present", coverageLabel: "Not present", observation: "Not tested", evidence: "Conflicting", evidenceClass: "conflicting" }
  ]);

  class GeneticsApiAdapter {
    constructor({ fetchImplementation = window.fetch.bind(window), endpoints = GENETICS_API_ENDPOINTS } = {}) {
      this.fetchImplementation = fetchImplementation;
      this.endpoints = endpoints;
    }

    async request(endpoint, options = {}) {
      const response = await this.fetchImplementation(endpoint, {
        credentials: "same-origin",
        headers: { "Accept": "application/json", "Content-Type": "application/json", ...(options.headers || {}) },
        ...options
      });
      if (!response.ok) {
        throw new Error(`Genetics request failed with status ${response.status}`);
      }
      return response.status === 204 ? null : response.json();
    }

    loadSummary(personId) {
      return this.request(this.endpoints.WORKSPACE_SUMMARY(personId));
    }

    importGenotype(personId, payload) {
      return this.request(this.endpoints.IMPORT(personId), {
        method: "POST",
        body: JSON.stringify(payload)
      });
    }

    compareFamily(personId, personBId) {
      return this.request(this.endpoints.FAMILY_COMPARISON(personId), {
        method: "POST",
        body: JSON.stringify({ person_b_id: personBId })
      });
    }

    runResearch(personId, payload) {
      return this.request(this.endpoints.RESEARCH_RUN(personId), {
        method: "POST",
        body: JSON.stringify(payload)
      });
    }
  }

  const activePersonId = document.body.dataset.personId || "";
  const state = {
    activeTab: "overview",
    surfaceState: "ready",
    initialMarkup: new Map()
  };
  const tabList = document.querySelector('[role="tablist"]');
  const tabs = Array.from(document.querySelectorAll('[role="tab"][data-tab]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"][data-panel]'));
  const stateHosts = Array.from(document.querySelectorAll("[data-state-host]"));
  const status = document.querySelector("#workspace-status");
  const demoState = document.querySelector("#demo-state");
  const variantSearch = document.querySelector("#variant-search");
  const coverageFilter = document.querySelector("#coverage-filter");
  const categoryFilter = document.querySelector("#category-filter");

  function announce(message) {
    if (status) status.textContent = message;
  }

  function cacheInitialMarkup() {
    stateHosts.forEach((host) => state.initialMarkup.set(host.dataset.stateHost, host.innerHTML));
  }

  function activateTab(tabName, { focus = false } = {}) {
    const nextTab = tabs.find((tab) => tab.dataset.tab === tabName);
    if (!nextTab) return;
    state.activeTab = tabName;
    tabs.forEach((tab) => {
      const selected = tab === nextTab;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    panels.forEach((panel) => { panel.hidden = panel.dataset.panel !== tabName; });
    if (focus) nextTab.focus();
    announce(`${nextTab.querySelector("span").textContent} section selected.`);
  }

  function moveTabFocus(currentIndex, direction) {
    const nextIndex = (currentIndex + direction + tabs.length) % tabs.length;
    activateTab(tabs[nextIndex].dataset.tab, { focus: true });
  }

  function handleTabKeydown(event) {
    const currentIndex = tabs.indexOf(event.target);
    if (currentIndex < 0) return;
    const isHorizontal = window.matchMedia("(max-width: 980px)").matches;
    const previousKey = isHorizontal ? "ArrowLeft" : "ArrowUp";
    const nextKey = isHorizontal ? "ArrowRight" : "ArrowDown";
    if (event.key === previousKey || event.key === nextKey) {
      event.preventDefault();
      moveTabFocus(currentIndex, event.key === nextKey ? 1 : -1);
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      activateTab(tabs[event.key === "Home" ? 0 : tabs.length - 1].dataset.tab, { focus: true });
    }
  }

  function stateMessage(kind, panelName) {
    const panelLabel = tabs.find((tab) => tab.dataset.tab === panelName)?.querySelector("span")?.textContent || "Genetics";
    if (kind === "loading") {
      return `<div class="state-card" role="status" aria-live="polite"><div class="state-skeleton" aria-hidden="true"><i></i><i></i><i></i><i></i></div><span class="sr-only">Loading ${panelLabel}.</span></div>`;
    }
    if (kind === "empty") {
      const explanation = panelName === "variants"
        ? "No selectively indexed observations match this view. An absent chip locus is untested, not a reference genotype."
        : "No synthetic records are available for this section. Raw genome content is never shown as a fallback.";
      return `<div class="state-card"><h3>Nothing to review yet</h3><p>${explanation}</p><button class="button-secondary" type="button" data-action="restore-ready">Return to demo data</button></div>`;
    }
    return `<div class="state-card error" role="alert"><h3>This genetics view could not be loaded</h3><p>No sensitive values were exposed. Try the synthetic view again, or return later when the local service is available.</p><button class="button-secondary" type="button" data-action="restore-ready">Try synthetic view again</button></div>`;
  }

  function applySurfaceState(kind) {
    state.surfaceState = kind;
    stateHosts.forEach((host) => {
      const panelName = host.dataset.stateHost;
      if (kind === "ready") {
        if (panelName === "variants") renderVariants();
        else host.innerHTML = state.initialMarkup.get(panelName) || "";
      } else {
        host.innerHTML = stateMessage(kind, panelName);
      }
    });
    if (kind === "ready") {
      updateResearchReadiness();
      updateContextCount();
    }
    announce(kind === "ready" ? "Synthetic genetics data restored." : `${kind} state preview shown.`);
  }

  function filteredVariants() {
    const search = (variantSearch?.value || "").trim().toLowerCase();
    const coverage = coverageFilter?.value || "all";
    const category = categoryFilter?.value || "all";
    return SYNTHETIC_VARIANTS.filter((variant) => {
      const matchesSearch = !search || variant.id.toLowerCase().includes(search) || variant.gene.toLowerCase().includes(search);
      const matchesCoverage = coverage === "all" || variant.coverage === coverage;
      const matchesCategory = category === "all" || variant.category === category;
      return matchesSearch && matchesCoverage && matchesCategory;
    });
  }

  function variantMarkup(variant) {
    return `<article class="observation-row" data-variant-id="${variant.id}">
      <div><span class="evidence-badge evidence-${variant.evidenceClass}">${variant.evidence}</span><h3>${variant.gene}</h3><small>${variant.id}</small></div>
      <div><small>Indexed observation</small><p class="genotype">${variant.observation}</p></div>
      <div><small>${variant.categoryLabel}</small><p class="coverage-state ${variant.coverage}">${variant.coverageLabel}</p></div>
      <details><summary>Provenance</summary><div class="provenance-detail"><p><strong>Source:</strong> Immutable synthetic dataset</p><p><strong>Build:</strong> GRCh37 / hg19</p><p><strong>Orientation:</strong> ${variant.coverage === "present" ? "Resolved" : "Not interpreted"}</p><p><strong>Boundary:</strong> Selected observation only. Raw source rows are not rendered.</p></div></details>
    </article>`;
  }

  function renderVariants() {
    const host = document.querySelector('[data-state-host="variants"]');
    if (!host || state.surfaceState !== "ready") return;
    const variants = filteredVariants();
    host.innerHTML = variants.length
      ? variants.map(variantMarkup).join("")
      : '<div class="state-card"><h3>No matching indexed observations</h3><p>Adjust the filters. Not present and no-call observations remain distinct from a confirmed reference genotype.</p><button class="button-secondary" type="button" data-action="clear-variant-filters">Clear filters</button></div>';
    const count = document.querySelector("#panel-variants .count-label");
    if (count) count.textContent = `${variants.length} shown`;
    announce(`${variants.length} synthetic indexed observations shown.`);
  }

  function clearVariantFilters() {
    if (variantSearch) variantSearch.value = "";
    if (coverageFilter) coverageFilter.value = "all";
    if (categoryFilter) categoryFilter.value = "all";
    renderVariants();
    variantSearch?.focus();
  }

  function updateResearchReadiness() {
    const confirmation = document.querySelector("#disclosure-confirmation");
    const button = document.querySelector("#run-research");
    const message = document.querySelector("#research-readiness");
    if (!confirmation || !button || !message) return;
    const confirmed = confirmation.checked;
    button.disabled = !confirmed;
    message.textContent = confirmed
      ? "Disclosure confirmed for this run only."
      : "Confirm external disclosure to continue.";
  }

  function updateContextCount() {
    const selected = document.querySelectorAll('#research-form input[name="context"]:checked').length;
    const count = document.querySelector("#context-count");
    if (count) count.textContent = `${selected} selected item${selected === 1 ? "" : "s"}`;
  }

  function updateResearchMode(mode) {
    const statusLabel = document.querySelector(".epistemic-status");
    const title = document.querySelector("#hypothesis-title");
    if (statusLabel) statusLabel.textContent = mode === "explore" ? "Plausible" : "Supported synthesis";
    if (title) title.textContent = mode === "explore" ? "Synthetic pathway hypothesis" : "Synthetic evidence synthesis";
    announce(`${mode === "explore" ? "Explore" : "Evidence"} mode selected.`);
  }

  function handleFamilyComparison(event) {
    event.preventDefault();
    const secondPerson = document.querySelector("#family-person-b")?.value;
    const gate = document.querySelector("#family-gate");
    const results = document.querySelector("#family-results");
    if (!gate || !results) return;
    const authorized = secondPerson === "synthetic-b";
    gate.hidden = authorized;
    results.hidden = !authorized;
    announce(authorized ? "Synthetic family coverage comparison shown." : "Choose a separately authorized profile before comparing.");
    (authorized ? results : gate).focus?.();
  }

  function handleResearchSubmit(event) {
    event.preventDefault();
    const confirmation = document.querySelector("#disclosure-confirmation");
    const button = document.querySelector("#run-research");
    if (!confirmation?.checked) {
      updateResearchReadiness();
      confirmation?.focus();
      return;
    }
    const output = document.querySelector(".research-output");
    if (!output || !button) return;
    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Running bounded research...";
    output.setAttribute("aria-busy", "true");
    announce("Running synthetic bounded research.");
    window.setTimeout(() => {
      output.removeAttribute("aria-busy");
      button.textContent = originalLabel;
      updateResearchReadiness();
      announce("Synthetic bounded research result is ready. No raw genome content was disclosed.");
    }, 450);
  }

  function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("The local file could not be read."));
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
      reader.readAsDataURL(file);
    });
  }

  async function handleImportSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const statusNode = document.querySelector("#genetics-import-status");
    const file = document.querySelector("#genetics-file")?.files?.[0];
    if (!activePersonId || !file) {
      if (statusNode) statusNode.textContent = "Select a genetics-authorized profile and local TXT file first.";
      return;
    }
    const submit = form.querySelector("button[type='submit']");
    if (submit) submit.disabled = true;
    try {
      const payloadBase64 = await readFileAsBase64(file);
      await new GeneticsApiAdapter().importGenotype(activePersonId, {
        filename: file.name,
        payload_base64: payloadBase64,
        genome_build: document.querySelector("#genetics-build")?.value || "unknown",
        confirmation: Boolean(document.querySelector("#genetics-import-confirmation")?.checked)
      });
      if (statusNode) statusNode.textContent = "Imported locally. The source is immutable; indexed coverage is ready to review.";
      announce("Genetic source imported locally.");
    } catch (error) {
      if (statusNode) statusNode.textContent = error instanceof Error ? error.message : "The local import failed.";
      announce("Genetic import failed without exposing source values.");
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  function addQuestionToVisit(button) {
    const question = document.querySelector("#visit-question")?.textContent?.trim() || "";
    const handoffStatus = document.querySelector("#visit-handoff-status");
    const event = new CustomEvent("genetics:visit-question-handoff", {
      bubbles: true,
      detail: Object.freeze({ question, source: "genetics-research", synthetic: true })
    });
    button.dispatchEvent(event);
    if (handoffStatus) handoffStatus.textContent = "Question prepared for Visit handoff. Choose a Visit in the connected workspace to save it.";
    announce("Synthetic question prepared for Visit handoff.");
  }

  function handleAction(button) {
    const action = button.dataset.action;
    if (action === "restore-ready") {
      if (demoState) demoState.value = "ready";
      applySurfaceState("ready");
    } else if (action === "clear-variant-filters") {
      clearVariantFilters();
    } else if (action === "toggle-evidence-help") {
      const help = document.querySelector("#evidence-help");
      if (!help) return;
      help.hidden = !help.hidden;
      button.setAttribute("aria-expanded", String(!help.hidden));
    } else if (action === "add-to-visit") {
      addQuestionToVisit(button);
    }
  }

  function handleDocumentClick(event) {
    const tab = event.target.closest('[role="tab"][data-tab]');
    if (tab) {
      activateTab(tab.dataset.tab);
      return;
    }
    const actionButton = event.target.closest("button[data-action]");
    if (actionButton) handleAction(actionButton);
  }

  function handleDocumentChange(event) {
    if (event.target === demoState) {
      applySurfaceState(demoState.value);
    } else if (event.target.matches("#variant-filters select")) {
      renderVariants();
    } else if (event.target.matches("#disclosure-confirmation")) {
      updateResearchReadiness();
    } else if (event.target.matches('input[name="research-mode"]')) {
      updateResearchMode(event.target.value);
    } else if (event.target.matches('#research-form input[name="context"]')) {
      updateContextCount();
    }
  }

  function handleDocumentSubmit(event) {
    if (event.target.matches("#genetics-import-form")) {
      void handleImportSubmit(event);
    } else if (event.target.matches("#family-comparison-form")) {
      handleFamilyComparison(event);
    } else if (event.target.matches("#research-form")) {
      handleResearchSubmit(event);
    }
  }

  function init() {
    cacheInitialMarkup();
    renderVariants();
    updateResearchReadiness();
    updateContextCount();
    tabList?.addEventListener("keydown", handleTabKeydown);
    document.addEventListener("click", handleDocumentClick);
    document.addEventListener("change", handleDocumentChange);
    variantSearch?.addEventListener("input", renderVariants);
    document.addEventListener("submit", handleDocumentSubmit);
  }

  window.GeneticsWorkspace = Object.freeze({
    endpoints: GENETICS_API_ENDPOINTS,
    ApiAdapter: GeneticsApiAdapter
  });

  init();
})();
