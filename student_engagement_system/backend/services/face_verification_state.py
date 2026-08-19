"""Short-lived, backend-owned record of "this student just passed live face
verification for this class," consumed by the join endpoints.

This is the anti-bypass mechanism for Feature 2: the frontend can never
just tell the backend "verified=true". The ONLY way this state gets set is
a successful face match inside routes/student.py's /face/verify-live
endpoint, which itself only runs a real comparison against the logged-in
student's own registered embedding. The join endpoints then require and
consume (single-use) this flag before creating an enrollment / confirming
a live-class join -- so calling the join endpoint directly, without ever
having passed verification, always fails.

Mirrors the per-(session, student) scoping/locking style already used in
ai_state.py for the same reason: cheap, process-local, no schema needed
for something this transient (a verification result is only ever useful
for the few seconds between "camera matched" and "the join call that
immediately follows").
"""

import threading
import time

_lock = threading.Lock()

# (student_id, class_id) -> verified_at (unix timestamp)
_verified: dict[tuple[int, int], float] = {}

# How long a successful face match remains usable to complete the join
# that follows it. Generous enough to cover network latency + the join
# call, short enough that it can't be replayed long after the camera
# check happened.
VERIFICATION_TTL_SECONDS = 120


def mark_verified(student_id: int, class_id: int) -> None:
    key = (int(student_id), int(class_id))

    with _lock:
        _verified[key] = time.time()


def consume_verification(student_id: int, class_id: int) -> bool:
    """Check whether this student has a still-valid verification for this
    class, and consume it (single-use) regardless of outcome so it can
    never be replayed for a second join.

    Returns True only if a verification existed and had not expired.
    """

    key = (int(student_id), int(class_id))

    with _lock:
        verified_at = _verified.pop(key, None)

    if verified_at is None:
        return False

    return (time.time() - verified_at) <= VERIFICATION_TTL_SECONDS
