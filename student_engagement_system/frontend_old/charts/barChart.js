/**
 * Phase 8 Dashboard -- dependency-free SVG bar chart.
 * entries: [{ label: string, value: number }, ...]
 */
import { el } from "../utils/dom.js";

export function renderBarChart(entries, { width = 640, height = 220, color = "var(--accent)" } = {}) {
  if (!entries || entries.length === 0) {
    return el("div", { class: "chart-empty" }, "No data recorded yet.");
  }

  const padding = { top: 16, right: 16, bottom: 34, left: 16 };
  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;

  const maxValue = Math.max(...entries.map((e) => Number(e.value) || 0), 1);
  const gap = 10;
  const barWidth = Math.max((innerW - gap * (entries.length - 1)) / entries.length, 4);

  const bars = entries.map((entry, i) => {
    const value = Number(entry.value) || 0;
    const barHeight = (value / maxValue) * innerH;
    const x = padding.left + i * (barWidth + gap);
    const y = padding.top + innerH - barHeight;
    const labelX = x + barWidth / 2;
    return `
      <rect x="${x}" y="${y}" width="${barWidth}" height="${Math.max(barHeight, 1)}" rx="4" fill="${color}">
        <title>${entry.label}: ${value}</title>
      </rect>
      <text x="${labelX}" y="${height - 12}" font-size="11" fill="var(--text-muted)" text-anchor="middle">${entry.label}</text>
    `;
  }).join("");

  const box = el("div", { class: "chart-box" });
  box.innerHTML = `<svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">${bars}</svg>`;
  return box;
}
