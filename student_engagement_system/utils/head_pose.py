import cv2
import numpy as np

from utils.config import *


def estimate_head_pose(landmarks, width, height):
    """
    Estimate head pose using MediaPipe landmarks.

    Returns:
        "Forward"
        "Left"
        "Right"
        "Up"
        "Down"
        "Unknown"
    """

    try:

        face_2d = []
        face_3d = []

        ids = [
            NOSE,
            CHIN,
            LEFT_EYE_OUTER,
            RIGHT_EYE_OUTER,
            LEFT_MOUTH,
            RIGHT_MOUTH
        ]

        for idx in ids:

            x = landmarks[idx].x * width
            y = landmarks[idx].y * height
            z = landmarks[idx].z

            face_2d.append([x, y])
            face_3d.append([x, y, z])

        face_2d = np.array(face_2d, dtype=np.float64)
        face_3d = np.array(face_3d, dtype=np.float64)

        focal_length = width

        cam_matrix = np.array([
            [focal_length, 0, width / 2],
            [0, focal_length, height / 2],
            [0, 0, 1]
        ])

        dist_matrix = np.zeros((4, 1), dtype=np.float64)

        success, rot_vec, trans_vec = cv2.solvePnP(
            face_3d,
            face_2d,
            cam_matrix,
            dist_matrix
        )

        if not success:
            return "Unknown"

        rmat, _ = cv2.Rodrigues(rot_vec)

        angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

        x_angle = angles[0] * 360
        y_angle = angles[1] * 360

        if y_angle < -15:
            direction = "Left"
        elif y_angle > 15:
            direction = "Right"
        elif x_angle < -15:
            direction = "Down"
        elif x_angle > 15:
            direction = "Up"
        else:
            direction = "Forward"

        
    except Exception:
        return "Unknown"