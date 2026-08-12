/**
 * Phase 8 Dashboard -- Analytics page: emotion/engagement/cognitive
 * timelines, attention & fatigue trends, phone/multiple-people/attendance
 * history, and risk-flag frequency. Every chart is sourced from
 * GET /dashboard/timeline/{metric}.
 */
import { el, mount } from "../utils/dom.js";
import { api } from "../services/api.js";
import { renderLineChart } from "../charts/lineChart.js";
import { renderBarChart } from "../charts/barChart.js";
import { renderDonut } from "../charts/donutChart.js";
import { capitalize } from "../utils/format.js";

const RANGE_OPTIONS = [
  { value: "today", label: "Today" },
  { value: "week", label: "This week" },
  { value: "month", label: "This month" },
  { value: "all", label: "All time" },
];

function sumCategoryCounts(points) {
  const totals = {};
  points.forEach((point) => {
    Object.entries(point.counts || {}).forEach(([label, count]) => {
      totals[label] = (totals[label] || 0) + count;
    });
  });
  return totals;
}

async function loadCharts(range) {
  const [emotion, engagement, cognitive, attention, fatigue, phone, multi, attendance, riskFlags] = await Promise.all([
    api.getTimeline("emotion", range),
    api.getTimeline("engagement", range),
    api.getTimeline("cognitive", range),
    api.getTimeline("attention", range),
    api.getTimeline("fatigue", range),
    api.getTimeline("phone_detection", range),
    api.getTimeline("multiple_people", range),
    api.getTimeline("attendance", range),
    api.getTimeline("risk_flags", range),
  ]);
  return { emotion, engagement, cognitive, attention, fatigue, phone, multi, attendance, riskFlags };
}

function chartCard(title, chartEl) {
  return el("div", { class: "card" }, [el("div", { class: "card-title" }, title), chartEl]);
}

export async function renderAnalytics(container) {
  let range = "today";

  async function draw() {
    const data = await loadCharts(range);

    const riskTotals = sumCategoryCounts(data.riskFlags.points);
    const riskEntries = Object.entries(riskTotals).map(([label, value]) => ({ label: capitalize(label), value }));

    const page = el("div", {}, [
      el("div", { class: "page-header" }, [
        el("div", {}, [
          el("h1", { class: "page-title" }, "Analytics"),
          el("div", { class: "page-subtitle" }, "Trends across every monitored cognitive and engagement signal."),
        ]),
        el(
          "select",
          {
            class: "select",
            onChange: (event) => {
              range = event.target.value;
              draw();
            },
          },
          RANGE_OPTIONS.map((opt) =>
            el("option", { value: opt.value, selected: opt.value === range ? "selected" : null }, opt.label)
          )
        ),
      ]),
      el("div", { class: "grid grid-2" }, [
        chartCard("Engagement Timeline", renderLineChart(data.engagement.points, { color: "var(--accent)", label: "engagement" })),
        chartCard("Attention Trend", renderLineChart(data.attention.points, { color: "var(--success)", label: "attention" })),
        chartCard("Fatigue Trend", renderLineChart(data.fatigue.points, { color: "var(--warning)", label: "fatigue" })),
        chartCard("Attendance History", renderLineChart(data.attendance.points, { color: "var(--info)", label: "attendance" })),
        chartCard("Phone Detection History", renderLineChart(data.phone.points, { color: "var(--danger)", label: "phone detection" })),
        chartCard("Multiple People History", renderLineChart(data.multi.points, { color: "var(--danger)", label: "multiple people" })),
        chartCard("Emotion Timeline", renderDonut(sumCategoryCounts(data.emotion.points))),
        chartCard("Cognitive State Timeline", renderDonut(sumCategoryCounts(data.cognitive.points))),
      ]),
      chartCard("Risk Flag Frequency", renderBarChart(riskEntries, { color: "var(--danger)" })),
    ]);

    mount(container, page);
  }

  await draw();
}
