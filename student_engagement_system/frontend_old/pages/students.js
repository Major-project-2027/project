/**
 * Phase 8 Dashboard -- Students page: searchable, sortable, filterable
 * table of every student's latest recorded snapshot.
 * Sourced from GET /dashboard/students.
 */
import { el, mount } from "../utils/dom.js";
import { createDataTable } from "../components/dataTable.js";
import { api } from "../services/api.js";
import { capitalize, formatTime, formatScore, levelTone } from "../utils/format.js";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "offline", label: "Offline" },
];

export async function renderStudents(container) {
  let search = "";
  let status = "";
  let sortBy = "student_id";

  async function draw() {
    const { students, count } = await api.getStudents({ search, status, sortBy });

    const table = createDataTable({
      columns: [
        { key: "student_id", label: "Student ID" },
        {
          key: "attendance",
          label: "Attendance",
          render: (row) => badge(row.attendance ? "Present" : "Absent", row.attendance ? "success" : "danger"),
        },
        { key: "last_emotion", label: "Last Emotion", render: (row) => capitalize(row.last_emotion) || "--" },
        {
          key: "engagement_score",
          label: "Engagement",
          render: (row) => `${formatScore(row.engagement_score)} (${capitalize(row.engagement_level) || "--"})`,
        },
        {
          key: "cognitive_state",
          label: "Cognitive State",
          render: (row) => badge(capitalize(row.cognitive_state) || "Unknown", levelTone(row.cognitive_state)),
        },
        { key: "last_seen", label: "Last Login", render: (row) => formatTime(row.last_seen) },
        {
          key: "status",
          label: "Status",
          render: (row) => badge(capitalize(row.status), row.status === "active" ? "success" : "neutral"),
        },
      ],
      rows: students,
      initialSortKey: sortBy,
      onSort: (key) => {
        sortBy = key;
        draw();
      },
    });

    const page = el("div", {}, [
      el("div", { class: "page-header" }, [
        el("div", {}, [
          el("h1", { class: "page-title" }, "Students"),
          el("div", { class: "page-subtitle" }, `${count} student${count === 1 ? "" : "s"} recorded.`),
        ]),
        el("div", { class: "row" }, [
          el("input", {
            class: "input",
            placeholder: "Search by student ID...",
            value: search,
            onInput: (event) => {
              search = event.target.value;
              draw();
            },
          }),
          el(
            "select",
            {
              class: "select",
              onChange: (event) => {
                status = event.target.value;
                draw();
              },
            },
            STATUS_OPTIONS.map((opt) => el("option", { value: opt.value }, opt.label))
          ),
        ]),
      ]),
      el("div", { class: "card" }, [table]),
    ]);

    mount(container, page);
  }

  await draw();
}

function badge(text, tone) {
  return el("span", { class: `badge badge-${tone}` }, text);
}
