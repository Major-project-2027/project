/**
 * Phase 8 Dashboard -- reusable stat card component (used on Dashboard
 * Home for the eight required top-line numbers).
 */
import { el } from "../utils/dom.js";

export function createStatCard({ label, value, icon = "", trend = "" }) {
  return el("div", { class: "card stat-card" }, [
    el("div", { class: "stat-card__top" }, [
      el("span", { class: "stat-card__label" }, label),
      icon ? el("span", { class: "stat-card__icon", html: icon }) : null,
    ]),
    el("div", { class: "stat-card__value" }, String(value)),
    trend ? el("div", { class: "stat-card__trend" }, trend) : null,
  ]);
}
