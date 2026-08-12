/**
 * Phase 8 Dashboard -- application shell. Builds the sidebar/navbar/content
 * grid once, then re-renders only the content area on every route change.
 */
import { el, clear } from "../utils/dom.js";
import { renderSidebar } from "../components/sidebar.js";
import { renderNavbar } from "../components/navbar.js";
import { renderLoading } from "../components/loadingScreen.js";
import { renderError } from "../components/errorScreen.js";
import { startRouter, renderRoute, currentRoute } from "../pages/router.js";
import { getSettings, saveSettings } from "../services/api.js";

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function mountApp(rootSelector = "#app") {
  const root = document.querySelector(rootSelector);
  if (!root) throw new Error(`mountApp: no element matches ${rootSelector}`);

  let theme = getSettings().theme || "dark";
  applyTheme(theme);

  const content = el("main", { class: "app-content" }, [renderLoading("Loading dashboard...")]);

  const shell = () => {
    clear(root);
    root.appendChild(renderSidebar(currentRoute()));
    root.appendChild(
      renderNavbar({
        activeRoute: currentRoute(),
        theme,
        onToggleTheme: () => {
          theme = theme === "dark" ? "light" : "dark";
          applyTheme(theme);
          saveSettings({ theme });
          shell();
        },
      })
    );
    root.appendChild(content);
  };

  const renderContent = async (route) => {
    clear(content);
    content.appendChild(renderLoading());
    try {
      await renderRoute(route, content);
    } catch (err) {
      clear(content);
      content.appendChild(renderError(err.message, () => renderContent(route)));
    }
  };

  shell();
  startRouter((route) => {
    shell();
    renderContent(route);
  });

  return { setTheme: (t) => { theme = t; applyTheme(theme); shell(); } };
}
