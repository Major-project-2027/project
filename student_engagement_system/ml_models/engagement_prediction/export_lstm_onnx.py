"""Exports both trained LSTM engagement models from Keras to ONNX.

Offline, one-time conversion step -- NOT part of the deployed
application and never imported by it. Reads the two existing .keras
files (never modifies, retrains, or re-saves them) and writes an .onnx
file next to each, containing the exact same architecture and weights:

    lstm_engagement_model.keras         -> lstm_engagement_model.onnx
        input  (None, 30, 1)  float32   (SEQUENCE_LENGTH frames x 1 feature)
    lstm_future_engagement_model.keras  -> lstm_future_engagement_model.onnx
        input  (None, 6, 6)   float32   (FUTURE_SEQUENCE_LENGTH_SESSIONS x
                                          FUTURE_NUM_FEATURES)
    both output (None, 1)     float32   (tanh delta-from-window-mean)

Shapes must match services/engagement_prediction_service.py's
_build_model_input() / _build_future_model_input() exactly; the script
asserts the loaded Keras models agree before converting.

Why tf2onnx.convert.from_function rather than from_keras: from_keras
does not support Keras 3 models (this project saves with Keras 3.x).
Tracing model(x, training=False) through a tf.function with an explicit
input signature is the supported path, and training=False guarantees
the LSTM's dropout/recurrent_dropout are inactive -- identical to what
model.predict() does at inference time. The batch dimension is left
dynamic (None), same as the Keras models.

Requires (dev machine only, not production): tensorflow, tf2onnx, onnx,
onnxruntime.

Usage (from student_engagement_system/):
    python ml_models/engagement_prediction/export_lstm_onnx.py
"""

import hashlib
import os
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

MODEL_DIR = Path(__file__).resolve().parent

# (keras file, onnx file, expected input shape excluding batch)
MODELS = [
    ("lstm_engagement_model.keras", "lstm_engagement_model.onnx", (30, 1)),
    ("lstm_future_engagement_model.keras", "lstm_future_engagement_model.onnx", (6, 6)),
]

# Supported by both tf2onnx 1.17 and onnxruntime 1.29; well below either's max.
ONNX_OPSET = 17

INPUT_NAME = "input"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _convert(keras_path: Path, onnx_path: Path, feature_shape: tuple) -> None:
    import tensorflow as tf
    import tf2onnx
    from tensorflow.keras.models import load_model

    model = load_model(keras_path)

    expected_input = (None, *feature_shape)
    if tuple(model.input_shape) != expected_input:
        raise ValueError(
            f"{keras_path.name}: input shape {model.input_shape} != expected {expected_input}"
        )
    if tuple(model.output_shape) != (None, 1):
        raise ValueError(f"{keras_path.name}: output shape {model.output_shape} != (None, 1)")

    @tf.function(
        input_signature=[tf.TensorSpec(expected_input, tf.float32, name=INPUT_NAME)]
    )
    def inference(x):
        return model(x, training=False)

    tf2onnx.convert.from_function(
        inference,
        input_signature=inference.input_signature,
        opset=ONNX_OPSET,
        output_path=str(onnx_path),
    )


def _check_onnx(onnx_path: Path, feature_shape: tuple) -> None:
    """Structural check + load with onnxruntime + one dummy run to confirm
    the graph executes and returns (batch, 1). Deliberately NOT a Keras-vs-
    ONNX numerical comparison -- that is the separate parity-validation step.
    """
    import numpy as np
    import onnx
    import onnxruntime as ort

    onnx.checker.check_model(onnx.load(str(onnx_path)))

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = session.get_inputs()[0]
    out = session.get_outputs()[0]
    print(f"  onnxruntime load: OK")
    print(f"  input : name={inp.name!r} shape={inp.shape} type={inp.type}")
    print(f"  output: name={out.name!r} shape={out.shape} type={out.type}")

    for batch in (1, 4):
        dummy = np.zeros((batch, *feature_shape), dtype="float32")
        result = session.run(None, {inp.name: dummy})[0]
        if result.shape != (batch, 1):
            raise ValueError(f"{onnx_path.name}: batch={batch} returned shape {result.shape}")
    print(f"  dummy run (batch 1 and 4): OK, output shape (batch, 1)")


def main():
    for keras_name, onnx_name, feature_shape in MODELS:
        keras_path = MODEL_DIR / keras_name
        onnx_path = MODEL_DIR / onnx_name

        print("=" * 60)
        print(f"{keras_name} -> {onnx_name}")

        hash_before = _sha256(keras_path)
        _convert(keras_path, onnx_path, feature_shape)
        hash_after = _sha256(keras_path)

        if hash_before != hash_after:
            raise RuntimeError(f"{keras_name} changed during conversion -- this must never happen")
        print(f"  source .keras unchanged: sha256 {hash_before[:16]}...")
        print(f"  wrote {onnx_path} ({onnx_path.stat().st_size:,} bytes)")

        _check_onnx(onnx_path, feature_shape)

    print("=" * 60)


if __name__ == "__main__":
    main()
