/**
 * Phase 8 Dashboard -- small, dependency-free formatting helpers shared by
 * every page and chart module.
 */
export function formatDateTime(isoString) {
  if (!isoString) return "--";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return isoString;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatTime(isoString) {
  if (!isoString) return "--";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return isoString;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

export function formatPercent(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return `${Number(value).toFixed(digits)}%`;
}

export function formatScore(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return Number(value).toFixed(digits);
}

export function formatDurationMinutes(minutes) {
  if (!minutes || Number.isNaN(minutes)) return "0m";
  const total = Math.round(minutes);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function capitalize(text) {
  if (!text) return "";
  const clean = String(text).replace(/_/g, " ").toLowerCase();
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

export function severityTone(severity) {
  switch (severity) {
    case "high":
      return "danger";
    case "medium":
      return "warning";
    case "low":
      return "info";
    default:
      return "neutral";
  }
}

export function levelTone(level) {
  const lvl = String(level || "").toUpperCase();
  if (["VERY_HIGH", "HIGH", "FOCUSED"].includes(lvl)) return "success";
  if (["MODERATE", "NEUTRAL"].includes(lvl)) return "info";
  if (["LOW", "DISTRACTED", "CONFUSED"].includes(lvl)) return "warning";
  if (["VERY_LOW", "FATIGUED", "DISENGAGED", "UNAVAILABLE"].includes(lvl)) return "danger";
  return "neutral";
}
