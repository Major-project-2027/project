/**
 * Phase 8 Dashboard -- modal dialog singleton.
 * showDialog({ title, body, actions: [{ label, primary?, onClick }] })
 */
import { el } from "../utils/dom.js";

export function showDialog({ title, body, actions = [{ label: "Close" }] }) {
  const overlay = el("div", { class: "dialog-overlay" });

  const close = () => overlay.remove();

  const actionButtons = actions.map((action) =>
    el(
      "button",
      {
        class: `btn ${action.primary ? "btn-primary" : ""}`,
        onClick: () => {
          if (action.onClick) action.onClick();
          close();
        },
      },
      action.label
    )
  );

  const box = el("div", { class: "dialog-box" }, [
    el("div", { class: "dialog-title" }, title),
    el("div", { class: "dialog-body" }, body),
    el("div", { class: "dialog-actions" }, actionButtons),
  ]);

  overlay.appendChild(box);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });

  document.body.appendChild(overlay);
  return close;
}
