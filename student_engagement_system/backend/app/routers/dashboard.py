"""
Dashboard & Analytics router.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ml_models.dashboard_analytics.analytics_store import get_analytics_store
from ml_models.dashboard_analytics.dashboard_schemas import (
    DashboardEvent,
    DashboardFeatureError,
    DashboardQuery,
)
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["dashboard-analytics"])


class DashboardEventRequest(BaseModel):
    student_id: str = Field(..., description="Unique student identifier.")
    timestamp: Optional[str] = None
    session_id: Optional[str] = None
    attendance: bool = True
    emotion: Optional[str] = None
    emotion_confidence: float = 0.0
    cognitive_state: Optional[str] = None
    attention_score: float = 0.0
    attention_level: Optional[str] = None
    distraction_score: float = 0.0
    fatigue_score: float = 0.0
    confusion_score: float = 0.0
    engagement_score: float = 0.0
    engagement_level: Optional[str] = None
    head_pose: Optional[str] = None
    gaze: Optional[str] = None
    multiple_person: bool = False
    phone_detected: bool = False
    overall_confidence: float = 0.0
    risk_flags: List[str] = Field(default_factory=list)
    fps: float = 0.0


@router.post("/dashboard/events")
def record_event(request: DashboardEventRequest) -> Dict[str, Any]:
    """Record one dashboard event snapshot (typically forwarded from Phase
    7's `/cognitive/predict` response) into the append-only analytics log."""
    try:
        event = DashboardEvent.from_dict(request.model_dump())
    except DashboardFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store = get_analytics_store()
    store.append_event(event)
    return {"status": "recorded", "student_id": event.student_id, "timestamp": event.timestamp}


@router.get("/dashboard/summary")
def get_summary(range: str = Query("today", description="today|week|month|all")) -> Dict[str, Any]:
    """Return the stat-card numbers for the Dashboard Home page."""
    try:
        query = DashboardQuery.from_params(range_=range)
    except DashboardFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store = get_analytics_store()
    return store.compute_summary(range_=query.range_)


@router.get("/dashboard/timeline/{metric}")
def get_timeline(metric: str, range: str = Query("today")) -> Dict[str, Any]:
    """Return a bucketed timeline for one Analytics-page metric (emotion,
    engagement, cognitive, attention, fatigue, phone_detection,
    multiple_people, attendance, risk_flags)."""
    try:
        query = DashboardQuery.from_params(range_=range, metric=metric)
    except DashboardFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store = get_analytics_store()
    return {"metric": metric, "range": query.range_, "points": store.compute_timeline(metric, range_=query.range_)}


@router.get("/dashboard/students")
def get_students(
    search: Optional[str] = Query(None, description="Filter by student_id substring."),
    sort_by: str = Query("student_id", description="student_id|engagement_score|last_seen"),
    status: Optional[str] = Query(None, description="active|offline"),
) -> Dict[str, Any]:
    """Return the Students-page table: search, sort, and filter over each
    student's latest recorded snapshot."""
    store = get_analytics_store()
    rows = store.compute_student_table()

    if search:
        rows = [r for r in rows if search.lower() in r["student_id"].lower()]
    if status:
        rows = [r for r in rows if r["status"] == status]

    valid_sort_keys = {"student_id", "engagement_score", "last_seen"}
    if sort_by not in valid_sort_keys:
        raise HTTPException(status_code=422, detail=f"'sort_by' must be one of {sorted(valid_sort_keys)}.")
    rows = sorted(rows, key=lambda r: (r[sort_by] is None, r[sort_by]))

    return {"count": len(rows), "students": rows}


@router.get("/dashboard/alerts")
def get_alerts(
    range: str = Query("today"),
    flag: Optional[str] = Query(None, description="Filter by a single risk-flag name."),
) -> Dict[str, Any]:
    """Return the Alerts-page risk-flag history."""
    try:
        query = DashboardQuery.from_params(range_=range)
    except DashboardFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store = get_analytics_store()
    alerts = store.compute_alerts(range_=query.range_, flag=flag)
    return {"count": len(alerts), "alerts": alerts}


@router.get("/dashboard/reports/{period}")
def get_report(period: str, student_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Return a daily / weekly / monthly / student / class report."""
    try:
        query = DashboardQuery.from_params(period=period)
    except DashboardFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if period in ("student",) and not student_id:
        raise HTTPException(status_code=422, detail="'student_id' is required for a student report.")
    store = get_analytics_store()
    return store.compute_report(query.period, student_id=student_id)


@router.get("/dashboard/reports/export/csv")
def export_report_csv(range: str = Query("all")) -> StreamingResponse:
    """Stream a CSV export of every recorded event in the given range (the
    Reports page's 'CSV export' action). A PDF export placeholder is served
    by the frontend Reports page (`frontend/pages/reports.js`) directly."""
    try:
        query = DashboardQuery.from_params(range_=range)
    except DashboardFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    store = get_analytics_store()
    csv_text = store.export_csv(range_=query.range_)
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dashboard_export.csv"},
    )


@router.get("/dashboard/config")
def get_dashboard_config() -> Dict[str, Any]:
    """Return the currently loaded dashboard configuration (retention,
    default range, timeline bucket size, alert thresholds, theme)."""
    store = get_analytics_store()
    return store.get_config()


@router.get("/dashboard/health")
def dashboard_health() -> Dict[str, Any]:
    """Report whether the dashboard analytics store is available and how
    many events it currently holds."""
    store = get_analytics_store()
    event_count = store.compute_summary(range_="all")["event_count"]
    return {"status": "ok", "events_recorded": event_count}
