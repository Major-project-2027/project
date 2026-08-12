/**
 * Phase 8 Dashboard -- Dashboard Home page: live camera preview
 * placeholder, current student snapshot, and the eight top-line stat
 * cards, all sourced from GET /dashboard/summary and GET /dashboard/students.
 */
import { el, clear, mount } from "../utils/dom.js";
import { createStatCard } from "../components/statCard.js";
import { icons } from "../assets/icons.js";
import { api } from "../services/api.js";
import { usePolling } from "../hooks/usePolling.js";
import { formatPercent, formatScore, formatTime, capitalize, levelTone } from "../utils/format.js";

let stopPolling = null;

export async function renderDashboardHome(container) {
  if (stopPolling) stopPolling();

  const summary = await api.getSummary("today");
  const studentsResp = await api.getStudents({ sortBy: "last_seen" });
  const current = studentsResp.students[studentsResp.students.length - 1] || null;

  const page = el("div", {}, [
    el("div", { class: "page-header" }, [
      el("div", {}, [
        el("h1", { class: "page-title" }, "Dashboard"),
        el("div", { class: "page-subtitle" }, "Live session overview across every connected classroom stream."),
      ]),
    ]),
    el("div", { class: "grid grid-2", style: "margin-bottom:var(--space-4)" }, [
      renderCameraCard(current),
      renderCurrentStateCard(current),
    ]),
    el("div", { class: "grid grid-stats" }, [
      createStatCard({ label: "Today's Attendance", value: summary.today_attendance, icon: icons.users }),
      createStatCard({ label: "Average Engagement", value: formatPercent(summary.average_engagement), icon: icons.spark }),
      createStatCard({ label: "Average Attention", value: formatPercent(summary.average_attention), icon: icons.eye }),
      createStatCard({ label: "Average Confidence", value: formatPercent(summary.average_confidence * 100), icon: icons.check }),
      createStatCard({ label: "Alerts Generated", value: summary.alerts_generated, icon: icons.bell }),
      createStatCard({ label: "Distraction Count", value: summary.distraction_count, icon: icons.alert }),
      createStatCard({ label: "Phone Detections", value: summary.phone_detections, icon: icons.phone }),
      createStatCard({ label: "Fatigue Detections", value: summary.fatigue_detections, icon: icons.moon }),
    ]),
  ]);

  mount(container, page);

  stopPolling = usePolling(async () => {
    const nextSummary = await api.getSummary("today");
    const nextStudents = await api.getStudents({ sortBy: "last_seen" });
    const nextCurrent = nextStudents.students[nextStudents.students.length - 1] || null;
    if (!container.isConnected) {
      stopPolling();
      return;
    }
    const refreshed = el("div", {}, [
      el("div", { class: "page-header" }, [
        el("div", {}, [
          el("h1", { class: "page-title" }, "Dashboard"),
          el("div", { class: "page-subtitle" }, "Live session overview across every connected classroom stream."),
        ]),
      ]),
      el("div", { class: "grid grid-2", style: "margin-bottom:var(--space-4)" }, [
        renderCameraCard(nextCurrent),
        renderCurrentStateCard(nextCurrent),
      ]),
      el("div", { class: "grid grid-stats" }, [
        createStatCard({ label: "Today's Attendance", value: nextSummary.today_attendance, icon: icons.users }),
        createStatCard({ label: "Average Engagement", value: formatPercent(nextSummary.average_engagement), icon: icons.spark }),
        createStatCard({ label: "Average Attention", value: formatPercent(nextSummary.average_attention), icon: icons.eye }),
        createStatCard({ label: "Average Confidence", value: formatPercent(nextSummary.average_confidence * 100), icon: icons.check }),
        createStatCard({ label: "Alerts Generated", value: nextSummary.alerts_generated, icon: icons.bell }),
        createStatCard({ label: "Distraction Count", value: nextSummary.distraction_count, icon: icons.alert }),
        createStatCard({ label: "Phone Detections", value: nextSummary.phone_detections, icon: icons.phone }),
        createStatCard({ label: "Fatigue Detections", value: nextSummary.fatigue_detections, icon: icons.moon }),
      ]),
    ]);
    clear(container);
    container.appendChild(refreshed);
  }, 8000);
}

function renderCameraCard(current) {
  return el("div", { class: "card" }, [
    el("div", { class: "card-title" }, "Live Camera Preview"),
    el("div", { class: "camera-preview" }, [
      el("span", { style: "width:32px;height:32px", html: icons.camera }),
      el("span", {}, current ? `Streaming -- ${current.student_id}` : "No active stream"),
    ]),
  ]);
}

function renderCurrentStateCard(current) {
  if (!current) {
    return el("div", { class: "card" }, [
      el("div", { class: "card-title" }, "Current Student"),
      el("div", { style: "color:var(--text-muted)" }, "No student authenticated yet."),
    ]);
  }
  const rows = [
    ["Authenticated Student", current.student_id],
    ["Attendance", current.attendance ? "Present" : "Absent"],
    ["Current Emotion", capitalize(current.last_emotion)],
    ["Current Engagement", `${capitalize(current.engagement_level)} (${formatScore(current.engagement_score)})`],
    ["Current Cognitive State", capitalize(current.cognitive_state)],
    ["Last Seen", formatTime(current.last_seen)],
  ];
  return el("div", { class: "card" }, [
    el("div", { class: "card-title" }, "Current Student"),
    el(
      "div",
      { class: "stack", style: "gap:8px" },
      rows.map(([label, value]) =>
        el("div", { class: "row-between" }, [
          el("span", { style: "color:var(--text-secondary);font-size:var(--fs-sm)" }, label),
          el("span", { class: `badge badge-${levelTone(value)}` }, String(value)),
        ])
      )
    ),
  ]);
}
