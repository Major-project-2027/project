/**
 * Phase 8 Dashboard -- reusable, sortable data table.
 * columns: [{ key, label, render? }]
 * rows: array of plain objects
 */
import { el, clear } from "../utils/dom.js";

export function createDataTable({ columns, rows, initialSortKey = null, onSort = null }) {
  let sortKey = initialSortKey;
  let sortAsc = true;

  const wrap = el("div", { class: "table-wrap" });
  const table = el("table", { class: "data-table" });
  wrap.appendChild(table);

  function sortedRows() {
    if (!sortKey) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (av === bv) return 0;
      if (av === null || av === undefined) return 1;
      if (bv === null || bv === undefined) return -1;
      return (av > bv ? 1 : -1) * (sortAsc ? 1 : -1);
    });
    return copy;
  }

  function renderHead() {
    const tr = el("tr");
    columns.forEach((col) => {
      const arrow = sortKey === col.key ? (sortAsc ? " \u2191" : " \u2193") : "";
      tr.appendChild(
        el(
          "th",
          {
            onClick: () => {
              if (onSort) {
                onSort(col.key);
                return;
              }
              if (sortKey === col.key) {
                sortAsc = !sortAsc;
              } else {
                sortKey = col.key;
                sortAsc = true;
              }
              render();
            },
          },
          `${col.label}${arrow}`
        )
      );
    });
    return el("thead", {}, [tr]);
  }

  function renderBody() {
    const tbody = el("tbody");
    sortedRows().forEach((row) => {
      const tr = el("tr");
      columns.forEach((col) => {
        const content = col.render ? col.render(row) : String(row[col.key] ?? "--");
        const td = el("td");
        if (content instanceof Node) {
          td.appendChild(content);
        } else {
          td.textContent = content;
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    if (rows.length === 0) {
      const tr = el("tr");
      const td = el("td", { colspan: String(columns.length) }, "No rows to display.");
      td.style.color = "var(--text-muted)";
      td.style.textAlign = "center";
      td.style.padding = "24px";
      tr.appendChild(td);
      tbody.appendChild(tr);
    }
    return tbody;
  }

  function render() {
    clear(table);
    table.appendChild(renderHead());
    table.appendChild(renderBody());
  }

  render();
  return wrap;
}
