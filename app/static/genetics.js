(() => {
  "use strict";

  const GENETICS_API_ENDPOINTS = Object.freeze({
    WORKSPACE_SUMMARY: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics`,
    IMPORT: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics/import`,
    FAMILY_COMPARISON: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics/compare`,
    RESEARCH_RUN: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/genetics/research`,
    CAPABILITIES: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/workspace-capabilities`,
    PEOPLE: "/api/product-core/v1/people",
    MEDICATIONS: (personId) => `/api/product-core/v1/people/${encodeURIComponent(personId)}/medications`,
    ACTIVE_PERSON: "/api/family-access/v1/active-person",
  });

  const MAX_UPLOAD_BYTES = 32_000_000;

  // Translation helper (reads #product-shell-translations JSON)
  const translationPayload = document.getElementById("product-shell-translations");
  let translations = {};
  try {
    const parsed = JSON.parse(translationPayload?.textContent || "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) translations = parsed;
  } catch (_) {}
  const t = (key, fallback = key) =>
    typeof translations[key] === "string" && translations[key] ? translations[key] : fallback;

  const byId = (id) => document.getElementById(id);
  const escapeHtml = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]
    );
  const hostFor = (panelName) => document.querySelector(`[data-state-host="${panelName}"]`);

  // State
  const state = {
    activeTab: "overview",
    personId: document.body.dataset.personId || "",
    people: [],
    capabilities: {},
    overview: null,
    medications: [],
    loadVersion: 0,
  };

  // DOM refs
  const status = byId("genetics-status");
  const tabs = Array.from(document.querySelectorAll('[role="tab"][data-tab]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"][data-panel]'));
  const workspaceShell = byId("genetics-workspace-shell");
  const noPersonSection = byId("genetics-no-person");
  const noAccessSection = byId("genetics-no-access");
  const emptySection = byId("genetics-empty");
  const loadErrorSection = byId("genetics-load-error");

  function announce(message) {
    if (status) status.textContent = message;
  }

  // CSRF helper
  const csrfToken = () =>
    document.cookie.split("; ").find((c) => c.startsWith("opencare_csrf="))
      ?.split("=").slice(1).join("=") || "";
  const securedHeaders = (extra = {}) => ({
    "Content-Type": "application/json",
    "X-OpenCare-CSRF": csrfToken(),
    ...extra,
  });

  // API helper
  async function apiRequest(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      headers: securedHeaders(options.headers),
      ...options,
    });
    if (!response.ok) {
      const err = new Error(`HTTP ${response.status}`);
      err.status = response.status;
      try { err.body = await response.json(); } catch (_) {}
      throw err;
    }
    return response.status === 204 ? null : response.json();
  }

  // Tab navigation
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
    announce(`${nextTab.querySelector("span")?.textContent || tabName} ${t("genetics.sections_label")}.`);
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

  // Person identity
  function updateShellPerson(person) {
    const target = byId("product-shell-person-status");
    if (!target) return;
    target.textContent = person ? `${t("workspace.viewing")} ${person.display_name}` : t("person.no_selection");
  }

  function renderPersonIdentity() {
    const name = byId("genetics-person-name");
    const person = state.people.find((p) => p.person_id === state.personId);
    if (name) name.textContent = person ? person.display_name : t("workspace.no_profile_selected");
    updateShellPerson(person || null);
    const clear = byId("genetics-clear-person");
    if (clear) clear.disabled = !state.personId;
  }

  // People
  async function loadPeople() {
    try {
      const response = await apiRequest(GENETICS_API_ENDPOINTS.PEOPLE);
      state.people = Array.isArray(response.people) ? response.people : [];
    } catch (_) {
      state.people = [];
    }
    const selector = byId("genetics-person-selector");
    if (selector) {
      selector.replaceChildren();
      if (!state.people.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = t("workspace.selector_empty");
        selector.append(option);
        selector.disabled = true;
      } else {
        state.people.forEach((person) => {
          const option = document.createElement("option");
          option.value = person.person_id;
          option.textContent = person.display_name;
          option.selected = person.person_id === state.personId;
          selector.append(option);
        });
        selector.disabled = false;
      }
    }
    if (!state.people.some((p) => p.person_id === state.personId)) state.personId = "";
    renderPersonIdentity();
  }

  // Set active person
  async function setActivePerson(personId) {
    await apiRequest(GENETICS_API_ENDPOINTS.ACTIVE_PERSON, {
      method: "PUT",
      body: JSON.stringify({ person_id: personId }),
    });
    state.personId = personId;
  }

  // Surface states
  function showOnly(section) {
    [noPersonSection, noAccessSection, emptySection, loadErrorSection].forEach((node) => {
      if (node) node.hidden = node !== section;
    });
    if (workspaceShell) workspaceShell.hidden = true;
    if (section === noPersonSection || section === noAccessSection || section === loadErrorSection) {
      const cta = byId("genetics-import-cta");
      if (cta) cta.hidden = true;
    }
  }

  function showNoPerson() {
    showOnly(noPersonSection);
    const selector = byId("genetics-person-selector");
    if (selector) selector.value = "";
    announce(t("genetics.no_person"));
  }

  function showNoAccess() {
    showOnly(noAccessSection);
    announce(t("genetics.no_access"));
  }

  function showLoadError() {
    showOnly(loadErrorSection);
    announce(t("genetics.load_error"));
  }

  function showEmpty() {
    showOnly(emptySection);
    const cta = byId("genetics-import-cta");
    if (cta) cta.hidden = !state.capabilities.genetics_write;
    announce(t("genetics.empty_title"));
  }

  function showWorkspace() {
    [noPersonSection, noAccessSection, emptySection, loadErrorSection].forEach((node) => {
      if (node) node.hidden = true;
    });
    if (workspaceShell) workspaceShell.hidden = false;
    const cta = byId("genetics-import-cta");
    if (cta) cta.hidden = true;
  }

  // Load genetics workspace
  async function loadGeneticsWorkspace(personId) {
    state.loadVersion++;
    const generation = state.loadVersion;
    announce(t("genetics.loading"));
    try {
      const capabilitiesResponse = await apiRequest(GENETICS_API_ENDPOINTS.CAPABILITIES(personId));
      if (generation !== state.loadVersion || capabilitiesResponse.person_id !== personId) return;
      state.capabilities = capabilitiesResponse.capabilities || {};
      if (!state.capabilities.genetics_read) {
        showNoAccess();
        return;
      }
      const overview = await apiRequest(GENETICS_API_ENDPOINTS.WORKSPACE_SUMMARY(personId));
      if (generation !== state.loadVersion || overview.person_id !== personId) return;
      state.overview = overview;
      if (state.overview.dataset === null) {
        state.medications = [];
        showEmpty();
        return;
      }
      if (state.capabilities.medication_read) {
        try {
          const medications = await apiRequest(GENETICS_API_ENDPOINTS.MEDICATIONS(personId));
          if (generation !== state.loadVersion) return;
          state.medications = Array.isArray(medications.medications) ? medications.medications : [];
        } catch (_) {
          if (generation !== state.loadVersion) return;
          state.medications = [];
        }
      } else {
        state.medications = [];
      }
      const contextOptions = byId("research-context-options");
      if (contextOptions) contextOptions.replaceChildren();
      const researchOutput = byId("research-output");
      if (researchOutput) researchOutput.hidden = true;
      const contextCount = byId("context-count");
      if (contextCount) contextCount.hidden = true;
      const disclosure = byId("disclosure-confirmation");
      if (disclosure) disclosure.checked = false;
      byId("research-question").value = "";
      showWorkspace();
      renderAll();
      activateTab("overview");
    } catch (error) {
      if (generation !== state.loadVersion) return;
      showLoadError();
    }
  }

  // Rendering helpers
  const EVIDENCE_LEVEL_ORDER = ["Clinical", "High", "Moderate", "Low", "Exploratory", "Conflicting"];

  function evidenceClass(level) {
    const normalized = String(level || "").toLowerCase();
    const known = ["clinical", "high", "moderate", "low", "exploratory", "conflicting"];
    return known.includes(normalized) ? normalized : "moderate";
  }

  function statusLabel(statusValue) {
    const map = {
      pending: t("genetics.status_pending"),
      reviewed: t("genetics.status_reviewed"),
      dismissed: t("genetics.status_dismissed"),
      unsupported: t("genetics.status_unsupported"),
      conflicting: t("genetics.status_conflicting"),
    };
    return map[statusValue] || statusValue;
  }

  function categoryLabel(category) {
    const map = {
      pgx: t("genetics.category_pgx"),
      health: t("genetics.category_health"),
      health_association: t("genetics.category_health"),
      trait: t("genetics.category_trait"),
    };
    return map[category] || category;
  }

  function observationCoverageLabel(coverageState) {
    if (coverageState === "present" || coverageState === "indexed") {
      return { label: t("genetics.coverage_present"), css: "present" };
    }
    if (coverageState === "no_call") {
      return { label: t("genetics.coverage_no_call"), css: "no-call" };
    }
    return { label: t("genetics.coverage_not_present"), css: "not-present" };
  }

  function donutGradient(coverage, targets) {
    const present = Number(coverage?.present_loci) || 0;
    const noCall = Number(coverage?.no_call_loci) || 0;
    const notPresent = Number(coverage?.not_present_loci) || 0;
    if (!targets) return "var(--surface-alt)";
    const p1 = (present / targets) * 100;
    const p2 = ((present + noCall) / targets) * 100;
    return `conic-gradient(var(--accent) 0 ${p1}%, #b8892e ${p1}% ${p2}%, #cbd5d1 ${p2}% 100%)`;
  }

  function renderAll() {
    renderOverview();
    renderVariants();
    renderPGx();
    renderHealth();
    renderTraits();
    renderEvidence();
    renderFamily();
    renderResearch();
  }

  // Overview
  function renderOverview() {
    const host = hostFor("overview");
    const overview = state.overview;
    const importForm = byId("genetics-import-form");
    const seal = byId("overview-source-seal");
    if (!host) return;
    if (importForm) {
      importForm.hidden = !(state.capabilities.genetics_write && (!overview || overview.dataset === null));
    }
    if (!overview || overview.dataset === null) {
      if (seal) seal.hidden = true;
      host.innerHTML = `<div class="state-card"><h3>${escapeHtml(t("genetics.empty_title"))}</h3><p>${escapeHtml(t("genetics.empty_help"))}</p></div>`;
      return;
    }
    const dataset = overview.dataset || {};
    const coverage = overview.coverage || {};
    const targets = Number(coverage.target_loci) || 0;
    const present = Number(coverage.present_loci) || 0;
    const noCall = Number(coverage.no_call_loci) || 0;
    const notPresent = Number(coverage.not_present_loci) || 0;
    if (seal) {
      const hash = String(dataset.source_hash || "");
      seal.textContent = `${t("genetics.provenance_label")} · ${hash.slice(0, 12) || t("genetics.dataset_immutable")}`;
      seal.hidden = false;
    }
    const findings = Array.isArray(overview.findings) ? overview.findings : [];
    const reviewedCount = findings.filter((f) => f.status === "reviewed").length;
    const evidenceCount = new Set(findings.map((f) => f.evidence_id)).size;
    const indexedCount = Number(dataset.indexed_loci_count) || 0;
    const distribution = overview.evidence_level_distribution || {};
    const strip = EVIDENCE_LEVEL_ORDER
      .filter((level) => Number(distribution[level]) > 0)
      .map((level) => `<span class="evidence-badge evidence-${evidenceClass(level)}">${escapeHtml(level)} ${Number(distribution[level])}</span>`)
      .join("");
    host.innerHTML = `
      <div class="coverage-notice" role="note">
        <strong>${escapeHtml(t("genetics.coverage_note_title"))}</strong>
        <p>${escapeHtml(t("genetics.coverage_note_body"))}</p>
      </div>
      <div class="overview-ledger">
        <div class="dataset-facts">
          <h3>${escapeHtml(t("genetics.overview_dataset"))}</h3>
          <dl>
            <div><dt>${escapeHtml(t("genetics.import_file_label"))}</dt><dd>${escapeHtml(dataset.original_filename || "")}</dd></div>
            <div><dt>${escapeHtml(t("genetics.import_build_label"))}</dt><dd>${escapeHtml(dataset.genome_build || t("genetics.build_unknown"))}</dd></div>
            <div><dt>${escapeHtml(t("genetics.dataset_imported"))}</dt><dd>${escapeHtml(dataset.imported_at || "")}</dd></div>
            <div><dt>${escapeHtml(t("genetics.dataset_parser"))}</dt><dd>${escapeHtml(dataset.parser || "")} · v${escapeHtml(dataset.parser_version || "")}</dd></div>
            <div><dt>${escapeHtml(t("genetics.dataset_raw"))}</dt><dd>${escapeHtml(t("genetics.dataset_immutable"))}</dd></div>
          </dl>
        </div>
        <div class="coverage-figure" aria-labelledby="coverage-title">
          <h3 id="coverage-title">${escapeHtml(t("genetics.overview_coverage"))}</h3>
          <div class="coverage-donut" role="img" aria-label="${escapeHtml(`${targets} ${t("genetics.overview_coverage")}: ${present} ${t("genetics.coverage_present")}, ${noCall} ${t("genetics.coverage_no_call")}, ${notPresent} ${t("genetics.coverage_not_present")}`)}" style="background:${donutGradient(coverage, targets)}"><span><strong>${targets}</strong>${escapeHtml(t("genetics.overview_coverage"))}</span></div>
          <ul class="coverage-key">
            <li><i class="key-present"></i><span>${escapeHtml(t("genetics.coverage_present"))}</span><strong>${present}</strong></li>
            <li><i class="key-no-call"></i><span>${escapeHtml(t("genetics.coverage_no_call"))}</span><strong>${noCall}</strong></li>
            <li><i class="key-absent"></i><span>${escapeHtml(t("genetics.coverage_not_present"))}</span><strong>${notPresent}</strong></li>
          </ul>
        </div>
      </div>
      <div class="finding-summary">
        <article><span>${escapeHtml(t("genetics.findings_reviewed"))}</span><strong>${reviewedCount}</strong><small>${escapeHtml(t("genetics.overview_findings"))}</small></article>
        <article><span>${escapeHtml(t("genetics.evidence_entries"))}</span><strong>${evidenceCount}</strong><small>${escapeHtml(t("genetics.evidence_help"))}</small></article>
        <article><span>${escapeHtml(t("genetics.loci_indexed"))}</span><strong>${indexedCount}</strong><small>${escapeHtml(t("genetics.raw_source_note"))}</small></article>
      </div>
      ${strip ? `<div class="evidence-strip" aria-label="${escapeHtml(t("genetics.overview_evidence"))}">${strip}</div>` : ""}
    `;
  }

  // Variants
  function renderVariants() {
    const host = hostFor("variants");
    if (!host) return;
    const observations = Array.isArray(state.overview?.observations) ? state.overview.observations : [];
    const coverageSelect = byId("coverage-filter");
    const categorySelect = byId("category-filter");
    const search = (byId("variant-search")?.value || "").trim().toLowerCase();
    const coverageFilter = coverageSelect?.value || "all";
    const categoryFilter = categorySelect?.value || "all";

    if (coverageSelect && coverageSelect.options.length <= 1) {
      const seen = [];
      observations.forEach((row) => {
        const value = row.coverage_state;
        if (!seen.includes(value) && (value === "present" || value === "no_call")) seen.push(value);
      });
      if (coverageSelect.options.length === 1) {
        seen.forEach((value) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = observationCoverageLabel(value).label;
          coverageSelect.append(option);
        });
      }
    }
    if (categorySelect && categorySelect.options.length <= 1) {
      const seen = [];
      observations.forEach((row) => {
        const category = row.category || "";
        if (category && !seen.includes(category)) seen.push(category);
      });
      if (categorySelect.options.length === 1) {
        seen.forEach((category) => {
          const option = document.createElement("option");
          option.value = category;
          option.textContent = categoryLabel(category);
          categorySelect.append(option);
        });
      }
    }

    const filtered = observations.filter((row) => {
      const matchesSearch = !search
        || String(row.rsid || "").toLowerCase().includes(search)
        || String(row.gene || "").toLowerCase().includes(search);
      const matchesCoverage = coverageFilter === "all" || row.coverage_state === coverageFilter;
      const matchesCategory = categoryFilter === "all" || (row.category || "") === categoryFilter;
      return matchesSearch && matchesCoverage && matchesCategory;
    });

    const countLabel = byId("variant-count");
    if (countLabel) {
      countLabel.textContent = t("genetics.variants_count").replace("{count}", String(filtered.length));
      countLabel.hidden = !filtered.length;
    }

    const filtersActive = Boolean(search) || coverageFilter !== "all" || categoryFilter !== "all";
    if (!filtered.length) {
      host.innerHTML = `<div class="state-card"><h3>${escapeHtml(t("genetics.variants_empty"))}</h3>${filtersActive ? `<button class="button-secondary" type="button" data-action="clear-variant-filters">${escapeHtml(t("genetics.filter_all"))}</button>` : ""}</div>`;
      renderVariantCountMessage(filtered.length);
      return;
    }
    host.innerHTML = filtered.map((row) => {
      const coverage = observationCoverageLabel(row.coverage_state);
      const category = row.category || "";
      return `<article class="observation-row" data-observation-id="${escapeHtml(row.observation_id || "")}">
        <div><h3>${escapeHtml(row.gene || row.rsid || "")}</h3><small>${escapeHtml(row.rsid || "")}</small></div>
        <div><small>${escapeHtml(categoryLabel(category))}</small><p class="genotype">${escapeHtml(String(row.no_call) === "1" || row.no_call === 1 ? t("genetics.coverage_no_call") : row.normalized_genotype || "")}</p></div>
        <div><small>${escapeHtml(t("genetics.tab_variants_sub"))}</small><p class="coverage-state ${coverage.css}">${escapeHtml(coverage.label)}</p></div>
        <details><summary>${escapeHtml(t("genetics.provenance_label"))}</summary><div class="provenance-detail">
          <p><strong>${escapeHtml(t("genetics.import_build_label"))}:</strong> ${escapeHtml(row.genome_build || t("genetics.build_unknown"))}</p>
          <p><strong>Orientation:</strong> ${escapeHtml(row.orientation_state || "")}</p>
          <p><strong>${escapeHtml(t("genetics.provenance_label"))}:</strong> ${escapeHtml(t("genetics.raw_source_note"))}</p>
        </div></details>
      </article>`;
    }).join("");
    renderVariantCountMessage(filtered.length);
  }

  function renderVariantCountMessage(count) {
    announce(t("genetics.variants_count").replace("{count}", String(count)));
  }

  function clearVariantFilters() {
    byId("variant-search").value = "";
    byId("coverage-filter").value = "all";
    byId("category-filter").value = "all";
    renderVariants();
    byId("variant-search").focus();
  }

  // PGx
  function renderPGx() {
    const host = hostFor("pgx");
    if (!host) return;
    const intersections = Array.isArray(state.overview?.pgx_intersections) ? state.overview.pgx_intersections : [];
    if (!intersections.length) {
      host.innerHTML = `<div class="state-card"><h3>${escapeHtml(t("genetics.pgx_empty"))}</h3><p>${escapeHtml(t("genetics.pgx_boundary_note"))}</p></div>`;
      return;
    }
    host.innerHTML = intersections.map((item) => `
      <article class="pgx-path">
        <div class="path-node"><span>${escapeHtml(t("genetics.tab_variants_sub"))}</span><strong>${escapeHtml(item.gene || "")}</strong><small>${escapeHtml(t("genetics.category_pgx"))}</small></div>
        <div class="path-arrow" aria-hidden="true">→</div>
        <div class="path-node"><span>${escapeHtml(t("genetics.observation_label"))}</span><strong>${escapeHtml(item.association || "")}</strong><small>${escapeHtml(t("genetics.pgx_boundary"))}</small></div>
        <div class="path-arrow" aria-hidden="true">→</div>
        <div class="path-node"><span>${escapeHtml(t("genetics.tab_pgx_sub"))}</span><strong>${escapeHtml(item.medication_name || "")}</strong><small>${escapeHtml(t("workspace.medications"))}</small></div>
        <div class="path-result"><span class="evidence-badge evidence-${evidenceClass(item.evidence_level)}">${escapeHtml(item.evidence_level || "")}</span><p>${escapeHtml(t("genetics.pgx_boundary_note"))}</p></div>
        <details><summary>${escapeHtml(t("genetics.provenance_label"))}</summary><div class="provenance-detail">
          <p><strong>${escapeHtml(t("genetics.provenance_label"))}:</strong> ${escapeHtml(item.source_citation || "")}</p>
          ${Array.isArray(item.limitations) ? item.limitations.map((limit) => `<p>${escapeHtml(limit)}</p>`).join("") : ""}
        </div></details>
      </article>`).join("");
  }

  // Health
  const HEALTH_CATEGORIES = ["health", "health_association", "nutrition"];

  function renderHealth() {
    const host = hostFor("health");
    if (!host) return;
    const findings = (Array.isArray(state.overview?.findings) ? state.overview.findings : [])
      .filter((f) => HEALTH_CATEGORIES.includes(f.category));
    if (!findings.length) {
      host.innerHTML = `<div class="state-card"><h3>${escapeHtml(t("genetics.health_empty"))}</h3><p>${escapeHtml(t("genetics.health_help"))}</p></div>`;
      return;
    }
    const groups = new Map();
    findings.forEach((finding) => {
      if (!groups.has(finding.category)) groups.set(finding.category, []);
      groups.get(finding.category).push(finding);
    });
    host.innerHTML = Array.from(groups.entries()).map(([category, rows]) => `
      <section class="association-group">
        <header><h3>${escapeHtml(categoryLabel(category))}</h3><span>${rows.length}</span></header>
        ${rows.map((f) => `
          <article class="finding-row">
            <div><span class="evidence-badge evidence-${evidenceClass(f.evidence_level)}">${escapeHtml(f.evidence_level || "")}</span><h4>${escapeHtml(f.title || "")}</h4><p>${escapeHtml(f.association || "")}</p></div>
            <span class="review-state">${escapeHtml(statusLabel(f.status))}</span>
          </article>`).join("")}
      </section>`).join("");
  }

  // Traits
  const TRAIT_CATEGORIES = ["trait", "exploratory"];

  function renderTraits() {
    const host = hostFor("traits");
    if (!host) return;
    const findings = (Array.isArray(state.overview?.findings) ? state.overview.findings : [])
      .filter((f) => TRAIT_CATEGORIES.includes(f.category));
    if (!findings.length) {
      host.innerHTML = `<div class="state-card"><h3>${escapeHtml(t("genetics.traits_empty"))}</h3><p>${escapeHtml(t("genetics.traits_help"))}</p></div>`;
      return;
    }
    host.innerHTML = findings.map((f) => `
      <article class="pathway-card">
        <div class="pathway-map" aria-hidden="true"><i></i><i></i></div>
        <div><span class="evidence-badge evidence-${evidenceClass(f.evidence_level)}">${escapeHtml(f.evidence_level || "")}</span><h3>${escapeHtml(f.title || "")}</h3><p>${escapeHtml(f.association || "")}</p><details><summary>${escapeHtml(t("genetics.provenance_label"))}</summary><div class="provenance-detail"><p><strong>${escapeHtml(t("genetics.status_reviewed"))}:</strong> ${escapeHtml(statusLabel(f.status))}</p><p>${escapeHtml(t("genetics.raw_source_note"))}</p></div></details></div>
      </article>`).join("");
  }

  // Evidence
  function renderEvidence() {
    const host = hostFor("evidence");
    if (!host) return;
    const findings = Array.isArray(state.overview?.findings) ? state.overview.findings : [];
    const byEvidence = new Map();
    findings.forEach((f) => {
      if (f.evidence_id && !byEvidence.has(f.evidence_id)) byEvidence.set(f.evidence_id, f);
    });
    if (!byEvidence.size) {
      host.innerHTML = `<div class="state-card"><h3>${escapeHtml(t("genetics.evidence_empty"))}</h3><p>${escapeHtml(t("genetics.evidence_help"))}</p></div>`;
      return;
    }
    host.innerHTML = Array.from(byEvidence.values()).map((entry) => {
      const limitations = (() => {
        try {
          const parsed = JSON.parse(entry.limitations_json || "[]");
          return Array.isArray(parsed) ? parsed : [];
        } catch (_) { return []; }
      })();
      return `<article>
        <div><span class="evidence-badge evidence-${evidenceClass(entry.evidence_level)}">${escapeHtml(entry.evidence_level || "")}</span><h3>${escapeHtml(entry.title || "")}</h3><p>${escapeHtml(entry.pack_id || "")} · ${escapeHtml(t("genetics.overview_evidence"))} ${escapeHtml(entry.pack_version || "")}</p></div>
        <dl>
          <div><dt>${escapeHtml(t("genetics.tab_variants_sub"))}</dt><dd>${escapeHtml(statusLabel(entry.status))}</dd></div>
          <div><dt>${escapeHtml(t("genetics.provenance_label"))}</dt><dd>${escapeHtml(entry.source_name || "")}</dd></div>
        </dl>
        <details><summary>${escapeHtml(t("genetics.evidence_help"))}</summary><div class="provenance-detail">
          <p><strong>${escapeHtml(t("genetics.provenance_label"))}:</strong> ${escapeHtml(entry.source_citation || "")}</p>
          ${limitations.map((limit) => `<p>${escapeHtml(limit)}</p>`).join("")}
          <p>${escapeHtml(t("genetics.raw_source_note"))}</p>
        </div></details>
      </article>`;
    }).join("");
  }

  // Family comparison
  function renderFamily() {
    const personASelect = byId("family-person-a");
    const personBSelect = byId("family-person-b");
    const personA = state.people.find((p) => p.person_id === state.personId);
    if (personASelect) {
      personASelect.replaceChildren();
      if (personA) {
        const option = document.createElement("option");
        option.value = personA.person_id;
        option.textContent = personA.display_name;
        personASelect.append(option);
      }
    }
    if (personBSelect) {
      personBSelect.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = t("genetics.family_choose_person_b");
      personBSelect.append(placeholder);
      state.people
        .filter((p) => p.person_id !== state.personId)
        .forEach((p) => {
          const option = document.createElement("option");
          option.value = p.person_id;
          option.textContent = p.display_name;
          personBSelect.append(option);
        });
    }
    const gate = byId("family-gate");
    const results = byId("family-results");
    if (gate) {
      gate.hidden = false;
      gate.innerHTML = `<h3>${escapeHtml(t("genetics.family_choose_person_b"))}</h3><p>${escapeHtml(t("genetics.family_help"))}</p>`;
    }
    if (results) results.hidden = true;
  }

  async function handleFamilyComparison(event) {
    event.preventDefault();
    const personB = byId("family-person-b")?.value;
    const gate = byId("family-gate");
    const results = byId("family-results");
    if (!personB) {
      if (gate) {
        gate.hidden = false;
        gate.innerHTML = `<h3>${escapeHtml(t("genetics.family_choose_person_b"))}</h3><p>${escapeHtml(t("genetics.family_help"))}</p>`;
      }
      announce(t("genetics.family_choose_person_b"));
      return;
    }
    const submit = event.submitter || byId("family-comparison-form")?.querySelector("button[type='submit']");
    if (submit) submit.disabled = true;
    try {
      const result = await apiRequest(GENETICS_API_ENDPOINTS.FAMILY_COMPARISON(state.personId), {
        method: "POST",
        body: JSON.stringify({ person_b_id: personB }),
      });
      if (gate) gate.hidden = true;
      if (results) {
        results.hidden = false;
        if (!result.build_compatible) {
          results.innerHTML = `<div class="comparison-summary"><article><strong>0</strong><span>${escapeHtml(t("genetics.compare_shared"))}</span></article></div><p class="comparison-limit"><strong>${escapeHtml(t("genetics.compare_incompatible"))}</strong></p>`;
        } else {
          results.innerHTML = `
            <div class="comparison-summary">
              <article><strong>${Number(result.common_covered_loci) || 0}</strong><span>${escapeHtml(t("genetics.compare_shared"))}</span></article>
              <article><strong>${Array.isArray(result.shared_loci) ? result.shared_loci.length : 0}</strong><span>${escapeHtml(t("genetics.compare_matching"))}</span></article>
              <article><strong>${Array.isArray(result.differing_loci) ? result.differing_loci.length : 0}</strong><span>${escapeHtml(t("genetics.compare_differing"))}</span></article>
            </div>
            <p class="comparison-limit"><strong>${escapeHtml(t("genetics.family_limit"))}</strong></p>`;
        }
      }
      announce(t("genetics.family_compare_submit"));
    } catch (error) {
      if (gate) {
        gate.hidden = false;
        if (error.status === 404) {
          gate.innerHTML = `<h3>${escapeHtml(t("genetics.family_no_access"))}</h3><p>${escapeHtml(t("genetics.family_no_access_help"))}</p>`;
        } else {
          gate.innerHTML = `<h3>${escapeHtml(t("genetics.load_error"))}</h3>`;
        }
      }
      if (results) results.hidden = true;
      announce(t("genetics.family_no_access"));
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  // Research Studio
  function renderResearch() {
    const host = hostFor("research");
    const optionsNode = byId("research-context-options");
    const findings = (Array.isArray(state.overview?.findings) ? state.overview.findings : [])
      .filter((f) => f.status === "reviewed");
    const medications = Array.isArray(state.medications) ? state.medications.filter((m) => m.is_active !== false) : [];
    if (!host) return;
    if (optionsNode && !optionsNode.childElementCount) {
      if (findings.length) {
        findings.forEach((finding) => {
          const label = document.createElement("label");
          const input = document.createElement("input");
          input.type = "checkbox";
          input.name = "context-finding";
          input.value = finding.finding_id;
          input.checked = true;
          label.append(input);
          label.append(document.createTextNode(` ${categoryLabel(finding.category)}: ${finding.title || finding.finding_id}`));
          optionsNode.append(label);
        });
      }
      medications.forEach((medication) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.name = "context-record";
        input.value = medication.id;
        input.checked = true;
        label.append(input);
        label.append(document.createTextNode(` ${t("workspace.medications")}: ${medication.display_name || medication.id}`));
        optionsNode.append(label);
      });
      if (!findings.length && !medications.length) {
        const note = document.createElement("p");
        note.className = "research-context-note";
        note.textContent = t("genetics.research_context_none");
        optionsNode.append(note);
      }
    }
    const providerName = byId("research-provider-name");
    if (providerName) providerName.textContent = t("genetics.research_provider_name");
    updateResearchContext();
  }

  function updateResearchContext() {
    const findings = document.querySelectorAll('#research-context-options input[name="context-finding"]:checked').length;
    const records = document.querySelectorAll('#research-context-options input[name="context-record"]:checked').length;
    const count = byId("context-count");
    if (count) {
      count.textContent = t("genetics.context_count").replace("{count}", String(findings + records));
      count.hidden = findings + records === 0;
    }
    const summary = byId("research-context-summary");
    if (summary) {
      summary.textContent = findings + records
        ? t("genetics.research_context_summary")
            .replace("{findings}", String(findings))
            .replace("{records}", String(records))
        : t("genetics.research_context_none");
    }
    updateResearchReadiness();
  }

  function updateResearchReadiness() {
    const confirmation = byId("disclosure-confirmation");
    const button = byId("run-research");
    const message = byId("research-readiness");
    const available = document.querySelectorAll('#research-context-options input[name="context-finding"]:checked').length > 0;
    if (!confirmation || !button || !message) return;
    const confirmed = confirmation.checked;
    button.disabled = !(confirmed && available);
    message.textContent = !available
      ? t("genetics.research_context_none")
      : confirmed
        ? t("genetics.research_readiness_confirmed")
        : t("genetics.research_readiness_confirm");
  }

  async function handleResearchSubmit(event) {
    event.preventDefault();
    const confirmation = byId("disclosure-confirmation");
    if (!confirmation?.checked) {
      updateResearchReadiness();
      confirmation?.focus();
      return;
    }
    const selectedFindings = Array.from(document.querySelectorAll('#research-context-options input[name="context-finding"]:checked'))
      .map((input) => input.value);
    const selectedRecords = Array.from(document.querySelectorAll('#research-context-options input[name="context-record"]:checked'))
      .map((input) => {
        const record = state.medications.find((m) => m.id === input.value);
        return record
          ? { id: record.id, person_id: record.person_id, display_name: record.display_name || record.id }
          : { id: input.value, person_id: state.personId, display_name: input.value };
      });
    const question = byId("research-question")?.value.trim() || "";
    if (!selectedFindings.length || !question) {
      updateResearchReadiness();
      return;
    }
    const mode = document.querySelector('input[name="research-mode"]:checked')?.value || "evidence";
    const runButton = byId("run-research");
    const output = byId("research-output");
    if (runButton) runButton.disabled = true;
    if (output) {
      output.hidden = false;
      output.setAttribute("aria-busy", "true");
    }
    announce(t("genetics.research_running"));
    try {
      const result = await apiRequest(GENETICS_API_ENDPOINTS.RESEARCH_RUN(state.personId), {
        method: "POST",
        body: JSON.stringify({
          mode,
          question,
          finding_ids: selectedFindings,
          canonical_records: selectedRecords,
          second_person_id: null,
        }),
      });
      renderResearchOutput(result, output);
    } catch (error) {
      if (output) {
        output.innerHTML = `<div class="state-card error"><h3>${escapeHtml(t("genetics.load_error"))}</h3><p>${escapeHtml(t("genetics.research_context_none"))}</p></div>`;
      }
      announce(t("genetics.load_error"));
    } finally {
      if (output) output.removeAttribute("aria-busy");
      if (runButton) {
        runButton.disabled = !confirmation.checked;
        updateResearchReadiness();
      }
    }
  }

  function renderResearchOutput(result, output) {
    if (!output) return;
    const data = result?.output || {};
    const confidence = data.confidence === "supported"
      ? t("genetics.research_supported")
      : data.confidence === "plausible"
        ? t("genetics.research_plausible")
        : String(data.confidence || "");
    const confidenceNode = byId("research-confidence");
    const titleNode = byId("research-output-title");
    if (confidenceNode) confidenceNode.textContent = confidence;
    if (titleNode) titleNode.textContent = t("genetics.research_output_title");
    const resolvingFindingTitle = (id) => {
      const finding = (Array.isArray(state.overview?.findings) ? state.overview.findings : [])
        .find((f) => f.finding_id === id);
      return finding ? finding.title || id : id;
    };
    const sections = [
      { heading: t("genetics.research_what_may_be_happening"), body: `<p>${escapeHtml(data.what_may_be_happening || "")}</p>` },
      { heading: t("genetics.research_evidence_supporting"), body: Array.isArray(data.evidence_supporting) && data.evidence_supporting.length ? `<ul>${data.evidence_supporting.map((id) => `<li>${escapeHtml(resolvingFindingTitle(id))}</li>`).join("")}</ul>` : "" },
      { heading: t("genetics.research_evidence_against"), extraClass: "devils-advocate", body: Array.isArray(data.evidence_against) && data.evidence_against.length ? `<ul>${data.evidence_against.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "" },
      { heading: t("genetics.research_alternative_explanations"), extraClass: "devils-advocate", body: Array.isArray(data.alternative_explanations) && data.alternative_explanations.length ? `<ul>${data.alternative_explanations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "" },
      { heading: t("genetics.research_missing_information"), body: Array.isArray(data.missing_information) && data.missing_information.length ? `<ul>${data.missing_information.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "" },
      { heading: t("genetics.research_questions"), body: Array.isArray(data.questions_worth_investigating) && data.questions_worth_investigating.length ? `<ul>${data.questions_worth_investigating.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : "" },
    ];
    const claims = Array.isArray(data.claims) ? data.claims : [];
    const claimsMarkup = claims.length ? `
      <section>
        <h4>${escapeHtml(t("genetics.research_claims"))}</h4>
        ${claims.map((claim) => `
          <p><strong>${escapeHtml(claim.claim || "")}</strong> <span class="epistemic-status">${escapeHtml(claim.epistemic_status || "")}</span></p>
          ${claim.reasoning_summary ? `<p>${escapeHtml(claim.reasoning_summary)}</p>` : ""}
          ${Array.isArray(claim.limitations) && claim.limitations.length ? `<ul>${claim.limitations.map((limit) => `<li>${escapeHtml(limit)}</li>`).join("")}</ul>` : ""}
        `).join("")}
      </section>` : "";
    const sessionMarkup = `
      <section>
        <h4>${escapeHtml(t("genetics.research_session"))}</h4>
        <p>${escapeHtml(t("genetics.research_help"))}</p>
        <p><strong>context_hash:</strong> ${escapeHtml(result?.packet?.context_hash || "")} · <strong>raw_genome_included:</strong> ${String(result?.packet?.raw_genome_included === false)}</p>
      </section>`;
    output.innerHTML = sections
      .filter((section) => section.body)
      .map((section) => `<section class="${section.extraClass || ""}"><h4>${escapeHtml(section.heading)}</h4>${section.body}</section>`)
      .join("") + claimsMarkup + sessionMarkup;
    announce(t("genetics.research_output_title"));
  }

  // Import
  function readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("file_read_failed"));
      reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
      reader.readAsDataURL(file);
    });
  }

  async function handleImportSubmit(event) {
    event.preventDefault();
    const file = byId("genetics-file")?.files?.[0];
    const statusNode = byId("genetics-import-status");
    const setStatus = (message) => { if (statusNode) statusNode.textContent = message; };
    if (!file) {
      setStatus(t("genetics.import_error_invalid"));
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setStatus(t("genetics.import_error_too_large"));
      return;
    }
    if (!byId("genetics-import-confirmation")?.checked) {
      setStatus(t("genetics.import_error_confirmation"));
      return;
    }
    const submit = byId("genetics-import-submit");
    if (submit) submit.disabled = true;
    try {
      const payloadBase64 = await readFileAsBase64(file);
      await apiRequest(GENETICS_API_ENDPOINTS.IMPORT(state.personId), {
        method: "POST",
        body: JSON.stringify({
          filename: file.name,
          payload_base64: payloadBase64,
          genome_build: byId("genetics-build")?.value || "unknown",
          confirmation: true,
        }),
      });
      setStatus(t("genetics.import_success"));
      announce(t("genetics.import_success"));
      await loadGeneticsWorkspace(state.personId);
    } catch (error) {
      setStatus(error.status === 413
        ? t("genetics.import_error_too_large")
        : error.status === 404
          ? t("genetics.no_access")
          : t("genetics.import_error_invalid"));
      announce(t("genetics.import_error_generic"));
    } finally {
      if (submit) submit.disabled = false;
    }
  }

  function enterImportMode() {
    showWorkspace();
    activateTab("overview", { focus: false });
    renderAll();
    renderOverview();
    const input = byId("genetics-file");
    if (input) input.focus();
  }

  // Init
  function init() {
    const tabList = document.querySelector('[role="tablist"]');
    tabList?.addEventListener("keydown", handleTabKeydown);
    byId("genetics-clear-person")?.addEventListener("click", async () => {
      try {
        await setActivePerson(null);
      } catch (_) {}
      state.people.forEach((person) => {
        const option = byId("genetics-person-selector")?.querySelector(`option[value="${CSS.escape(person.person_id)}"]`);
        if (option) option.selected = false;
      });
      state.personId = "";
      state.overview = null;
      state.capabilities = {};
      renderPersonIdentity();
      showNoPerson();
    });
    byId("genetics-person-selector")?.addEventListener("change", async (event) => {
      const personId = event.target.value;
      if (!personId) {
        state.personId = "";
        showNoPerson();
        return;
      }
      state.personId = personId;
      renderPersonIdentity();
      await loadGeneticsWorkspace(personId);
    });
    byId("genetics-import-form")?.addEventListener("submit", handleImportSubmit);
    byId("genetics-import-cta")?.addEventListener("click", enterImportMode);
    byId("variant-search")?.addEventListener("input", renderVariants);
    byId("coverage-filter")?.addEventListener("change", renderVariants);
    byId("category-filter")?.addEventListener("change", renderVariants);
    byId("family-comparison-form")?.addEventListener("submit", handleFamilyComparison);
    byId("research-form")?.addEventListener("submit", handleResearchSubmit);
    byId("disclosure-confirmation")?.addEventListener("change", updateResearchContext);
    document.querySelectorAll('input[name="research-mode"]').forEach((radio) => {
      radio.addEventListener("change", () => { announce(t("genetics.research_mode_label")); });
    });
    document.addEventListener("click", (event) => {
      const actionButton = event.target.closest("button[data-action]");
      if (!actionButton) return;
      const action = actionButton.dataset.action;
      if (action === "clear-variant-filters") clearVariantFilters();
      if (action === "toggle-evidence-help") {
        const help = byId("evidence-help");
        if (!help) return;
        help.hidden = !help.hidden;
        actionButton.setAttribute("aria-expanded", String(!help.hidden));
      }
    });

    void loadPeople().then(() => {
      if (state.personId) {
        void loadGeneticsWorkspace(state.personId);
      } else {
        showNoPerson();
      }
    });
  }

  window.GeneticsWorkspace = Object.freeze({ endpoints: GENETICS_API_ENDPOINTS });
  init();
})();