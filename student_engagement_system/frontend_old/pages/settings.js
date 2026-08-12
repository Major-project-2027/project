/**
 * Phase 8 Dashboard -- Settings page: theme, camera selection, confidence
 * threshold, alert threshold, backend selection, logging, API
 * configuration. Persists to localStorage via services/api.js.
 */
import { el, mount } from "../utils/dom.js";
import { getSettings, saveSettings, api } from "../services/api.js";
import { showToast } from "../components/toast.js";

export async function renderSettings(container) {
  const settings = getSettings();
  let health = null;
  try {
    health = await api.getHealth();
  } catch (err) {
    health = { status: "unreachable", error: err.message };
  }

  const field = (labelText, inputEl) => el("div", { class: "field" }, [el("label", {}, labelText), inputEl]);

  const themeSelect = el(
    "select",
    { class: "select" },
    ["dark", "light"].map((t) => el("option", { value: t, selected: t === settings.theme ? "selected" : null }, t))
  );

  const cameraInput = el("input", { class: "input", value: settings.camera, placeholder: "e.g. default, USB Camera 0" });

  const confidenceInput = el("input", {
    class: "input",
    type: "number",
    step: "0.05",
    min: "0",
    max: "1",
    value: String(settings.confidenceThreshold),
  });

  const alertInput = el("input", {
    class: "input",
    type: "number",
    step: "0.05",
    min: "0",
    max: "1",
    value: String(settings.alertThreshold),
  });

  const backendSelect = el(
    "select",
    { class: "select" },
    ["rule_based", "ml_based"].map((b) => el("option", { value: b, selected: b === settings.backend ? "selected" : null }, b))
  );

  const loggingCheckbox = el("input", { type: "checkbox", checked: settings.loggingEnabled ? "checked" : null });

  const apiBaseInput = el("input", {
    class: "input",
    value: settings.apiBaseUrl,
    placeholder: "Leave blank to use the same origin as this page",
  });

  const saveButton = el(
    "button",
    {
      class: "btn btn-primary",
      onClick: () => {
        saveSettings({
          theme: themeSelect.value,
          camera: cameraInput.value,
          confidenceThreshold: parseFloat(confidenceInput.value) || 0,
          alertThreshold: parseFloat(alertInput.value) || 0,
          backend: backendSelect.value,
          loggingEnabled: loggingCheckbox.checked,
          apiBaseUrl: apiBaseInput.value.trim(),
        });
        document.documentElement.setAttribute("data-theme", themeSelect.value);
        showToast("Settings saved. Reload for the API base URL to take effect.", "success");
      },
    },
    "Save Settings"
  );

  const statusBadge = el(
    "span",
    { class: `badge badge-${health.status === "ok" ? "success" : "danger"}` },
    health.status === "ok" ? `Connected (${health.events_recorded ?? 0} events)` : "Unreachable"
  );

  const page = el("div", {}, [
    el("div", { class: "page-header" }, [
      el("div", {}, [
        el("h1", { class: "page-title" }, "Settings"),
        el("div", { class: "page-subtitle" }, "Preferences are stored locally in this browser."),
      ]),
      statusBadge,
    ]),
    el("div", { class: "grid grid-2" }, [
      el("div", { class: "card stack" }, [
        el("div", { class: "card-title" }, "Appearance"),
        field("Theme", themeSelect),
      ]),
      el("div", { class: "card stack" }, [
        el("div", { class: "card-title" }, "Capture"),
        field("Camera Selection", cameraInput),
      ]),
      el("div", { class: "card stack" }, [
        el("div", { class: "card-title" }, "Thresholds"),
        field("Confidence Threshold (0-1)", confidenceInput),
        field("Alert Threshold (0-1)", alertInput),
      ]),
      el("div", { class: "card stack" }, [
        el("div", { class: "card-title" }, "Backend"),
        field("Prediction Backend", backendSelect),
        field("API Base URL", apiBaseInput),
        el("div", { class: "row" }, [loggingCheckbox, el("span", { style: "font-size:var(--fs-sm)" }, "Enable client-side logging")]),
      ]),
    ]),
    el("div", { style: "margin-top:var(--space-4)" }, [saveButton]),
  ]);

  mount(container, page);
}
