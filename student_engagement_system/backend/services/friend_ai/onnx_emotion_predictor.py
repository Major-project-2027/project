"""ONNX Runtime replacement for the friend's Keras-based EmotionPredictor
(inference/emotion/predictor.py).

WHY THIS EXISTS: loading the friend's emotion_model.keras via
tensorflow.keras.models.load_model, plus running one real prediction,
measured at ~112MB resident (construct + first inference) on top of an
already-~950MB pipeline that was getting OOM-killed on Render's 512MB
free tier. onnxruntime does the identical job (same weights, same
preprocessing, same output contract) for ~45MB (import + model load +
inference) -- verified numerically: the ONNX and Keras models were run
side-by-side on the same real face images and produced outputs matching
to within ~4e-6 (pure floating-point rounding noise), with the top
predicted class identical every time. See emotion_model.onnx, exported
from emotion_model.keras via tf2onnx.convert.from_keras, opset 15.

Every constant below (IMG_SIZE, class labels, simplified-label mapping,
the preprocessing steps) is copied verbatim from the friend's own
inference/emotion/config.py and predictor.py -- not re-derived -- so
behavior matches exactly, just via a lighter runtime.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np

# From inference/emotion/config.py -- FER2013 native resolution (48x48)
# upsampled to 96x96 for MobileNetV2, replicated across 3 channels.
IMG_SIZE = 96

# From inference/emotion/config.py's SIMPLIFIED_LABEL_MAP.
SIMPLIFIED_LABEL_MAP = {
    "angry": "Angry",
    "disgust": "Angry",
    "fear": "Confused",
    "happy": "Happy",
    "sad": "Sad",
    "surprise": "Confused",
    "neutral": "Neutral",
}

# Fallback if label_map.json is somehow missing -- matches config.CLASS_NAMES.
_DEFAULT_CLASS_NAMES = [
    "angry", "disgust", "fear", "happy", "sad", "surprise", "neutral",
]


class ONNXEmotionPredictor:
    """Same public contract as the friend's EmotionPredictor
    (inference/emotion/predictor.py): predict(face_image) -> dict with
    raw_label / simplified_label / confidence / probabilities."""

    def __init__(self, model_path: Path, label_map_path: Path):
        import onnxruntime as ort

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"No ONNX emotion model found at {model_path}.")

        # See ai_service.py's matching comment on the YOLO session --
        # disabling the memory arena/pattern pooling trades a small
        # per-call allocation cost for materially lower resident memory,
        # which is what a 512MB ceiling needs.
        session_options = ort.SessionOptions()
        session_options.enable_cpu_mem_arena = False
        session_options.enable_mem_pattern = False
        self.session = ort.InferenceSession(
            str(model_path), sess_options=session_options, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

        if Path(label_map_path).exists():
            with open(label_map_path, "r", encoding="utf-8") as f:
                raw_map = json.load(f)
            self.index_to_label = {int(k): v for k, v in raw_map.items()}
        else:
            self.index_to_label = dict(enumerate(_DEFAULT_CLASS_NAMES))

    def _preprocess(self, face_image: np.ndarray) -> np.ndarray:
        """Identical to the friend's EmotionPredictor._preprocess: grayscale,
        resize to IMG_SIZE, replicate to 3 channels, normalize to [0, 1]."""
        import cv2

        if face_image.ndim == 2:
            gray = face_image
        else:
            gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)

        resized = cv2.resize(gray, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_AREA)
        rgb = np.repeat(resized[..., np.newaxis], 3, axis=-1).astype("float32") / 255.0
        return np.expand_dims(rgb, axis=0)

    def predict(self, face_image: np.ndarray) -> dict:
        batch = self._preprocess(face_image)
        probs = self.session.run(None, {self.input_name: batch})[0][0]

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
