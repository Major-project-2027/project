/**
 * Phase 8 Dashboard -- tiny hash-based router. Maps `#/<route>` to a page
 * module's `render(container)` function.
 */
import { renderDashboardHome } from "./dashboardHome.js";
import { renderAnalytics } from "./analytics.js";
import { renderReports } from "./reports.js";
import { renderStudents } from "./students.js";
import { renderAlerts } from "./alerts.js";
import { renderSettings } from "./settings.js";

const ROUTES = {
  home: renderDashboardHome,
  analytics: renderAnalytics,
  reports: renderReports,
  students: renderStudents,
  alerts: renderAlerts,
  settings: renderSettings,
};

export function currentRoute() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  return ROUTES[hash] ? hash : "home";
}

export function startRouter(onNavigate) {
  const handle = () => onNavigate(currentRoute());
  window.addEventListener("hashchange", handle);
  handle();
  return () => window.removeEventListener("hashchange", handle);
}

export function renderRoute(route, container) {
  const renderFn = ROUTES[route] || ROUTES.home;
  return renderFn(container);
}
