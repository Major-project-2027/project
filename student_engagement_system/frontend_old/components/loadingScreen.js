/**
 * Phase 8 Dashboard -- loading screen shown while a page's first fetch is
 * in flight.
 */
import { el } from "../utils/dom.js";

export function renderLoading(message = "Loading...") {
  return el("div", { class: "screen-center" }, [
    el("div", { class: "spinner" }),
    el("div", {}, message),
  ]);
}
