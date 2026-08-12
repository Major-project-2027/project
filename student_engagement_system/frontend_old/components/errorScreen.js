/**
 * Phase 8 Dashboard -- error screen shown when a page's data fetch fails
 * (e.g. a Phase 2-7 backend is unreachable). Always offers a retry.
 */
import { el } from "../utils/dom.js";
import { icons } from "../assets/icons.js";

export function renderError(message, onRetry = null) {
  return el("div", { class: "screen-center error-screen" }, [
    el("span", { style: "width:28px;height:28px;color:var(--danger)", html: icons.alert }),
    el("div", {}, message || "Something went wrong while loading this page."),
    onRetry ? el("button", { class: "btn btn-primary", onClick: onRetry }, "Retry") : null,
  ]);
}
