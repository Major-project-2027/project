/**
 * Phase 8 Dashboard -- left navigation sidebar.
 */
import { el } from "../utils/dom.js";
import { icons } from "../assets/icons.js";

export const NAV_ITEMS = [
  { route: "home", label: "Dashboard", icon: icons.home },
  { route: "analytics", label: "Analytics", icon: icons.chart },
  { route: "reports", label: "Reports", icon: icons.file },
  { route: "students", label: "Students", icon: icons.users },
  { route: "alerts", label: "Alerts", icon: icons.bell },
  { route: "settings", label: "Settings", icon: icons.settings },
];

export function renderSidebar(activeRoute) {
  const links = NAV_ITEMS.map((item) =>
    el(
      "a",
      {
        href: `#/${item.route}`,
        class: `sidebar__link${activeRoute === item.route ? " active" : ""}`,
        dataset: { route: item.route },
      },
      [el("span", { html: item.icon }), el("span", {}, item.label)]
    )
  );

  return el("aside", { class: "sidebar app-sidebar" }, [
    el("div", { class: "sidebar__brand" }, [
      el("span", { style: "width:20px;height:20px;color:var(--accent)", html: icons.spark }),
      el("span", {}, "CogniTrack"),
    ]),
    el("nav", { class: "sidebar__nav" }, links),
  ]);
}
