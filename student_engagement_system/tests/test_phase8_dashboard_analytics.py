"""
Phase 8 -- Dashboard & Analytics test suite.
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml_models.dashboard_analytics.dashboard_schemas import (  # noqa: E402
    DashboardEvent,
    DashboardFeatureError,
    DashboardQuery,
)
from ml_models.dashboard_analytics.analytics_store import (  # noqa: E402
    DashboardAnalyticsStore,
    get_analytics_store,
    reset_analytics_store,
)


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    reset_analytics_store()
    store = DashboardAnalyticsStore(tmp_path)
    yield store
    reset_analytics_store()


# -- DashboardEvent / DashboardQuery -----------------------------------------------
def test_event_from_dict_valid():
    event = DashboardEvent.from_dict({"student_id": "22CS001", "engagement_score": 80.0})
    assert event.student_id == "22CS001"
    assert event.engagement_score == 80.0
    assert event.timestamp  # auto-populated


def test_event_from_dict_missing_student_id():
    with pytest.raises(DashboardFeatureError):
        DashboardEvent.from_dict({"engagement_score": 80.0})


def test_event_from_dict_bad_types():
    with pytest.raises(DashboardFeatureError):
        DashboardEvent.from_dict({"student_id": "22CS001", "engagement_score": "not-a-number"})


def test_query_from_params_valid():
    q = DashboardQuery.from_params(range_="week", metric="engagement", period="daily")
    assert q.range_ == "week"


def test_query_from_params_invalid_range():
    with pytest.raises(DashboardFeatureError):
        DashboardQuery.from_params(range_="decade")


def test_query_from_params_invalid_metric():
    with pytest.raises(DashboardFeatureError):
        DashboardQuery.from_params(metric="not_a_metric")


# -- DashboardAnalyticsStore ---------------------------------------------------------
def test_append_and_read(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "engagement_score": 50}))
    events = tmp_store._read_events()
    assert len(events) == 1
    assert events[0]["student_id"] == "S1"


def test_compute_summary_empty(tmp_store):
    summary = tmp_store.compute_summary("all")
    assert summary["event_count"] == 0
    assert summary["today_attendance"] == 0


def test_compute_summary_with_events(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({
        "student_id": "S1", "engagement_score": 80, "attention_score": 70,
        "overall_confidence": 0.9, "attendance": True, "risk_flags": [],
    }))
    tmp_store.append_event(DashboardEvent.from_dict({
        "student_id": "S2", "engagement_score": 20, "attention_score": 30,
        "overall_confidence": 0.6, "phone_detected": True, "attendance": True,
        "risk_flags": ["PHONE_USAGE", "FATIGUE_DETECTED"],
    }))
    summary = tmp_store.compute_summary("all")
    assert summary["event_count"] == 2
    assert summary["today_attendance"] == 2
    assert summary["phone_detections"] == 1
    assert summary["fatigue_detections"] == 1
    assert summary["alerts_generated"] == 2


def test_compute_timeline_numeric_metric(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "engagement_score": 40}))
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "engagement_score": 60}))
    points = tmp_store.compute_timeline("engagement", "all")
    assert len(points) >= 1
    assert "value" in points[0]


def test_compute_timeline_category_metric(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "emotion": "happy"}))
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "emotion": "sad"}))
    points = tmp_store.compute_timeline("emotion", "all")
    assert "counts" in points[0]


def test_compute_timeline_invalid_metric_raises(tmp_store):
    from ml_models.dashboard_analytics.analytics_store import DashboardAnalyticsError
    with pytest.raises(DashboardAnalyticsError):
        tmp_store.compute_timeline("not_a_metric", "all")


def test_compute_student_table(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "emotion": "happy"}))
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S2", "emotion": "tired"}))
    table = tmp_store.compute_student_table()
    assert len(table) == 2
    assert {row["student_id"] for row in table} == {"S1", "S2"}


def test_compute_alerts_filters_by_flag(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "risk_flags": ["PHONE_USAGE"]}))
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "risk_flags": ["FATIGUE_DETECTED"]}))
    all_alerts = tmp_store.compute_alerts("all")
    assert len(all_alerts) == 2
    phone_only = tmp_store.compute_alerts("all", flag="PHONE_USAGE")
    assert len(phone_only) == 1
    assert phone_only[0]["flag"] == "PHONE_USAGE"


def test_compute_report_daily(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "engagement_score": 55}))
    report = tmp_store.compute_report("daily")
    assert report["period"] == "daily"
    assert report["student_count"] == 1


def test_export_csv_contains_header_and_rows(tmp_store):
    tmp_store.append_event(DashboardEvent.from_dict({"student_id": "S1", "engagement_score": 55}))
    csv_text = tmp_store.export_csv("all")
    assert "student_id" in csv_text.splitlines()[0]
    assert "S1" in csv_text


def test_singleton_pattern(tmp_path):
    reset_analytics_store()
    store_a = get_analytics_store(tmp_path)
    store_b = get_analytics_store(tmp_path)
    assert store_a is store_b
    reset_analytics_store()


# -- FastAPI router --------------------------------------------------------------------
@pytest.fixture
def client():
    reset_analytics_store()
    from backend.app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_router_record_and_summary(client):
    resp = client.post("/dashboard/events", json={"student_id": "R1", "engagement_score": 66, "attention_score": 71, "overall_confidence": 0.8})
    assert resp.status_code == 200
    summary_resp = client.get("/dashboard/summary?range=all")
    assert summary_resp.status_code == 200
    assert summary_resp.json()["event_count"] >= 1


def test_router_record_missing_student_id(client):
    resp = client.post("/dashboard/events", json={"engagement_score": 66})
    assert resp.status_code == 422


def test_router_all_timeline_metrics(client):
    client.post("/dashboard/events", json={"student_id": "R2", "emotion": "happy", "engagement_score": 70, "risk_flags": ["LOW_ATTENTION"]})
    for metric in ("emotion", "engagement", "cognitive", "attention", "fatigue",
                   "phone_detection", "multiple_people", "attendance", "risk_flags"):
        resp = client.get(f"/dashboard/timeline/{metric}?range=all")
        assert resp.status_code == 200, f"{metric} failed: {resp.text}"
        assert resp.json()["metric"] == metric


def test_router_timeline_invalid_metric(client):
    resp = client.get("/dashboard/timeline/not_a_metric?range=all")
    assert resp.status_code == 422


def test_router_students_search_sort_filter(client):
    client.post("/dashboard/events", json={"student_id": "AAA1", "engagement_score": 90})
    client.post("/dashboard/events", json={"student_id": "BBB2", "engagement_score": 10})
    resp = client.get("/dashboard/students?search=AAA&sort_by=engagement_score")
    assert resp.status_code == 200
    body = resp.json()
    assert all("AAA" in s["student_id"] for s in body["students"])


def test_router_alerts(client):
    client.post("/dashboard/events", json={"student_id": "C1", "risk_flags": ["PHONE_USAGE"]})
    resp = client.get("/dashboard/alerts?range=all")
    assert resp.status_code == 200
    assert resp.json()["count"] >= 1


def test_router_reports_all_periods(client):
    client.post("/dashboard/events", json={"student_id": "D1", "engagement_score": 50})
    for period in ("daily", "weekly", "monthly", "class"):
        resp = client.get(f"/dashboard/reports/{period}")
        assert resp.status_code == 200, resp.text
        assert resp.json()["period"] == period
    resp = client.get("/dashboard/reports/student?student_id=D1")
    assert resp.status_code == 200
    resp = client.get("/dashboard/reports/student")
    assert resp.status_code == 422
    resp = client.get("/dashboard/reports/not_a_period")
    assert resp.status_code == 422


def test_router_export_csv(client):
    client.post("/dashboard/events", json={"student_id": "E1", "engagement_score": 50})
    resp = client.get("/dashboard/reports/export/csv?range=all")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "E1" in resp.text


def test_router_config_and_health(client):
    assert client.get("/dashboard/config").status_code == 200
    health_resp = client.get("/dashboard/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"


# -- main.py registration ------------------------------------------------------------------
def test_main_py_registers_dashboard_router_and_static_mount():
    main_source = (PROJECT_ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    assert "from backend.app.routers import dashboard" in main_source
    assert "app.include_router(dashboard.router)" in main_source
    assert "StaticFiles" in main_source
    assert "/dashboard-ui" in main_source


# -- frontend file presence --------------------------------------------------------------
FRONTEND_REQUIRED_FILES = [
    "frontend/index.html",
    "frontend/main.js",
    "frontend/styles/theme.css",
    "frontend/styles/base.css",
    "frontend/styles/components.css",
    "frontend/utils/format.js",
    "frontend/utils/dom.js",
    "frontend/services/api.js",
    "frontend/hooks/usePolling.js",
    "frontend/charts/lineChart.js",
    "frontend/charts/barChart.js",
    "frontend/charts/donutChart.js",
    "frontend/components/sidebar.js",
    "frontend/components/navbar.js",
    "frontend/components/statCard.js",
    "frontend/components/dataTable.js",
    "frontend/components/toast.js",
    "frontend/components/dialog.js",
    "frontend/components/loadingScreen.js",
    "frontend/components/errorScreen.js",
    "frontend/layouts/appLayout.js",
    "frontend/pages/router.js",
    "frontend/pages/dashboardHome.js",
    "frontend/pages/analytics.js",
    "frontend/pages/reports.js",
    "frontend/pages/students.js",
    "frontend/pages/alerts.js",
    "frontend/pages/settings.js",
    "frontend/assets/icons.js",
]


@pytest.mark.parametrize("relative_path", FRONTEND_REQUIRED_FILES)
def test_frontend_file_exists_and_nonempty(relative_path):
    path = PROJECT_ROOT / relative_path
    assert path.is_file(), f"Missing frontend file: {relative_path}"
    assert path.stat().st_size > 0, f"Frontend file is empty: {relative_path}"
