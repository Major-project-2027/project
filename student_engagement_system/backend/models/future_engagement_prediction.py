from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey

try:
    from database.base import Base
except ModuleNotFoundError:
    from backend.database.base import Base


class FutureEngagementPrediction(Base):
    """The latest cross-session HISTORICAL/FUTURE engagement prediction for
    one student (one row per student_id, upserted).

    This is a DIFFERENT feature from engagement_records/the live LSTM in
    services/engagement_prediction_service.py's predict(): that one
    forecasts a few seconds ahead *within* one live session from per-frame
    data. This table instead persists the output of that same service's
    get_future_prediction(), which forecasts a student's *next* class from
    their own COMPLETED sessions' engagement + alert history only -- never
    the current live session. Persisted here so the prediction survives a
    student leaving a live class, and so repeated dashboard reads don't
    re-run inference (see get_future_prediction's staleness check for when
    it actually recomputes).
    """

    __tablename__ = "future_engagement_predictions"

    id = Column(Integer, primary_key=True, index=True)

    student_id = Column(
        Integer,
        ForeignKey("students.student_id"),
        nullable=False,
        unique=True,
    )

    # One of: "insufficient_data" | "ready" | "unavailable" | "error"
    # (see EngagementPredictionService.get_future_prediction).
    status = Column(String(30), nullable=False)

    # Only set when status == "ready" -- never a fabricated number for any
    # other status.
    prediction_score = Column(Float, nullable=True)

    historical_sessions_used = Column(Integer, nullable=False, default=0)

    # Model-file identity marker (path + mtime) at the time this row was
    # computed -- lets get_future_prediction() detect "the trained model
    # changed since this row was cached" and recompute, without needing a
    # manually-bumped version string.
    model_version = Column(String(80), nullable=True)

    reason = Column(String(255), nullable=True)

    generated_at = Column(DateTime(timezone=True), nullable=True)
