"""Per-(session, student) state for the live AI pipeline.

Previously, blink counters and frame-skip caches (last detected name,
emotion, person count, phone flag, EAR, active alert) lived as module-level
globals shared by every request regardless of which student or session they
belonged to. With more than one student being monitored at once, those
globals would interleave and corrupt each other's results. This module
scopes that state by (session_id, student_id) instead, so each student's
detection state is completely independent of every other student's -- even
across different classes/sessions running at the same time.

A single process-wide lock guards the dict itself (creation/deletion of
entries); it is intentionally NOT held during model inference, so requests
for different students still run concurrently. A second, separate lock
(`inference_lock` in ai_service.py) serializes the actual calls into the
shared MediaPipe/YOLO/TensorFlow model instances, which are not safe to
call from multiple threads at once.
"""

import threading

_lock = threading.Lock()

_states: dict[tuple[int, int], dict] = {}


def _new_state() -> dict:
    return {
        "blink_counter": 0,
        "blink_total": 0,
        "frame_counter": 0,
        "last_name": "Unknown",
        "last_emotion": "Unknown",
        "last_person_count": 1,
        "last_phone_detected": False,
        "last_ear": 0.0,
        "last_alert_type": None,
        "no_person_streak": 0,
        "last_prediction_at": 0.0,
        "last_prediction": None,
        "last_prediction_state": None,
    }


def get_state(session_id: int, student_id: int) -> dict:
    key = (int(session_id), int(student_id))

    with _lock:
        if key not in _states:
            _states[key] = _new_state()

        return _states[key]


def clear_session(session_id: int) -> int:
    """Drop all per-student state for a session that has ended. Returns the
    number of entries removed."""

    with _lock:
        keys = [key for key in _states if key[0] == int(session_id)]

        for key in keys:
            del _states[key]

        return len(keys)
