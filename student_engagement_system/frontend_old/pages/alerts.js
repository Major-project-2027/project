/**
 * Phase 8 Dashboard -- Alerts page: high distraction, low attention, phone
 * detected, multiple people, unknown face, fatigue detected, and full risk
 * history. Sourced from GET /dashboard/alerts.
 */
import { el, mount } from "../utils/dom.js";
import { createDataTable } from "../components/dataTable.js";
import { api } from "../services/api.js";
import { capitalize, formatDateTime, severityTone } from "../utils/format.js";

const FLAG_OPTIONS = [
  { value: "", label: "All alert types" },
  { value: "HIGH_DISTRACTION", label: "High Distraction" },
  { value: "LOW_ATTENTION", label: "Low Attention" },
  { value: "PHONE_USAGE", label: "Phone Detected" },
  { value: "MULTIPLE_PERSON", label: "Multiple People" },
  { value: "UNKNOWN_FACE", label: "Unknown Face" },
  { value: "FATIGUE_DETECTED", label: "Fatigue Detected" },
];

const RANGE_OPTIONS = [
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
  { value: "all", label: "All time" },
];

export async function renderAlerts(container) {
  let range = "today";
  let flag = "";

  async function draw() {
    const { alerts, count } = await api.getAlerts(range, flag);

    const table = createDataTable({
      columns: [
        { key: "timestamp", label: "Time", render: (row) => formatDateTime(row.timestamp) },
        { key: "student_id", label: "Student ID" },
        { key: "flag", label: "Alert Type", render: (row) => capitalize(row.flag) },
        {
          key: "severity",
          label: "Severity",
          render: (row) => el("span", { class: `badge badge-${severityTone(row.severity)}` }, capitalize(row.severity)),
        },
        { key: "cognitive_state", label: "Cognitive State", render: (row) => capitalize(row.cognitive_state) || "--" },
      ],
      rows: alerts,
      initialSortKey: "timestamp",
    });

    const page = el("div", {}, [
      el("div", { class: "page-header" }, [
        el("div", {}, [
          el("h1", { class: "page-title" }, "Alerts"),
          el("div", { class: "page-subtitle" }, `${count} alert${count === 1 ? "" : "s"} in range.`),
        ]),
        el("div", { class: "row" }, [
          el(
            "select",
            {
              class: "select",
              onChange: (event) => {
                flag = event.target.value;
                draw();
              },
            },
            FLAG_OPTIONS.map((opt) => el("option", { value: opt.value }, opt.label))
          ),
          el(
            "select",
            {
              class: "select",
              onChange: (event) => {
                range = event.target.value;
                draw();
              },
            },
            RANGE_OPTIONS.map((opt) => el("option", { value: opt.value, selected: opt.value === range ? "selected" : null }, opt.label))
          ),
        ]),
      ]),
      el("div", { class: "card" }, [table]),
    ]);

    mount(container, page);
  }

  await draw();
}
