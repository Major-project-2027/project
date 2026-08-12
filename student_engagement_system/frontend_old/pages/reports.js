/**
 * Phase 8 Dashboard -- Reports page: daily / weekly / monthly / student /
 * class reports, CSV export, and a PDF export placeholder.
 * Sourced from GET /dashboard/reports/{period} and
 * GET /dashboard/reports/export/csv.
 */
import { el, mount } from "../utils/dom.js";
import { api } from "../services/api.js";
import { showToast } from "../components/toast.js";
import { showDialog } from "../components/dialog.js";
import { formatPercent, formatDurationMinutes } from "../utils/format.js";

const PERIODS = [
  { value: "daily", label: "Daily Report" },
  { value: "weekly", label: "Weekly Report" },
  { value: "monthly", label: "Monthly Report" },
  { value: "student", label: "Student Report" },
  { value: "class", label: "Class Report" },
];

export async function renderReports(container) {
  let period = "daily";
  let studentId = "";

  async function draw() {
    let report = null;
    let errorMessage = "";
    try {
      report = await api.getReport(period, period === "student" ? studentId : "");
    } catch (err) {
      errorMessage = err.message;
    }

    const page = el("div", {}, [
      el("div", { class: "page-header" }, [
        el("div", {}, [
          el("h1", { class: "page-title" }, "Reports"),
          el("div", { class: "page-subtitle" }, "Attendance, engagement, and alert summaries by period."),
        ]),
      ]),
      el("div", { class: "card", style: "margin-bottom:var(--space-4)" }, [
        el("div", { class: "row", style: "flex-wrap:wrap" }, [
          el(
            "select",
            {
              class: "select",
              onChange: (event) => {
                period = event.target.value;
                draw();
              },
            },
            PERIODS.map((opt) => el("option", { value: opt.value, selected: opt.value === period ? "selected" : null }, opt.label))
          ),
          period === "student"
            ? el("input", {
                class: "input",
                placeholder: "Student ID (e.g. 22CS001)",
                value: studentId,
                onInput: (event) => {
                  studentId = event.target.value;
                },
              })
            : null,
          period === "student" ? el("button", { class: "btn", onClick: () => draw() }, "Load") : null,
          el("span", { style: "flex:1" }),
          el(
            "button",
            {
              class: "btn btn-primary",
              onClick: () => {
                window.open(api.exportCsvUrl("all"), "_blank");
                showToast("CSV export started", "success");
              },
            },
            "Export CSV"
          ),
          el(
            "button",
            {
              class: "btn",
              onClick: () =>
                showDialog({
                  title: "PDF Export",
                  body: "PDF export is a placeholder in Phase 8 -- wiring a PDF renderer to this same report payload is a drop-in addition for a later phase.",
                  actions: [{ label: "Got it", primary: true }],
                }),
            },
            "Export PDF"
          ),
        ]),
      ]),
      errorMessage ? el("div", { class: "card" }, `Could not load report: ${errorMessage}`) : renderReportBody(report),
    ]);

    mount(container, page);
  }

  await draw();
}

function renderReportBody(report) {
  if (!report) return el("div", { class: "card" }, "No report data available.");
  const s = report.summary;
  const rows = [
    ["Period", report.period],
    ["Students Covered", report.student_count],
    ["Events Recorded", report.event_count],
    ["Today's Attendance", s.today_attendance],
    ["Average Engagement", formatPercent(s.average_engagement)],
    ["Average Attention", formatPercent(s.average_attention)],
    ["Average Confidence", formatPercent(s.average_confidence * 100)],
    ["Alerts Generated", s.alerts_generated],
    ["Phone Detections", s.phone_detections],
    ["Fatigue Detections", s.fatigue_detections],
  ];

  const durationRows = Object.entries(report.session_duration_minutes || {}).map(([sid, minutes]) =>
    el("div", { class: "row-between" }, [
      el("span", { style: "color:var(--text-secondary)" }, sid),
      el("span", {}, formatDurationMinutes(minutes)),
    ])
  );

  return el("div", { class: "grid grid-2" }, [
    el("div", { class: "card" }, [
      el("div", { class: "card-title" }, "Summary"),
      el(
        "div",
        { class: "stack", style: "gap:8px" },
        rows.map(([label, value]) =>
          el("div", { class: "row-between" }, [
            el("span", { style: "color:var(--text-secondary);font-size:var(--fs-sm)" }, label),
            el("span", {}, String(value)),
          ])
        )
      ),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card-title" }, "Session Duration"),
      durationRows.length
        ? el("div", { class: "stack", style: "gap:8px" }, durationRows)
        : el("div", { style: "color:var(--text-muted)" }, "No sessions recorded for this period."),
    ]),
  ]);
}
