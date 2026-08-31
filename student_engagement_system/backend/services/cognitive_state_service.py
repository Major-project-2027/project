"""Session-level cognitive-state summary (Focused / Neutral / Distracted /
Drowsy) for one student's completed class.

============================================================================
INSPECTION FINDINGS -- read this before changing anything here.
============================================================================

1. NO TRAINED COGNITIVE-STATE MODEL EXISTS AND IS USED. A project search
   found `ml_models/cognitive_monitoring/` (cognitive_monitor.py,
   cognitive_utils.py, cognitive_features.py, cognitive_levels.py) -- a
   fully-built "Phase 7" module with its own FastAPI router
   (app/routers/cognitive_monitoring.py, registered in app/main.py). It is
   explicitly rule-based, not a trained model (its own docstring: "RULE-
   BASED ONLY... using a configurable rule/threshold system, never a
   trained model"), and -- more importantly -- it is NEVER CALLED by the
   frontend or by the live ai_service.py/monitoring.py pipeline. It is
   dead/unintegrated code from an earlier phased build plan.

   That module was deliberately NOT reused here, for an honesty reason,
   not a laziness one: its `predict()` contract requires per-field
   confidence scores (emotion/face/gaze/head_pose/phone/engagement
   confidence, each 0-1) and continuous head-pose yaw/pitch/roll degrees
   -- NONE of which are actually persisted anywhere for historical frames.
   EngagementRecord (models/engagement.py) stores only categorical/boolean
   signals (emotion string, head_pose string, gaze string, phone_detected,
   multiple_person, engagement_score) -- no confidences, no raw angles.
   Feeding that module fabricated confidence/angle values just to reuse
   its code would violate the explicit "do not fabricate" requirement this
   feature was built under. So: this service is a NEW, small, transparent,
   deterministic classifier built directly from the signals this project
   ACTUALLY stores -- not a machine-learning model, and not a repurposing
   of the unused Phase 7 module. It is honestly labeled as such throughout.

2. SIGNALS ACTUALLY AVAILABLE PER STORED FRAME (EngagementRecord):
   emotion, head_pose, gaze, phone_detected, multiple_person,
   engagement_score, engagement_status, blink_count, timestamp.
   `head_pose`/`gaze` already reflect this project's own dead-zone-aware
   looking-away fix (ai_service.py's FRIEND_HEAD_POSE_MAP /
   LOOKING_AWAY_CONFIRM_STREAK work) -- "Looking Forward" already means
   "within the acceptable laptop-screen viewing zone", not raw single-
   frame center-only. This service reuses those values as-is.

3. DROWSINESS is NOT a per-frame EngagementRecord column, but IS a real,
   persisted signal: the `alerts` table gets one row each time a
   student's active alert transitions INTO "drowsiness" -- and that
   transition itself only ever fires after a genuine, continuous
   SLEEP_THRESHOLD_SECONDS (4s+) closed-eye episode (see ai_service.py's
   process_frame sleeping-tracking block). A session's count of
   "drowsiness" alert rows is therefore a real, non-fabricated count of
   distinct confirmed sleep episodes -- used below as the basis for an
   optional DROWSY session state, exactly as the task instructions
   permit ("if the existing project/model already supports additional
   states such as Drowsy... inspect and determine whether they can be
   included safely").

4. CONFUSED was explicitly considered and REJECTED. There is no genuine
   "confused" class anywhere in the real emotion model output (the 7 real
   FER classes are angry/disgust/fear/happy/sad/surprise/neutral -- see
   ai_service.py's emotion_labels and frontend/src/types/domain.ts's own
   comment: "There is no genuine 'confused' class"). Reporting a
   "Confused" cognitive state would have no real basis, so it is not
   implemented.

5. THRESHOLDS ARE REUSED, NOT INVENTED, where the project already has
   one: FOCUSED_ENGAGEMENT_THRESHOLD (70) and DISTRACTED_ENGAGEMENT_
   THRESHOLD (40) are the exact same cutoffs already used throughout the
   live pipeline (ai_service.py's "Engaged"/"Distracted" split,
   monitoring.py's get_active_alert() attention_drop_predicted cutoff,
   engagement_prediction_service.py's STABLE_THRESHOLD/
   ATTENTION_DROP_THRESHOLD). Everything else below (MIN_VALID_RECORDS,
   DROWSY_EPISODE_THRESHOLD) is a new, explicit, documented, configurable
   constant -- not a hidden magic number.

============================================================================
CLASSIFICATION METHOD (deterministic, rule/score-based -- NOT machine
learning; kept clearly separate from the LSTM engagement prediction):
============================================================================

    Existing: engagement_score (per frame) -> LSTM -> engagement prediction
    New:      this session's own EngagementRecord + alerts rows
                  -> per-record Focused/Neutral/Distracted classification
                  -> session-level aggregation (majority + drowsy override)
                  -> Focused / Neutral / Distracted / Drowsy summary

Step 1 -- per-record classification (classify_record() below), applied to
every EngagementRecord in the session for this student EXCEPT "No Person
Detected" frames (not a real observation of the student -- same exclusion
policy engagement_prediction_service.py already uses):

    DISTRACTED  if engagement_score < DISTRACTED_ENGAGEMENT_THRESHOLD
                or phone_detected
                or multiple_person
                or head_pose == "Looking Away"
    FOCUSED     if (not already DISTRACTED) and
                engagement_score >= FOCUSED_ENGAGEMENT_THRESHOLD
                and head_pose == "Looking Forward"
                and gaze == "Center"
    NEUTRAL     otherwise

Step 2 -- session aggregation: count each class across all valid records,
convert to percentages. The OVERALL session cognitive_state is whichever
of focused/neutral/distracted the student spent the most time in (ties
resolve to "neutral", the safe middle option) -- this is what makes the
result reflect "mostly focused" / "frequent distraction" behaviour over
the whole class, not a single final frame.

Step 3 -- drowsy override: if this session has >= DROWSY_EPISODE_THRESHOLD
confirmed "drowsiness" alert rows for this student, the session's overall
cognitive_state becomes "drowsy" (drowsiness ranks above the Focused/
Neutral/Distracted read-out, mirroring the exact same severity ordering
already used by get_active_alert()/calculate_engagement() elsewhere in
this project). The focused/neutral/distracted percentages are still
computed and stored either way -- "drowsy" only overrides the headline
label, it does not erase the underlying breakdown.

Step 4 -- insufficient data: if fewer than MIN_VALID_RECORDS valid
(non-no-person) records exist (student joined and left almost
immediately, or has no records at all), status is "insufficient_data" and
cognitive_state is left None. NEVER a randomly/defaulted state.
"""

from typing import Optional

from repositories.active import EngagementRepository, AlertRepository, CognitiveStateRepository
from services.engagement_prediction_service import NO_PERSON_STATUS

# ============================================================
# CONFIGURATION -- centralized, documented constants (per the task's
# explicit instruction to make thresholds configurable/documented rather
# than scattering magic numbers).
# ============================================================

# Reused, not invented -- see module docstring point 5.
FOCUSED_ENGAGEMENT_THRESHOLD = 70.0
DISTRACTED_ENGAGEMENT_THRESHOLD = 40.0

# A session needs at least this many valid (non-no-person) engagement
# records before a cognitive-state summary is attempted at all. At the
# live pipeline's ~1-1.6 analyze-frame calls/sec, this is only a few
# seconds of real presence -- deliberately low, because this is a coarse
# END-OF-SESSION summary (not a live sequence-model input like the LSTM's
# MIN_SEQUENCE_LENGTH=10), and a short-but-real session should still get
# a genuine (if noisier) summary rather than being marked insufficient
# too aggressively. Tune upward if session summaries feel too eager on
# very short sessions.
MIN_VALID_RECORDS = 5

# Any genuinely confirmed drowsiness episode this session (each already
# required a real, continuous >= SLEEP_THRESHOLD_SECONDS closed-eye
# streak to be recorded -- see module docstring point 3) is treated as
# noteworthy enough to surface as the headline state. Raise this if a
# single brief episode should not be enough to label the whole session
# "Drowsy".
DROWSY_EPISODE_THRESHOLD = 1

STATUS_OK = "ok"
STATUS_INSUFFICIENT_DATA = "insufficient_data"

STATE_FOCUSED = "focused"
STATE_NEUTRAL = "neutral"
STATE_DISTRACTED = "distracted"
STATE_DROWSY = "drowsy"


# ============================================================
# Pure classification logic (no DB access -- independently testable)
# ============================================================

def classify_record(
    head_pose: Optional[str],
    gaze: Optional[str],
    phone_detected: bool,
    multiple_person: bool,
    engagement_score: float,
) -> str:
    """Classify ONE stored EngagementRecord into focused/neutral/distracted.

    See this module's docstring for the exact rule and why each threshold/
    signal was chosen. Never returns "drowsy" -- that is a session-level
    override computed separately from the alerts table, not a per-record
    signal (drowsiness is not itself a stored per-frame column).
    """

    head_pose = (head_pose or "").strip()
    gaze = (gaze or "").strip()

    is_distraction_signal = (
        bool(phone_detected)
        or bool(multiple_person)
        or head_pose == "Looking Away"
        or float(engagement_score) < DISTRACTED_ENGAGEMENT_THRESHOLD
    )

    if is_distraction_signal:
        return STATE_DISTRACTED

    if (
        float(engagement_score) >= FOCUSED_ENGAGEMENT_THRESHOLD
        and head_pose == "Looking Forward"
        and gaze == "Center"
    ):
        return STATE_FOCUSED

    return STATE_NEUTRAL


def _aggregate(records: list) -> dict:
    """Pure function: a list of EngagementRecord rows (already filtered to
    exclude no-person frames) -> per-class counts/percentages + the
    majority state. No DB access."""

    counts = {STATE_FOCUSED: 0, STATE_NEUTRAL: 0, STATE_DISTRACTED: 0}

    for record in records:
        state = classify_record(
            head_pose=record.head_pose,
            gaze=record.gaze,
            phone_detected=bool(record.phone_detected),
            multiple_person=bool(record.multiple_person),
            engagement_score=float(record.engagement_score or 0.0),
        )
        counts[state] += 1

    total = len(records)

    percentages = {
        state: round((count / total) * 100.0, 1) if total else 0.0
        for state, count in counts.items()
    }

    # Majority vote over the whole session. A state wins only if it is
    # the SOLE class with the highest count; any tie (2-way or 3-way,
    # regardless of which states are involved) resolves to "neutral", the
    # safe middle reading, rather than an arbitrary pick.
    max_count = max(counts.values())
    tied_states = [state for state, count in counts.items() if count == max_count]
    majority_state = tied_states[0] if len(tied_states) == 1 else STATE_NEUTRAL

    return {
        "counts": counts,
        "percentages": percentages,
        "majority_state": majority_state,
        "total": total,
    }


class CognitiveStateService:
    """Computes and persists ONE session's worth of cognitive-state
    summary for one student -- called exactly once per (session, student)
    from SessionService.end_session (the "class completed" event), never
    recomputed on every teacher-dashboard read (see
    CognitiveStateRepository.get_by_session for the read-only path)."""

    @staticmethod
    def _serialize(row) -> dict:
        return {
            "session_id": row.session_id,
            "student_id": row.student_id,
            "status": row.status,
            "cognitive_state": row.cognitive_state,
            "focused_percentage": row.focused_percentage,
            "neutral_percentage": row.neutral_percentage,
            "distracted_percentage": row.distracted_percentage,
            "valid_sample_count": row.valid_sample_count,
            "drowsy_episode_count": row.drowsy_episode_count,
            "reason": row.reason,
            "calculated_at": (
                row.calculated_at.isoformat() if row.calculated_at else None
            ),
        }

    @classmethod
    def compute_and_store(cls, db, session_id: int, class_id: int, student_id: int) -> dict:
        """Compute this student's cognitive-state summary for this session
        from their own stored engagement_records + alerts ONLY, and
        upsert it. Never raises -- degrades to an honest
        "insufficient_data" result instead."""

        try:
            all_records = EngagementRepository.get_student_session_records(
                db, session_id, student_id,
            )

            valid_records = [
                r for r in all_records
                if r.engagement_status != NO_PERSON_STATUS
                and r.engagement_score is not None
            ]

            drowsy_episode_count = AlertRepository.counts_by_type(
                db, session_id, student_id,
            ).get("drowsiness", 0)

            if len(valid_records) < MIN_VALID_RECORDS:
                status = STATUS_INSUFFICIENT_DATA
                cognitive_state = None
                percentages = {
                    STATE_FOCUSED: None,
                    STATE_NEUTRAL: None,
                    STATE_DISTRACTED: None,
                }
                reason = (
                    "No monitoring data was recorded for this student in "
                    "this session."
                    if not all_records
                    else (
                        f"Only {len(valid_records)}/{MIN_VALID_RECORDS} valid "
                        "monitoring samples -- the student was likely present "
                        "only briefly or rarely in frame."
                    )
                )
            else:
                aggregate = _aggregate(valid_records)
                status = STATUS_OK
                reason = None
                percentages = aggregate["percentages"]

                if drowsy_episode_count >= DROWSY_EPISODE_THRESHOLD:
                    cognitive_state = STATE_DROWSY
                else:
                    cognitive_state = aggregate["majority_state"]

        except Exception as exc:  # noqa: BLE001 -- must degrade, never crash session-end.
            status = STATUS_INSUFFICIENT_DATA
            cognitive_state = None
            percentages = {
                STATE_FOCUSED: None,
                STATE_NEUTRAL: None,
                STATE_DISTRACTED: None,
            }
            drowsy_episode_count = 0
            valid_records = []
            reason = f"Cognitive-state calculation failed: {exc}"

        saved = CognitiveStateRepository.upsert(
            db,
            session_id=session_id,
            class_id=class_id,
            student_id=student_id,
            status=status,
            cognitive_state=cognitive_state,
            focused_percentage=percentages[STATE_FOCUSED],
            neutral_percentage=percentages[STATE_NEUTRAL],
            distracted_percentage=percentages[STATE_DISTRACTED],
            valid_sample_count=len(valid_records),
            drowsy_episode_count=drowsy_episode_count,
            reason=reason,
        )

        return cls._serialize(saved)
