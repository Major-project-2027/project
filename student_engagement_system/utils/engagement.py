from utils.config import WEIGHTS


def calculate_engagement(
    emotion,
    head_pose,
    blink_count,
    phone_detected,
    person_count,
    gaze="Center"
):
    """
    Calculate overall student engagement score.

    Returns:
        score (0–100)
        status
    """

    score = 0

    # Emotion
    if emotion in ["Happy", "Neutral"]:
        score += WEIGHTS["emotion"]

    # Head Pose
    if head_pose == "Forward":
        score += WEIGHTS["head_pose"]

    # Blink
    if blink_count < 30:
        score += WEIGHTS["blink"]

    # Phone
    if not phone_detected:
        score += WEIGHTS["phone"]

    # Person Count
    if person_count == 1:
        score += WEIGHTS["person"]

    # Gaze
    if gaze == "Center":
        score += WEIGHTS["gaze"]

    # Limit score to 100
    score = min(score, 100)

    if score >= 90:
        status = "Highly Engaged"

    elif score >= 70:
        status = "Engaged"

    elif score >= 50:
        status = "Moderately Engaged"

    else:
        status = "Distracted"

    return score, status