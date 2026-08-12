/**
 * Phase 8 Dashboard -- toast notification singleton.
 * Usage: import { showToast } from "./components/toast.js"; showToast("Saved", "success");
 */
import { el } from "../utils/dom.js";

let stackEl = null;

function ensureStack() {
  if (stackEl && document.body.contains(stackEl)) return stackEl;
  stackEl = el("div", { class: "toast-stack" });
  document.body.appendChild(stackEl);
  return stackEl;
}

export function showToast(message, type = "info", durationMs = 3500) {
  const stack = ensureStack();
  const toast = el("div", { class: `toast toast-${type}` }, message);
  stack.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = "opacity 200ms ease";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 200);
  }, durationMs);
  return toast;
}
