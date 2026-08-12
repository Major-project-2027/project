import cv2
import numpy as np

from utils.config import FACE_INPUT_SIZE, EMOTION_INPUT_SIZE


def get_face_roi(frame, landmarks):
    """
    Extract face ROI from MediaPipe landmarks.
    """

    h, w = frame.shape[:2]

    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]

    xmin = max(int(min(xs) * w) - 20, 0)
    ymin = max(int(min(ys) * h) - 20, 0)

    xmax = min(int(max(xs) * w) + 20, w)
    ymax = min(int(max(ys) * h) + 20, h)

    face = frame[ymin:ymax, xmin:xmax]

    return face, (xmin, ymin, xmax, ymax)


def recognize_face(face, model):

    face = cv2.resize(face, FACE_INPUT_SIZE)

    face = face.astype(np.float32) / 255.0

    face = np.expand_dims(face, axis=0)

    prediction = model.predict(face, verbose=0)

    return prediction


def detect_emotion(face, model, emotion_labels):

    face = cv2.resize(face, EMOTION_INPUT_SIZE)

    face = face.astype(np.float32) / 255.0

    face = np.expand_dims(face, axis=0)

    prediction = model.predict(face, verbose=0)

    emotion = emotion_labels[np.argmax(prediction)]

    confidence = float(np.max(prediction))

    return emotion, confidence