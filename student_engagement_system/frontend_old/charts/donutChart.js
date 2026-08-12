/**
 * Phase 8 Dashboard -- dependency-free SVG donut / gauge chart, used for
 * single-value indicators (confidence, attention score) and small
 * category breakdowns (emotion/cognitive-state distribution).
 */
import { el } from "../utils/dom.js";

/** Single-value gauge, 0-100 (or 0-1 with asFraction=true). */
export function renderGauge(value, { size = 140, color = "var(--accent)", asFraction = false, label = "" } = {}) {
  const pct = Math.max(0, Math.min(100, asFraction ? value * 100 : value));
  const radius = size / 2 - 10;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);
  const center = size / 2;

  const svg = `
    <svg viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
      <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="var(--border-subtle)" stroke-width="10" />
      <circle cx="${center}" cy="${center}" r="${radius}" fill="none" stroke="${color}" stroke-width="10"
        stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
        transform="rotate(-90 ${center} ${center})" />
      <text x="${center}" y="${center - 2}" text-anchor="middle" font-size="22" font-weight="700" fill="var(--text-primary)">${pct.toFixed(0)}%</text>
      <text x="${center}" y="${center + 18}" text-anchor="middle" font-size="11" fill="var(--text-muted)">${label}</text>
    </svg>`;

  const box = el("div", { class: "chart-box", style: `min-height:${size}px` });
  box.innerHTML = svg;
  return box;
}

/** Category-breakdown donut. counts: { label: count, ... } */
export function renderDonut(counts, { size = 180, palette = null } = {}) {
  const entries = Object.entries(counts || {});
  if (entries.length === 0) {
    return el("div", { class: "chart-empty" }, "No data recorded yet.");
  }
  const defaultPalette = ["var(--accent)", "var(--success)", "var(--warning)", "var(--danger)", "var(--info)"];
  const colors = palette || defaultPalette;

  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
  const radius = size / 2 - 8;
  const center = size / 2;
  let cumulativeAngle = -90;

  const arcs = entries.map(([label, count], i) => {
    const fraction = count / total;
    const angle = fraction * 360;
    const startAngle = cumulativeAngle;
    const endAngle = cumulativeAngle + angle;
    cumulativeAngle = endAngle;

    const toRad = (deg) => (deg * Math.PI) / 180;
    const x1 = center + radius * Math.cos(toRad(startAngle));
    const y1 = center + radius * Math.sin(toRad(startAngle));
    const x2 = center + radius * Math.cos(toRad(endAngle));
    const y2 = center + radius * Math.sin(toRad(endAngle));
    const largeArc = angle > 180 ? 1 : 0;
    const color = colors[i % colors.length];

    return `<path d="M ${center} ${center} L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z"
              fill="${color}" opacity="0.85"><title>${label}: ${count}</title></path>`;
  }).join("");

  const legend = entries.map(([label, count], i) => `
    <div class="row" style="gap:6px;font-size:12px;color:var(--text-secondary)">
      <span style="width:8px;height:8px;border-radius:50%;background:${colors[i % colors.length]};display:inline-block"></span>
      ${label} (${count})
    </div>
  `).join("");

  const box = el("div", { class: "row", style: "align-items:center;gap:16px;flex-wrap:wrap" });
  const svgBox = el("div", { class: "chart-box", style: `max-width:${size}px;min-height:${size}px` });
  svgBox.innerHTML = `<svg viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">${arcs}</svg>`;
  const legendBox = el("div", { class: "stack", style: "gap:4px" });
  legendBox.innerHTML = legend;
  box.appendChild(svgBox);
  box.appendChild(legendBox);
  return box;
}
