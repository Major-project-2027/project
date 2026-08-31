"""Future-engagement prediction service (LSTM-based, per-student/per-session).

INSPECTION FINDINGS (read this before changing anything here):

This project already has a module called "engagement prediction"
(ml_models/engagement_prediction/engagement_predictor.py, mounted at
POST /engagement/predict in app/routers/engagement_prediction.py), but it
is a DIFFERENT feature: a rule-based, single-moment multimodal SCORER
(combines face/emotion/gaze/head-pose/object-detection readings for one
instant into a 0-100 score). Its own docstring says so explicitly:
"RULE-BASED ONLY... never a trained model", with an LSTM mentioned only as
a hypothetical future Phase 8 backend that was never implemented. It has
no time-series input, no sequence window, and is not wired into the live
/ai/analyze-frame pipeline at all (the frontend never calls it -- the
"LSTM prediction" text previously shown in AIMonitoringPanel.tsx was a
hardcoded client-side ternary on current engagement, not a real model
call).

A project-wide search (file names, `LSTM`/`keras.layers.LSTM` usage,
training notebooks, saved model files) originally found NO trained LSTM
model anywhere in this repository for TEMPORAL engagement forecasting
(predicting a FUTURE score from a sequence of past scores). That gap has
since been filled: ml_models/engagement_prediction/train_lstm.py trains a
real LSTM directly from this project's own engagement_records (no
synthetic data), and MODEL_PATH below is where it saves the result. This
service loads whatever is actually there -- if that file is ever missing
or fails to load, every prediction still honestly reports
status="unavailable" with the reason, never a made-up number.

------------------------------------------------------------------------
THE ACTUAL TRAINED MODEL'S INPUT/OUTPUT CONTRACT (see train_lstm.py for
how these were chosen and measured -- this is not a guess):
------------------------------------------------------------------------
- Input: exactly SEQUENCE_LENGTH (30) engagement scores, normalized to
  [0, 1], shape (1, 30, 1). Shorter valid histories (>= MIN_SEQUENCE_LENGTH)
  are LEFT-PADDED by repeating the earliest available sample; longer
  histories are truncated to the most recent 30.
- Output: the model predicts a DELTA from the input window's own mean,
  not the absolute future value (tanh activation, so it can be negative)
  -- engagement scores are highly autocorrelated over 30-40s, so
  "assume it stays the same" is a strong baseline, and training against
  the residual gives the network something more useful to learn than
  just copying that baseline. predict() reconstructs the absolute
  prediction as (window_mean + delta).
- HONEST RESULT (see train_lstm.py's printed output when it was last
  run): on held-out validation data (split by session so no sliding
  window leaks between train/val), this model's absolute-value MAE was
  close to but did NOT clearly beat the naive "predict the window's own
  mean" baseline. That is a genuine, expected consequence of the
  training set being small (~15 real session/student groups, not
  thousands of distinct students) and short-horizon engagement being
  intrinsically autocorrelated -- not a bug. Retraining as more live
  sessions accumulate real engagement_records (just re-run
  train_lstm.py) is expected to help; treat today's predictions as a
  genuine but early/low-confidence model output, not a mature one.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from repositories.active import EngagementRepository, AlertRepository
from models.student import Student  # noqa: F401 -- registers `students` table for
# FutureEngagementPrediction's FK (same pattern already used by
# app/routers/monitoring.py for EngagementRecord/Alert's FKs) -- this
# service must not depend on some other module having imported it first.

# ============================================================
# CONFIGURATION -- centralized here rather than scattered as magic
# numbers across routes/frontend, per the task's explicit instruction.
# ============================================================

# 30-60s window per spec; 45s is the midpoint.
SEQUENCE_WINDOW_SECONDS = 45

# How far ahead the trained model actually predicts: HORIZON_STEPS (10)
# in train_lstm.py, at this data's observed ~1 sample/sec analyze-frame
# rate. Reported to callers as prediction_horizon_seconds instead of
# reusing SEQUENCE_WINDOW_SECONDS (that's the INPUT collection window,
# a different, larger number) so the UI can honestly say how far ahead
# "predicted" actually means.
PREDICTION_HORIZON_SECONDS = 10

# Minimum number of VALID (non-no-person) samples inside the window
# before a prediction is even attempted. At ~1.6 analyze-frame calls/sec
# (the existing client send interval), this is roughly 6-7s of steady
# presence -- enough to be a real short history, comfortably under the
# 30-60s target window so "insufficient data" doesn't linger for the
# entire window on every session. This is a placeholder heuristic: the
# real minimum should come from whatever sequence length the eventual
# trained model actually requires.
MIN_SEQUENCE_LENGTH = 10

# The trained model's fixed input length (see train_lstm.py's
# SEQUENCE_LENGTH -- must match exactly, it's baked into the saved
# model's weights/shape). A valid history between MIN_SEQUENCE_LENGTH and
# this is left-padded, not rejected; MIN_SEQUENCE_LENGTH is the "is there
# enough real signal to even try" gate, SEQUENCE_LENGTH is purely the
# model's fixed tensor shape.
SEQUENCE_LENGTH = 30

# How often a prediction is actually (re)computed per student, in
# seconds. Engagement scores/records keep accumulating every frame via
# the existing pipeline regardless; only the (currently unavailable, and
# even once real, comparatively expensive) LSTM inference itself is
# gated to this cadence -- never run per-frame.
PREDICTION_INTERVAL_SECONDS = 10

# Reused, not invented: 40 is the exact cutoff app/routers/monitoring.py's
# get_active_alert() already uses for engagement_score < 40 ->
# "attention_drop_predicted" (current-score based). This service applies
# the same cutoff to the PREDICTED score instead.
ATTENTION_DROP_THRESHOLD = 40.0

# Reused, not invented: 70 is the "Engaged"/focused cutoff already used
# throughout the live pipeline and UI -- ai_service.py's
# `"Engaged" if engagement_score >= 70`, AIMonitoringPanel.tsx and
# TeacherLiveClassroomPage.tsx's `currentEngagement >= 70 ? 'engaged'`.
STABLE_THRESHOLD = 70.0

# Sentinel used for "no person" engagement_status by ai_service.py
# (see calculate_engagement / process_frame). Records carrying this
# status are NOT real engagement observations of the student -- they
# must never enter the prediction sequence (section 9 of the spec).
NO_PERSON_STATUS = "No Person Detected"

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = _PROJECT_ROOT / "ml_models" / "engagement_prediction" / "lstm_engagement_model.keras"

STATUS_OK = "ok"
STATUS_INSUFFICIENT_DATA = "insufficient_data"
STATUS_UNAVAILABLE = "unavailable"
STATUS_PAUSED_NO_PERSON = "paused_no_person"


# ============================================================
# HISTORICAL / FUTURE ENGAGEMENT PREDICTION -- a SEPARATE feature from
# predict() above.
#
# predict() forecasts a few seconds ahead, *within* one live session,
# from that session's own per-FRAME engagement_score sequence. The
# feature below instead forecasts a student's engagement in their *next*
# class, from their own COMPLETED sessions only (never the current live
# one) -- one input timestep per completed session, not per frame. It
# therefore genuinely needs a different-shaped model (multivariate,
# session-granularity) rather than reusing predict()'s trained weights,
# which are fixed at (30 frames, 1 feature) and tuned for ~1s-apart
# frame-to-frame autocorrelation -- not for session-to-session gaps that
# can be hours or days apart. Everything else (repositories, alert
# taxonomy, no-person exclusion policy, the "predict a delta from the
# window's own mean" framing) is reused as-is; see
# ml_models/engagement_prediction/train_future_engagement_lstm.py for
# how this model is trained, and for this module's honest reporting of
# whether the current real dataset was actually large enough to do so.
# ============================================================

# A student needs at least this many COMPLETED sessions with usable
# (non-no-person) engagement data before ANY future prediction is
# attempted -- explicit product requirement, not a technical minimum;
# also doubles as the model's fixed input window when exactly this many
# are available (see FUTURE_SEQUENCE_LENGTH_SESSIONS below).
FUTURE_MIN_SESSIONS = 3

# The trained future-model's fixed input length in SESSIONS (not
# frames). A student with more than this many usable completed sessions
# has only their FUTURE_SEQUENCE_LENGTH_SESSIONS most recent ones used
# (recency-biased fixed window, per the spec's "prefer recent history");
# a student with between FUTURE_MIN_SESSIONS and this many has their
# available history left-padded by repeating their earliest usable
# session's feature vector -- same padding technique predict() already
# uses for frame sequences, applied here at session granularity.
FUTURE_SEQUENCE_LENGTH_SESSIONS = 6

# Real alert_type strings actually written to the `alerts` table today
# (see app/routers/monitoring.py's get_active_alert() and its
# predicted_attention_drop write) mapped to this model's feature
# channels. No alert type is invented here -- "sleeping/drowsiness" is
# NOT included because it is only ever a derived, live-only UI label
# (AIMonitoringPanel's isDrowsy, computed from a low CURRENT engagement
# score) and is never itself persisted as an alerts row; low engagement
# already flows into the engagement_mean channel below, so that signal
# is not lost, just not double-counted as a separate "alert" channel.
# attention_drop_predicted (the rule-based get_active_alert threshold)
# and predicted_attention_drop (written when predict()'s own LSTM
# transitions into its low-prediction tier) are combined into one
# channel: both represent the same underlying "attention dip
# flagged" concept from two different detectors.
#
# EXCEPTION -- no_person_rate: `alerts` only gets ONE new row when the
# active alert TRANSITIONS into no_person_detected (see the Alert
# model's own docstring: one row per state change, not one per frame).
# A session that is 95% empty but never re-triggers that transition
# mid-session would then report a near-zero rate if counted the same
# way as the other four. So no_person_rate is instead computed directly
# in _build_student_session_history() from the dense, per-FRAME
# engagement_records.engagement_status column -- the tuple entry below
# is kept only so this list still defines the required feature ORDER
# and documents which concept the channel represents; its alert_type
# string is not actually queried for this one channel.
FUTURE_ALERT_FEATURES = [
    ("no_person_rate", ("no_person_detected",)),
    ("phone_rate", ("phone_detected",)),
    ("multiple_person_rate", ("multiple_person",)),
    ("looking_away_rate", ("looking_away",)),
    ("attention_drop_rate", ("attention_drop_predicted", "predicted_attention_drop")),
]

# engagement_mean + one rate per FUTURE_ALERT_FEATURES entry.
FUTURE_NUM_FEATURES = 1 + len(FUTURE_ALERT_FEATURES)

FUTURE_MODEL_PATH = (
    _PROJECT_ROOT
    / "ml_models"
    / "engagement_prediction"
    / "lstm_future_engagement_model.keras"
)

FUTURE_STATUS_INSUFFICIENT_DATA = "insufficient_data"
FUTURE_STATUS_READY = "ready"
FUTURE_STATUS_UNAVAILABLE = "unavailable"
FUTURE_STATUS_ERROR = "error"


class EngagementPredictionService:
    """Loads (or fails to load, honestly) a trained LSTM once per process,
    and produces per-(session_id, student_id) future-engagement
    predictions from that student's own recent, valid engagement_records
    -- never mixing students or sessions, never predicting from
    no-person/default data.
    """

    _model = None
    _model_load_attempted = False
    _model_error: Optional[str] = None

    # Separate cache for the historical/future-prediction model -- a
    # different file, different shape, loaded independently of _model
    # above so a problem with one never affects the other.
    _future_model = None
    _future_model_key: Optional[str] = None
    _future_model_error: Optional[str] = None

    # ------------------------------------------------------------
    # Model loading -- lazy, cached, never crashes the caller.
    # ------------------------------------------------------------
    @classmethod
    def _load_model(cls):
        if cls._model_load_attempted:
            return cls._model

        cls._model_load_attempted = True

        if not MODEL_PATH.exists():
            cls._model_error = (
                f"No trained LSTM model file found at {MODEL_PATH}. "
                "This project has not trained one yet -- engagement "
                "prediction is architecturally complete but inactive "
                "until a real model is placed there."
            )
            return None

        try:
            # Imported lazily so importing this module (and therefore the
            # whole prediction feature) never pays the TensorFlow import
            # cost, or risks crashing app startup, when no model file
            # exists at all -- same defensive pattern already used for
            # face_model/emotion_model in ai_service.py.
            from tensorflow.keras.models import load_model

            cls._model = load_model(MODEL_PATH)
        except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
            cls._model_error = (
                f"LSTM model file exists at {MODEL_PATH} but failed to "
                f"load ({exc}). Engagement prediction is unavailable "
                "until this is fixed -- no fallback/fake prediction will "
                "be substituted."
            )
            cls._model = None

        return cls._model

    @classmethod
    def is_model_available(cls) -> bool:
        return cls._load_model() is not None

    @classmethod
    def model_status(cls) -> dict:
        """Lightweight, side-effect-free health check for startup/manual
        verification -- does not itself attempt a prediction."""

        available = cls.is_model_available()

        return {
            "model_available": available,
            "model_path": str(MODEL_PATH),
            "error": None if available else cls._model_error,
        }

    # ------------------------------------------------------------
    # Sequence preparation
    # ------------------------------------------------------------
    @staticmethod
    def _collect_sequence(db, session_id: int, student_id: int):
        """This student's own valid engagement scores for this session
        only, from the last SEQUENCE_WINDOW_SECONDS. Excludes no-person
        frames (they are not real engagement observations) rather than
        letting them silently drag the sequence toward a default value.

        Returns (scores: list[float], most_recent_is_no_person: bool).
        """

        since = datetime.now(timezone.utc) - timedelta(seconds=SEQUENCE_WINDOW_SECONDS)

        records = EngagementRepository.get_recent_student_session_records(
            db, session_id, student_id, since
        )

        most_recent_is_no_person = bool(
            records and records[-1].engagement_status == NO_PERSON_STATUS
        )

        valid_scores = [
            float(r.engagement_score)
            for r in records
            if r.engagement_status != NO_PERSON_STATUS
            and r.engagement_score is not None
        ]

        return valid_scores, most_recent_is_no_person

    @staticmethod
    def _build_model_input(scores: list):
        """Normalize+shape a list of 0-100 engagement scores into exactly
        what the trained model expects: (1, SEQUENCE_LENGTH, 1), left-padded
        (by repeating the earliest sample) or truncated to the most recent
        SEQUENCE_LENGTH values. Also returns the normalized window's own
        mean, since predict() needs it to reconstruct an absolute
        prediction from the model's delta output.
        """

        normalized = np.array(scores, dtype="float32") / 100.0

        if len(normalized) < SEQUENCE_LENGTH:
            pad = np.full(
                SEQUENCE_LENGTH - len(normalized), normalized[0], dtype="float32"
            )
            normalized = np.concatenate([pad, normalized])
        elif len(normalized) > SEQUENCE_LENGTH:
            normalized = normalized[-SEQUENCE_LENGTH:]

        window_mean = float(normalized.mean())

        return normalized.reshape(1, SEQUENCE_LENGTH, 1), window_mean

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------
    @classmethod
    def predict(cls, db, session_id: int, student_id: int) -> dict:
        """Predict this student's future engagement for this session ONLY,
        from their own recent valid history. Never raises -- always
        returns a well-formed result dict, with status honestly
        reflecting whether a real prediction was actually produced.
        """

        timestamp = datetime.now(timezone.utc).isoformat()

        base_result = {
            "session_id": session_id,
            "student_id": student_id,
            "current_engagement": None,
            "predicted_engagement": None,
            "prediction_horizon_seconds": PREDICTION_HORIZON_SECONDS,
            "status": STATUS_UNAVAILABLE,
            "attention_drop_predicted": False,
            "threshold": ATTENTION_DROP_THRESHOLD,
            "sequence_length": 0,
            "reason": None,
            "timestamp": timestamp,
        }

        scores, most_recent_is_no_person = cls._collect_sequence(
            db, session_id, student_id
        )

        base_result["sequence_length"] = len(scores)
        base_result["current_engagement"] = scores[-1] if scores else None

        if most_recent_is_no_person:
            base_result["status"] = STATUS_PAUSED_NO_PERSON
            base_result["reason"] = (
                "No person is currently in frame -- prediction is paused "
                "rather than computed from stale or default data."
            )
            return base_result

        if len(scores) < MIN_SEQUENCE_LENGTH:
            base_result["status"] = STATUS_INSUFFICIENT_DATA
            base_result["reason"] = (
                f"Collecting engagement data ({len(scores)}/"
                f"{MIN_SEQUENCE_LENGTH} samples so far)."
            )
            return base_result

        model = cls._load_model()

        if model is None:
            base_result["status"] = STATUS_UNAVAILABLE
            base_result["reason"] = cls._model_error
            return base_result

        try:
            model_input, window_mean = cls._build_model_input(scores)
            raw_output = model.predict(model_input, verbose=0)
            predicted_delta = float(np.ravel(raw_output)[0])
            predicted_score = (window_mean + predicted_delta) * 100.0
            predicted_score = max(0.0, min(100.0, predicted_score))
        except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
            base_result["status"] = STATUS_UNAVAILABLE
            base_result["reason"] = f"LSTM inference failed: {exc}"
            return base_result

        base_result["predicted_engagement"] = round(predicted_score, 2)
        base_result["status"] = STATUS_OK
        base_result["attention_drop_predicted"] = (
            predicted_score < ATTENTION_DROP_THRESHOLD
        )

        return base_result

    # ==============================================================
    # HISTORICAL / FUTURE ENGAGEMENT PREDICTION (separate feature --
    # see the module-level comment above FUTURE_MIN_SESSIONS).
    # ==============================================================

    @classmethod
    def _future_model_key_now(cls) -> str:
        """Identity marker for whatever is currently at FUTURE_MODEL_PATH
        (path + mtime), used both to decide whether the in-process model
        cache needs reloading and to stamp persisted prediction rows --
        so a retrained model file is picked up (and every student's
        cached prediction recomputed) without needing a manually-bumped
        version constant."""

        if not FUTURE_MODEL_PATH.exists():
            return "no-model"

        return f"lstm-future-v1-{int(FUTURE_MODEL_PATH.stat().st_mtime)}"

    @classmethod
    def _load_future_model(cls):
        key = cls._future_model_key_now()

        if cls._future_model_key == key:
            return cls._future_model

        cls._future_model_key = key

        if key == "no-model":
            cls._future_model = None
            cls._future_model_error = (
                f"No trained historical/future-engagement model file found "
                f"at {FUTURE_MODEL_PATH}. Run "
                "ml_models/engagement_prediction/train_future_engagement_lstm.py "
                "once enough real completed-session data exists (see that "
                "script's own reporting of whether it currently does)."
            )
            return None

        try:
            from tensorflow.keras.models import load_model

            cls._future_model = load_model(FUTURE_MODEL_PATH)
            cls._future_model_error = None
        except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
            cls._future_model = None
            cls._future_model_error = (
                f"Historical/future-engagement model file exists at "
                f"{FUTURE_MODEL_PATH} but failed to load ({exc})."
            )

        return cls._future_model

    @staticmethod
    def _build_student_session_history(db, student_id: int) -> list:
        """This student's own COMPLETED sessions only (chronological
        order), reduced to one entry per session -- including sessions
        the student was absent from for part or all of the time.

        engagement_mean is a PRESENCE-AWARE session score, not a plain
        average of the frames the student happened to be visible for:

            visible_ratio      = (total_records - no_person_records) / total_records
            visible_engagement = mean engagement_score over the visible records only
            engagement_mean     = visible_engagement * visible_ratio

        A student visible for only 3% of a session, scoring 98% in that
        3%, gets engagement_mean ~= 2.9%, not 98%. (This is mathematically
        the same as averaging engagement_score across EVERY record in the
        session, since ai_service.calculate_engagement() already writes 0
        for every no-person frame -- computed the explicit way above so
        it stays correct even if that stored-zero convention ever
        changes.) A session where the student was never visible at all
        still contributes a real entry: engagement_mean=0.0,
        no_person_rate=1.0 -- it is NEVER dropped, because repeated
        absence is itself meaningful historical behavior the model must
        be able to see (both as a feature and, via train_future_
        engagement_lstm.py reusing this same method for its training
        target, as something the model is trained to predict).

        no_person_rate is computed directly from the dense, per-FRAME
        engagement_records.engagement_status column -- NOT from the
        `alerts` table, which only gets one row per state TRANSITION
        (see the Alert model's docstring) and would otherwise report a
        near-zero rate for a session that was mostly/entirely empty but
        never re-triggered that transition. The other four rates
        (phone/multiple_person/looking_away/attention_drop) remain real
        persisted `alerts` events, unchanged.
        """

        records = EngagementRepository.get_completed_session_records_for_student(
            db, student_id
        )

        sessions: dict = {}
        session_order: list = []

        for record in records:
            if record.session_id not in sessions:
                sessions[record.session_id] = []
                session_order.append(record.session_id)
            sessions[record.session_id].append(record)

        alert_counts_by_session = AlertRepository.counts_by_type_for_sessions(
            db, student_id, session_order
        )

        history = []

        for session_id in session_order:
            session_records = sessions[session_id]
            total_samples = len(session_records)

            valid_scores = [
                float(r.engagement_score)
                for r in session_records
                if r.engagement_status != NO_PERSON_STATUS
                and r.engagement_score is not None
            ]
            no_person_count = sum(
                1 for r in session_records
                if r.engagement_status == NO_PERSON_STATUS
            )

            visible_ratio = (total_samples - no_person_count) / total_samples
            visible_engagement = (
                sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
            )
            presence_aware_engagement = visible_engagement * visible_ratio

            no_person_rate = no_person_count / total_samples

            alert_counts = alert_counts_by_session.get(session_id, {})

            alert_rates = {"no_person_rate": no_person_rate}
            for feature_name, alert_type_strings in FUTURE_ALERT_FEATURES:
                if feature_name == "no_person_rate":
                    continue  # computed above, from engagement_records
                count = sum(
                    alert_counts.get(alert_type, 0)
                    for alert_type in alert_type_strings
                )
                alert_rates[feature_name] = count / total_samples

            history.append({
                "session_id": session_id,
                "engagement_mean": presence_aware_engagement,
                "alert_rates": alert_rates,
            })

        return history

    @staticmethod
    def _session_feature_vector(session: dict) -> list:
        vector = [session["engagement_mean"] / 100.0]

        for feature_name, _alert_types in FUTURE_ALERT_FEATURES:
            vector.append(session["alert_rates"][feature_name])

        return vector

    @classmethod
    def _build_future_model_input(cls, window: list):
        """Exactly SEQUENCE_LENGTH_SESSIONS timesteps x FUTURE_NUM_FEATURES
        features, left-padded (by repeating the earliest session in
        `window`) if fewer are available. `window` must already be
        truncated to at most FUTURE_SEQUENCE_LENGTH_SESSIONS entries by
        the caller. Also returns the window's own mean engagement (channel
        0), since the model predicts a delta from it -- same reconstruction
        as predict() uses for frame sequences."""

        vectors = [cls._session_feature_vector(s) for s in window]
        array = np.array(vectors, dtype="float32")

        if len(array) < FUTURE_SEQUENCE_LENGTH_SESSIONS:
            pad = np.tile(
                array[0], (FUTURE_SEQUENCE_LENGTH_SESSIONS - len(array), 1)
            )
            array = np.concatenate([pad, array], axis=0)

        window_mean_engagement = float(array[:, 0].mean())

        return (
            array.reshape(1, FUTURE_SEQUENCE_LENGTH_SESSIONS, FUTURE_NUM_FEATURES),
            window_mean_engagement,
        )

    @classmethod
    def _compute_future_prediction(cls, history: list) -> dict:
        """Pure function: history (as built by _build_student_session_history)
        -> {status, prediction_score, reason}. No DB access, no caching --
        get_future_prediction() below owns persistence."""

        usable_count = len(history)

        if usable_count < FUTURE_MIN_SESSIONS:
            return {
                "status": FUTURE_STATUS_INSUFFICIENT_DATA,
                "prediction_score": None,
                "reason": (
                    f"Only {usable_count}/{FUTURE_MIN_SESSIONS} completed "
                    "sessions with usable engagement data so far."
                ),
            }

        model = cls._load_future_model()

        if model is None:
            return {
                "status": FUTURE_STATUS_UNAVAILABLE,
                "prediction_score": None,
                "reason": cls._future_model_error,
            }

        try:
            window = history[-FUTURE_SEQUENCE_LENGTH_SESSIONS:]
            model_input, window_mean = cls._build_future_model_input(window)
            raw_output = model.predict(model_input, verbose=0)
            predicted_delta = float(np.ravel(raw_output)[0])
            predicted_score = (window_mean + predicted_delta) * 100.0
            predicted_score = max(0.0, min(100.0, predicted_score))
        except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
            return {
                "status": FUTURE_STATUS_UNAVAILABLE,
                "prediction_score": None,
                "reason": f"LSTM inference failed: {exc}",
            }

        return {
            "status": FUTURE_STATUS_READY,
            "prediction_score": round(predicted_score, 2),
            "reason": None,
        }

    @staticmethod
    def _serialize_future_row(row) -> dict:
        return {
            "student_id": row.student_id,
            "status": row.status,
            "prediction_score": row.prediction_score,
            "historical_sessions_used": row.historical_sessions_used,
            "model_version": row.model_version,
            "reason": row.reason,
            "generated_at": (
                row.generated_at.isoformat() if row.generated_at else None
            ),
        }

    @classmethod
    def get_future_prediction(
        cls, db, student_id: int, *, force_refresh: bool = False
    ) -> dict:
        """Cross-session HISTORICAL/FUTURE engagement prediction for one
        student -- persisted in future_engagement_predictions (one row per
        student, upserted) so it survives the student leaving a live
        class.

        Only actually recomputes (runs real DB queries + LSTM inference)
        when the number of usable completed sessions found has changed
        since the last computation, the trained model file itself has
        changed, or force_refresh=True -- so repeated dashboard/teacher-
        list reads are cheap cache reads, never re-inference on every
        poll. force_refresh=True is used by the session-end hook (see
        SessionService.end_session) right when a session most recently
        finalized as completed, which is the actual event this feature's
        regeneration is tied to. Never raises -- always returns a
        well-formed dict with an honest status.
        """

        from repositories.active import FutureEngagementRepository

        try:
            history = cls._build_student_session_history(db, student_id)
            usable_count = len(history)
            model_key = cls._future_model_key_now()

            cached = FutureEngagementRepository.get_by_student(db, student_id)

            if (
                not force_refresh
                and cached is not None
                and cached.historical_sessions_used == usable_count
                and cached.model_version == model_key
            ):
                return cls._serialize_future_row(cached)

            computed = cls._compute_future_prediction(history)

        except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
            computed = {
                "status": FUTURE_STATUS_ERROR,
                "prediction_score": None,
                "reason": str(exc),
            }
            usable_count = 0
            model_key = cls._future_model_key_now()

        saved = FutureEngagementRepository.upsert(
            db,
            student_id=student_id,
            status=computed["status"],
            prediction_score=computed["prediction_score"],
            historical_sessions_used=usable_count,
            model_version=model_key,
            reason=computed["reason"],
        )

        return cls._serialize_future_row(saved)


def prediction_state_label(result: dict) -> str:
    """Map a predict() result to the 3-tier UI label the spec asks for
    (Stable / Attention may decrease / Attention drop predicted),
    reusing the same centrally-defined thresholds -- so the frontend
    never has to hardcode them."""

    if result.get("status") != STATUS_OK or result.get("predicted_engagement") is None:
        return "unavailable"

    predicted = result["predicted_engagement"]

    if predicted >= STABLE_THRESHOLD:
        return "stable"
    if predicted >= ATTENTION_DROP_THRESHOLD:
        return "attention_may_decrease"
    return "attention_drop_predicted"


def future_prediction_status_label(result: dict) -> str:
    """Map a get_future_prediction() result to a 3-tier UI label, reusing
    the SAME centrally-defined thresholds as prediction_state_label()
    above (nothing new invented) -- "stable" / "needs_attention" /
    "at_risk" / "unavailable"."""

    if (
        result.get("status") != FUTURE_STATUS_READY
        or result.get("prediction_score") is None
    ):
        return "unavailable"

    score = result["prediction_score"]

    if score >= STABLE_THRESHOLD:
        return "stable"
    if score >= ATTENTION_DROP_THRESHOLD:
        return "needs_attention"
    return "at_risk"
