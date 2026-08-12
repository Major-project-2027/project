/**
 * Phase 8 Dashboard -- top navbar: page title, live clock, theme toggle.
 */
import { el } from "../utils/dom.js";
import { icons } from "../assets/icons.js";

const ROUTE_TITLES = {
  home: "Dashboard",
  analytics: "Analytics",
  reports: "Reports",
  students: "Students",
  alerts: "Alerts",
  settings: "Settings",
};

export function renderNavbar({ activeRoute, theme, onToggleTheme }) {
  const clock = el("span", { class: "navbar__clock", style: "color:var(--text-secondary);font-size:var(--fs-sm)" });
  const updateClock = () => {
    clock.textContent = new Date().toLocaleTimeString();
  };
  updateClock();
  setInterval(updateClock, 1000);

  const toggle = el(
    "button",
    { class: "theme-toggle", title: "Toggle theme", onClick: onToggleTheme },
    el("span", { style: "width:16px;height:16px", html: theme === "dark" ? icons.sun : icons.moon })
  );

  return el("header", { class: "navbar app-navbar" }, [
    el("div", { class: "navbar__title" }, ROUTE_TITLES[activeRoute] || "Dashboard"),
    el("div", { class: "navbar__right" }, [clock, toggle]),
  ]);
}
