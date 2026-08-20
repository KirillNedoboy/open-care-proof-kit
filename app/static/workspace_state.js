/* Pure workspace-state helpers for the OpenCare Health Workspace. */
(function (global) {
  "use strict";

  const compareText = (left, right) => String(left || "").localeCompare(String(right || ""), "en", { sensitivity: "base" });
  const compareDate = (left, right) => String(left || "").localeCompare(String(right || ""));

  function shouldApplyResponse(issuedGeneration, currentGeneration) {
    return typeof issuedGeneration === "number" && issuedGeneration === currentGeneration;
  }

  function shouldRefreshCapabilities(status) {
    return status === 401 || status === 403 || status === 404;
  }

  function evidenceFactType(item) {
    if (["medication", "condition", "lab"].includes(item?.fact_type)) return item.fact_type;
    const legacyRecordTypes = {
      confirmed_medication: "medication",
      confirmed_condition: "condition",
      confirmed_lab: "lab",
    };
    return legacyRecordTypes[item?.record_type] || "";
  }

  function sortVisits(visits) {
    return visits.slice().sort((left, right) => {
      const leftDate = left.scheduled_date || "9999-12-31";
      const rightDate = right.scheduled_date || "9999-12-31";
      return compareDate(leftDate, rightDate) || compareText(left.title, right.title) || compareText(left.visit_id, right.visit_id);
    });
  }

  function sortQuestions(questions) {
    return questions.slice().sort((left, right) => Number(left.position) - Number(right.position) || compareText(left.question_id, right.question_id));
  }

  function sortNewest(items, dateKey, idKey) {
    return items.slice().sort((left, right) => compareDate(right[dateKey], left[dateKey]) || compareText(right[idKey], left[idKey]));
  }

  function sanitizeDownloadFilename(value, fallback) {
    const candidate = String(value || "")
      .replace(/[\\/\u0000-\u001f\u007f]/g, "-")
      .replace(/^\.+/, "")
      .trim();
    let safe = candidate || fallback;
    if (!safe.toLowerCase().endsWith(".zip")) safe += ".zip";
    return safe;
  }

  function contentDispositionFilename(header) {
    if (!header) return "";
    const encoded = header.match(/filename\*=UTF-8''([^;]+)/i);
    if (encoded) {
      try { return decodeURIComponent(encoded[1]); } catch (_) { return ""; }
    }
    const plain = header.match(/filename\s*=\s*(?:"([^"]*)"|([^;\s]*))/i);
    return plain ? (plain[1] || plain[2] || "") : "";
  }

  function sanitizeDocumentFilename(value, fallback = "document") {
    const candidate = String(value || "")
      .replace(/[\\/\u0000-\u001f\u007f"]/g, "-")
      .replace(/[?#%]/g, "-")
      .replace(/^\.+/, "")
      .trim()
      .slice(0, 120);
    return candidate || fallback;
  }

  global.OpenCareWorkspaceState = {
    shouldApplyResponse,
    shouldRefreshCapabilities,
    evidenceFactType,
    sortVisits,
    sortQuestions,
    sortNewest,
    sanitizeDownloadFilename,
    contentDispositionFilename,
    sanitizeDocumentFilename,
  };
})(typeof window !== "undefined" ? window : globalThis);
