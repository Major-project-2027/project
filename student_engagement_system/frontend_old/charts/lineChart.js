/**
 * Phase 8 Dashboard -- dependency-free SVG line chart.
 * points: [{ timestamp: ISOString, value: number }, ...]
 */
import { el } from "../utils/dom.js";
import { formatTime } from "../utils/format.js";

export function renderLineChart(points, { width = 640, height = 220, color = "var(--accent)", label = "" } = {}) {
  if (!points || points.length === 0) {
    return el("div", { class: "chart-empty" }, `No ${label || "data"} recorded yet.`);
  }

  const padding = { top: 16, right: 16, bottom: 28, left: 40 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const values = points.map((p) => Number(p.value) || 0);
  const maxValue = Math.max(...values, 1);
  const minValue = Math.min(...values, 0);
  const range = maxValue - minValue || 1;

  const stepX = points.length > 1 ? innerW / (points.length - 1) : 0;
  const toX = (i) => padding.left + i * stepX;
  const toY = (v) => padding.top + innerH - ((v - minValue) / range) * innerH;

  const linePoints = points.map((p, i) => `${toX(i)},${toY(Number(p.value) || 0)}`).join(" ");
  const areaPoints = `${padding.left},${padding.top + innerH} ${linePoints} ${toX(points.length - 1)},${padding.top + innerH}`;

  const gridLines = [0, 0.5, 1].map((fraction) => {
    const y = padding.top + innerH * fraction;
    return `<line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke="var(--border-subtle)" stroke-width="1" />`;
  }).join("");

  const dots = points.map((p, i) => {
    const x = toX(i);
    const y = toY(Number(p.value) || 0);
    return `<circle cx="${x}" cy="${y}" r="3" fill="${color}"><title>${formatTime(p.timestamp)}: ${p.value}</title></circle>`;
  }).join("");

  const firstLabel = formatTime(points[0].timestamp);
  const lastLabel = formatTime(points[points.length - 1].timestamp);

  const svg = `
    <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
      ${gridLines}
      <polygon points="${areaPoints}" fill="${color}" opacity="0.12" />
      <polyline points="${linePoints}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
      ${dots}
      <text x="${padding.left}" y="${height - 6}" font-size="11" fill="var(--text-muted)">${firstLabel}</text>
      <text x="${width - padding.right}" y="${height - 6}" font-size="11" fill="var(--text-muted)" text-anchor="end">${lastLabel}</text>
    </svg>`;

  const box = el("div", { class: "chart-box" });
  box.innerHTML = svg;
  return box;
}
