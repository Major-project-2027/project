/**
 * Phase 8 Dashboard -- tiny DOM helpers. No framework: every page and
 * component is built with these three functions plus native DOM APIs.
 */
export function qs(selector, scope = document) {
  return scope.querySelector(selector);
}

export function qsa(selector, scope = document) {
  return Array.from(scope.querySelectorAll(selector));
}

/**
 * Create an element with attributes/props and children in one call.
 *   el("div", { class: "card", onClick: fn }, [el("span", {}, "hi")])
 */
export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);

  Object.entries(props || {}).forEach(([key, value]) => {
    if (value === null || value === undefined || value === false) return;
    if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "class") {
      node.className = value;
    } else if (key === "html") {
      node.innerHTML = value;
    } else if (key === "dataset") {
      Object.entries(value).forEach(([dk, dv]) => (node.dataset[dk] = dv));
    } else {
      node.setAttribute(key, value);
    }
  });

  const list = Array.isArray(children) ? children : [children];
  list.forEach((child) => {
    if (child === null || child === undefined || child === false) return;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  });

  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

export function mount(container, node) {
  clear(container);
  container.appendChild(node);
  return node;
}
