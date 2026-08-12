"""
Phase 8 Dashboard & Analytics -- append-only event store and aggregation
engine.

Every dashboard number (stat cards, timelines, student table, alerts,
reports) is derived from the same append-only JSON-Lines event log at
`data/dashboard/events.jsonl`. Nothing here calls or modifies any Phase
2-7 model -- it only stores and aggregates the structured results those
phases already produce (typically via Phase 7's `/cognitive/predict`
response, forwarded into `POST /dashboard/events`).
"""
import csv
import io
import json
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ml_models.dashboard_analytics.dashboard_schemas import DashboardEvent
from utils.common import load_yaml_config
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_RELATIVE_PATH = Path("configs") / "dashboard.yaml"
DEFAULT_EVENTS_RELATIVE_PATH = Path("data") / "dashboard" / "events.jsonl"

_ALERT_SEVERITY = {
    "PHONE_USAGE": "high",
    "MULTIPLE_PERSON": "high",
    "HIGH_DISTRACTION": "high",
    "FATIGUE_DETECTED": "medium",
    "LOOKING_AWAY": "medium",
    "LOW_ATTENTION": "medium",
    "LOW_CONFIDENCE": "low",
    "UNKNOWN_FACE": "high",
    "CONFUSION_DETECTED": "medium",
    "DISENGAGED": "medium",
}


class DashboardAnalyticsError(Exception):
    """Base exception for all Phase 8 dashboard-analytics failures."""


def _parse_ts(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class DashboardAnalyticsStore:
    """Thread-safe append-only event store plus read-side aggregation.

    A future phase could swap the JSON-Lines file for a real database by
    reimplementing just `append_event()` / `_read_events()` behind this
    exact class interface -- every router endpoint keeps working
    unmodified, mirroring the swappable-backend pattern Phase 6/7 already
    use for their scoring engines.
    """

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self._lock = threading.Lock()
        self._config = self._load_config()
        self.events_path = self.project_root / DEFAULT_EVENTS_RELATIVE_PATH
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_path.touch(exist_ok=True)

    def _load_config(self) -> Dict[str, Any]:
        config_path = self.project_root / DEFAULT_CONFIG_RELATIVE_PATH
        try:
            config = load_yaml_config(config_path)
            if isinstance(config, dict) and config:
                return config
        except Exception as exc:  # noqa: BLE001 -- defensive fallback only
            logger.warning(f"Falling back to default dashboard config: {exc}")
        return {
            "retention_days": 90,
            "default_range": "today",
            "timeline_bucket_minutes": 60,
            "alert_thresholds": {"low_attention": 40.0, "high_distraction": 50.0, "fatigue": 60.0},
            "theme": {"default_mode": "dark"},
        }

    def get_config(self) -> Dict[str, Any]:
        return dict(self._config)

    # -- write side ---------------------------------------------------
    def append_event(self, event: DashboardEvent) -> None:
        line = json.dumps(event.as_dict(), default=str)
        with self._lock:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        logger.info(f"Dashboard event recorded for student_id={event.student_id}")

    # -- read side ------------------------------------------------------
    def _read_events(
        self,
        since: Optional[datetime] = None,
        student_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not self.events_path.exists():
            return events
        with self._lock:
            raw_lines = self.events_path.read_text(encoding="utf-8").splitlines()
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if student_id and record.get("student_id") != student_id:
                continue
            if since is not None and _parse_ts(record.get("timestamp", "")) < since:
                continue
            events.append(record)
        return events

    @staticmethod
    def _range_start(range_: str) -> Optional[datetime]:
        now = datetime.now(timezone.utc)
        if range_ == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if range_ == "week":
            return now - timedelta(days=7)
        if range_ == "month":
            return now - timedelta(days=30)
        return None  # "all"

    # -- summary / stat cards --------------------------------------------
    def compute_summary(self, range_: str = "today") -> Dict[str, Any]:
        events = self._read_events(since=self._range_start(range_))
        if not events:
            return {
                "today_attendance": 0,
                "average_engagement": 0.0,
                "average_attention": 0.0,
                "average_confidence": 0.0,
                "alerts_generated": 0,
                "distraction_count": 0,
                "phone_detections": 0,
                "fatigue_detections": 0,
                "event_count": 0,
            }

        distinct_students = {e["student_id"] for e in events if e.get("attendance")}
        engagement_values = [e["engagement_score"] for e in events if e.get("engagement_score") is not None]
        attention_values = [e["attention_score"] for e in events if e.get("attention_score") is not None]
        confidence_values = [e["overall_confidence"] for e in events if e.get("overall_confidence") is not None]

        alerts = [flag for e in events for flag in (e.get("risk_flags") or [])]
        phone_detections = sum(1 for e in events if e.get("phone_detected"))
        fatigue_detections = sum(1 for e in events if "FATIGUE_DETECTED" in (e.get("risk_flags") or []))
        distraction_count = sum(1 for e in events if "HIGH_DISTRACTION" in (e.get("risk_flags") or []))

        return {
            "today_attendance": len(distinct_students),
            "average_engagement": round(sum(engagement_values) / len(engagement_values), 2) if engagement_values else 0.0,
            "average_attention": round(sum(attention_values) / len(attention_values), 2) if attention_values else 0.0,
            "average_confidence": round(sum(confidence_values) / len(confidence_values), 4) if confidence_values else 0.0,
            "alerts_generated": len(alerts),
            "distraction_count": distraction_count,
            "phone_detections": phone_detections,
            "fatigue_detections": fatigue_detections,
            "event_count": len(events),
        }

    # -- timelines --------------------------------------------------------
    def compute_timeline(self, metric: str, range_: str = "today") -> List[Dict[str, Any]]:
        valid_metrics = (
            "emotion", "engagement", "cognitive", "attention", "fatigue",
            "phone_detection", "multiple_people", "attendance", "risk_flags",
        )
        if metric not in valid_metrics:
            raise DashboardAnalyticsError(f"Unsupported timeline metric: {metric!r}")

        events = sorted(
            self._read_events(since=self._range_start(range_)),
            key=lambda e: e.get("timestamp", ""),
        )
        bucket_minutes = int(self._config.get("timeline_bucket_minutes", 60))
        buckets: Dict[str, List[float]] = defaultdict(list)
        bucket_meta: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for record in events:
            ts = _parse_ts(record.get("timestamp", ""))
            epoch_minutes = int(ts.timestamp() // 60)
            bucket_key_minutes = epoch_minutes - (epoch_minutes % bucket_minutes)
            bucket_dt = datetime.fromtimestamp(bucket_key_minutes * 60, tz=timezone.utc)
            bucket_key = bucket_dt.isoformat()

            if metric == "emotion":
                bucket_meta[bucket_key][str(record.get("emotion") or "unknown")] += 1
            elif metric == "engagement":
                buckets[bucket_key].append(float(record.get("engagement_score", 0.0)))
            elif metric == "cognitive":
                bucket_meta[bucket_key][str(record.get("cognitive_state") or "unknown")] += 1
            elif metric == "attention":
                buckets[bucket_key].append(float(record.get("attention_score", 0.0)))
            elif metric == "fatigue":
                buckets[bucket_key].append(float(record.get("fatigue_score", 0.0)))
            elif metric == "phone_detection":
                buckets[bucket_key].append(1.0 if record.get("phone_detected") else 0.0)
            elif metric == "multiple_people":
                buckets[bucket_key].append(1.0 if record.get("multiple_person") else 0.0)
            elif metric == "attendance":
                buckets[bucket_key].append(1.0 if record.get("attendance") else 0.0)
            elif metric == "risk_flags":
                for flag in record.get("risk_flags") or []:
                    bucket_meta[bucket_key][flag] += 1
            else:
                raise DashboardAnalyticsError(f"Unsupported timeline metric: {metric!r}")

        if metric in ("emotion", "cognitive", "risk_flags"):
            return [
                {"timestamp": key, "counts": dict(counts)}
                for key, counts in sorted(bucket_meta.items())
            ]

        return [
            {"timestamp": key, "value": round(sum(values) / len(values), 3) if values else 0.0}
            for key, values in sorted(buckets.items())
        ]

    # -- students table ---------------------------------------------------
    def compute_student_table(self) -> List[Dict[str, Any]]:
        events = self._read_events()
        latest_by_student: Dict[str, Dict[str, Any]] = {}
        for record in events:
            student_id = record.get("student_id")
            if not student_id:
                continue
            existing = latest_by_student.get(student_id)
            if existing is None or record.get("timestamp", "") >= existing.get("timestamp", ""):
                latest_by_student[student_id] = record

        rows = []
        now = datetime.now(timezone.utc)
        for student_id, record in latest_by_student.items():
            last_seen = _parse_ts(record.get("timestamp", ""))
            status = "active" if (now - last_seen) <= timedelta(minutes=10) else "offline"
            rows.append({
                "student_id": student_id,
                "attendance": bool(record.get("attendance", False)),
                "last_emotion": record.get("emotion"),
                "engagement_score": record.get("engagement_score", 0.0),
                "engagement_level": record.get("engagement_level"),
                "cognitive_state": record.get("cognitive_state"),
                "last_seen": record.get("timestamp"),
                "status": status,
            })
        return sorted(rows, key=lambda r: r["student_id"])

    # -- alerts -------------------------------------------------------------
    def compute_alerts(self, range_: str = "today", flag: Optional[str] = None) -> List[Dict[str, Any]]:
        events = self._read_events(since=self._range_start(range_))
        alerts: List[Dict[str, Any]] = []
        for record in events:
            for risk_flag in record.get("risk_flags") or []:
                if flag and risk_flag != flag:
                    continue
                alerts.append({
                    "student_id": record.get("student_id"),
                    "timestamp": record.get("timestamp"),
                    "flag": risk_flag,
                    "severity": _ALERT_SEVERITY.get(risk_flag, "low"),
                    "cognitive_state": record.get("cognitive_state"),
                })
        return sorted(alerts, key=lambda a: a["timestamp"], reverse=True)

    # -- reports --------------------------------------------------------------
    def compute_report(self, period: str, student_id: Optional[str] = None) -> Dict[str, Any]:
        range_map = {"daily": "today", "weekly": "week", "monthly": "month", "student": "all", "class": "all"}
        range_ = range_map.get(period, "all")
        events = self._read_events(since=self._range_start(range_), student_id=student_id)

        durations: Dict[str, List[datetime]] = defaultdict(list)
        for record in events:
            durations[record["student_id"]].append(_parse_ts(record.get("timestamp", "")))

        session_durations = {
            sid: round((max(ts_list) - min(ts_list)).total_seconds() / 60.0, 1)
            for sid, ts_list in durations.items()
        }

        return {
            "period": period,
            "student_id": student_id,
            "summary": self.compute_summary(range_=range_),
            "student_count": len({e["student_id"] for e in events}),
            "session_duration_minutes": session_durations,
            "event_count": len(events),
        }

    def export_csv(self, range_: str = "all") -> str:
        events = self._read_events(since=self._range_start(range_))
        buffer = io.StringIO()
        fieldnames = [
            "timestamp", "student_id", "attendance", "emotion", "cognitive_state",
            "attention_score", "engagement_score", "engagement_level",
            "phone_detected", "multiple_person", "overall_confidence", "risk_flags",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in events:
            row = dict(record)
            row["risk_flags"] = ";".join(record.get("risk_flags") or [])
            writer.writerow(row)
        return buffer.getvalue()


_STORE_SINGLETON: Optional[DashboardAnalyticsStore] = None
_SINGLETON_LOCK = threading.Lock()


def get_analytics_store(project_root: Optional[Path] = None) -> DashboardAnalyticsStore:
    """Return the process-wide `DashboardAnalyticsStore` singleton, creating
    it on first call (mirrors Phase 6/7's `get_*_predictor()` /
    `get_cognitive_monitor()` singleton pattern)."""
    global _STORE_SINGLETON
    with _SINGLETON_LOCK:
        if _STORE_SINGLETON is None:
            if project_root is None:
                # backend/app/routers/dashboard.py -> parents[2] == project root
                project_root = Path(__file__).resolve().parents[2]
            _STORE_SINGLETON = DashboardAnalyticsStore(project_root)
        return _STORE_SINGLETON


def reset_analytics_store() -> None:
    """Test-only helper: forces the next `get_analytics_store()` call to
    build a fresh singleton (used by the pytest suite between cases)."""
    global _STORE_SINGLETON
    with _SINGLETON_LOCK:
        _STORE_SINGLETON = None
