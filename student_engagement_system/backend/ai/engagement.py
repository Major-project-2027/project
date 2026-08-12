def calculate(
    emotion,
    blink_count,
    head_pose,
    gaze,
    phone_detected,
    person_count
):

    score = 100

    if phone_detected:
        score -= 30

    if person_count > 1:
        score -= 30

    if gaze != "Center":
        score -= 10

    if head_pose != "Forward":
        score -= 10

    return max(score, 0)