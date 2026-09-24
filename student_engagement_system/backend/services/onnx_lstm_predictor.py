"""ONNX Runtime drop-in for the two Keras LSTM engagement models
(lstm_engagement_model.keras / lstm_future_engagement_model.keras).

WHY THIS EXISTS: those two small LSTMs were the only thing in production
still loading TensorFlow -- ~300MB resident (import + load + first
predict), in both the Flask and FastAPI processes, against Render's 512MB
runtime limit. onnxruntime (already used for YOLO and the friend's
emotion model) runs the same job for ~15MB of import cost.

The .onnx files are the same architecture and weights, exported by
ml_models/engagement_prediction/export_lstm_onnx.py (tf2onnx,
model(x, training=False), opset 17), and verified against the Keras
models by ml_models/evaluation/validate_lstm_onnx_parity.py: max raw
output difference 8.1e-08 across 12,352 real replayed live inputs and
all 37 real future-model inputs, rounded scores and attention-drop flags
identical on all real data.

Same call contract as a Keras model as used by
engagement_prediction_service.py -- predict(x, verbose=0) -> array of
shape (batch, 1) -- so the service's inference lines stay unchanged.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


class ONNXLSTMPredictor:
    def __init__(self, model_path: Path):
        import onnxruntime as ort

        model_path = Path(model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"No ONNX LSTM model found at {model_path}.")

        # Same memory-oriented session options as ai_service.py's YOLO
        # session and onnx_emotion_predictor.py -- no numerical effect.
        from services.ort_options import single_thread_ort_options

        session_options = single_thread_ort_options(ort)
        session_options.enable_cpu_mem_arena = False
        session_options.enable_mem_pattern = False
        self.session = ort.InferenceSession(
            str(model_path), sess_options=session_options, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, x, verbose=0) -> np.ndarray:
        """Keras-compatible signature; `verbose` is accepted and ignored."""
        batch = np.ascontiguousarray(x, dtype=np.float32)
        return self.session.run(None, {self.input_name: batch})[0]
