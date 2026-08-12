/**
 * Phase 8 Dashboard -- entry point. Mounts the app shell once the DOM is
 * ready.
 */
import { mountApp } from "./layouts/appLayout.js";

document.addEventListener("DOMContentLoaded", () => {
  mountApp("#app");
});
