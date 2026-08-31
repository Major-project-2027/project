"""
predictor.py
------------
Inference wrapper around the trained emotion_model.keras.

Provides:
  - EmotionPredictor: loads the model once, predicts on a cropped face
    image (numpy array, BGR or grayscale) and returns both the raw
    FER2013 label and the simplified label used elsewhere in the system
    (Happy/Neutral/Sad/Angry/Confused/Tired — see FR-4 in the
    architecture doc).
  - run_webcam_demo(): a small OpenCV loop that opens the default webcam,
    runs MediaPipe/OpenCV face detection, crops each detected face, and
    overlays the predicted emotion + confidence on the video feed. This
    is a standalone demo only — the production system's real-time
    pipeline (Kafka/Celery worker, Section 4 of the architecture doc)
    would import EmotionPredictor.predict() the same way.

Not implemented here (out of scope for this module, per task instructions):
  face authentication, gaze/head-pose, object detection, backend/frontend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

from config import BEST_MODEL_PATH, IMG_SIZE, LABEL_MAP_PATH, SIMPLIFIED_LABEL_MAP
from utils import load_json


class EmotionPredictor:
    """Loads the trained Keras model once and exposes a simple predict() API."""

    def __init__(self, model_path: Path = BEST_MODEL_PATH, label_map_path: Path = LABEL_MAP_PATH):
        import tensorflow as tf

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"No trained model found at {model_path}. "
                "Run train_model.ipynb (or trainer.py) first."
            )

        self.model = tf.keras.models.load_model(model_path)

        if Path(label_map_path).exists():
            raw_map = load_json(label_map_path)
            # keys are stored as strings in JSON; normalize to int index
            self.index_to_label = {int(k): v for k, v in raw_map.items()}
        else:
            # Fallback to config.CLASS_NAMES order if label_map.json is missing
            from config import CLASS_NAMES

            self.index_to_label = dict(enumerate(CLASS_NAMES))

    def _preprocess(self, face_image: np.ndarray) -> np.ndarray:
        """Accepts a cropped face image as either:
          - grayscale (H, W)
          - BGR/RGB color (H, W, 3)
        and returns a (1, IMG_SIZE, IMG_SIZE, 3) float32 batch in [0, 1],
        matching what the model was trained on.
        """
        import cv2

        if face_image.ndim == 2:
            gray = face_image
        else:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)

        resized = cv2.resize(gray, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
        rgb = np.repeat(resized[..., np.newaxis], 3, axis=-1).astype("float32") / 255.0
        return np.expand_dims(rgb, axis=0)

    def predict(self, face_image: np.ndarray) -> dict:
        """Run inference on a single cropped face image.

        Returns
        -------
        dict with keys:
            raw_label        : str, one of config.CLASS_NAMES (FER2013 label)
            simplified_label : str, mapped onto the system-wide emotion set
            confidence       : float, softmax probability of the top class
            probabilities    : dict[str, float] of all class probabilities
        """
        batch = self._preprocess(face_image)
        probs = self.model.predict(batch, verbose=0)[0]

        top_idx = int(np.argmax(probs))
        raw_label = self.index_to_label[top_idx]

        return {
            "raw_label": raw_label,
            "simplified_label": SIMPLIFIED_LABEL_MAP.get(raw_label, raw_label.capitalize()),
            "confidence": float(probs[top_idx]),
            "probabilities": {
                self.index_to_label[i]: float(p) for i, p in enumerate(probs)
            },
        }


def run_webcam_demo(camera_index: int = 0, mirror: bool = True) -> None:
    """Standalone demo: open the webcam, detect faces, and overlay the
    predicted emotion in real time. Press 'q' to quit.

    Uses OpenCV's bundled Haar cascade for face detection so this demo has
    no extra dependency beyond opencv-python (already pinned in
    requirements.txt). The production pipeline uses MediaPipe for face
    detection instead (see architecture doc Section 4.1) — swapping the
    detector here does not change how EmotionPredictor is used.
    """
    import cv2

    predictor = EmotionPredictor()

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open webcam at index {camera_index}.")

    print("Webcam demo running. Press 'q' to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to read frame from webcam; stopping.")
                break

            if mirror:
                frame = cv2.flip(frame, 1)

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray_frame, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )

            for (x, y, w, h) in faces:
                face_crop = frame[y : y + h, x : x + w]
                if face_crop.size == 0:
                    continue
                result = predictor.predict(face_crop)
                label = f"{result['simplified_label']} ({result['confidence']*100:.0f}%)"

                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)
                cv2.putText(
                    frame,
                    label,
                    (x, max(y - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 200, 0),
                    2,
                )

            cv2.imshow("Emotion Detection (press q to quit)", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_webcam_demo()
