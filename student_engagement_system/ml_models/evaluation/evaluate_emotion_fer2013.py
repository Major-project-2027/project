"""Evaluates the EXISTING PRODUCTION emotion model
(ml_models/emotion_recognition/emotion_model.keras -- the exact file
backend/services/ai_service.py loads) against a genuine held-out test
split of the real FER2013 dataset it was trained on.

READ-ONLY / EVALUATION-ONLY:
- Does not modify, retrain, or fine-tune the model in any way.
- Does not touch backend/, frontend/, or any production inference code.
- Uses only the real, already-present FER2013 CSV
  (datasets/raw/fer2013/fer2013.csv) -- no synthetic/fabricated labels.

WHY THIS TEST SPLIT IS GENUINELY HELD OUT (not training data):
Phase9_Emotion_Training.ipynb.ipynb split FER2013 70/15/15 into
train/val/test via two chained sklearn train_test_split calls with
random_state=42 and stratify=y, then trained ONLY on the 70% train
split and used the 15% val split for early stopping/checkpointing.
The 15% test split (5,384 real images) was carved out but the notebook
never actually evaluated the model against it. This script reproduces
that EXACT split (same seed, same two-step procedure, same source CSV,
confirmed byte-identical row count/class distribution to the original
training run) purely to finally run that already-existing held-out
test set through the already-existing saved model -- nothing new is
trained, nothing is fabricated.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
EMOTION_MODEL_PATH = _PROJECT_ROOT / "ml_models" / "emotion_recognition" / "emotion_model.keras"
FER_PATH = _PROJECT_ROOT / "datasets" / "raw" / "fer2013" / "fer2013.csv"
REPORT_PATH = Path(__file__).resolve().parent / "reports" / "emotion_fer2013_report.json"

# Must match ai_service.py's own emotion_labels list order exactly (also
# the order FER2013's own `emotion` column indices 0-6 use, confirmed
# against Phase9_Emotion_Training.ipynb.ipynb's printed class counts).
EMOTION_LABELS = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]

IMG_SIZE = 224
BATCH_SIZE = 32


def _rebuild_test_split():
    """Reproduces Phase9's exact 70/15/15 stratified split (seed=42) and
    returns only the 15% TEST portion -- never seen during training or
    validation-time checkpointing."""

    from sklearn.model_selection import train_test_split
    from tensorflow.keras.utils import to_categorical

    df = pd.read_csv(FER_PATH)

    X = np.array([
        np.fromstring(pixels, dtype=np.uint8, sep=' ')
        for pixels in df['pixels']
    ]).reshape(-1, 48, 48).astype("float32") / 255.0

    y = df['emotion'].values
    y_onehot = to_categorical(y, num_classes=7)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y_onehot, test_size=0.30, random_state=42, stratify=y_onehot
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    return X_test, y_test


def _preprocess_batch(images_48x48):
    """Mirrors Phase9's own preprocess(): grayscale -> RGB -> resize to
    the model's real input size. Identical procedure, just applied only
    to the held-out test slice."""

    import tensorflow as tf

    imgs = tf.expand_dims(images_48x48, axis=-1)
    imgs = tf.image.grayscale_to_rgb(imgs)
    imgs = tf.image.resize(imgs, (IMG_SIZE, IMG_SIZE))
    return imgs.numpy()


def main():
    result = {
        "component": "Emotion Recognition (production model)",
        "model_path": str(EMOTION_MODEL_PATH),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "FER2013 (real, public) -- held-out 15% test split, reconstructed with the exact seed/procedure used at training time",
    }

    print("=" * 70)
    print("EMOTION MODEL EVALUATION -- real FER2013 held-out test split")
    print("=" * 70)

    # ------------------------------------------------------------
    # Step 1: attempt to load the ACTUAL production model file.
    # This is reported honestly regardless of what happens next.
    # ------------------------------------------------------------
    try:
        from tensorflow.keras.models import load_model
        model = load_model(EMOTION_MODEL_PATH)
        result["model_runtime_status"] = "LOADED_OK"
        print(f"MODEL RUNTIME STATUS: LOADED OK ({EMOTION_MODEL_PATH})")
    except Exception as exc:  # noqa: BLE001
        result["model_runtime_status"] = "FAILED_TO_LOAD"
        result["model_load_error"] = str(exc)[:500]
        result["status"] = "NOT EVALUATABLE -- PRODUCTION MODEL FAILED TO LOAD"
        print("MODEL RUNTIME STATUS: FAILED TO LOAD")
        print(f"  error: {str(exc)[:300]}")
        print()
        print("No fresh test-set metric can be computed -- the production")
        print("model file cannot be deserialized in this environment. This")
        print("is reported as-is, not hidden. The only surviving number is")
        print("the ORIGINAL TRAINING RUN's own reported validation accuracy")
        print("(0.2504, frozen across all 5 epochs, from")
        print("Phase9_Emotion_Training.ipynb.ipynb's saved output) -- that")
        print("number was NOT reproduced by this script and is NOT a test-set")
        print("metric; it is quoted here only for reference, clearly labeled.")
        result["historical_training_run_val_accuracy"] = {
            "value": 0.2504,
            "note": "As printed in Phase9_Emotion_Training.ipynb.ipynb's own saved cell output. NOT independently reproduced by this script. This is VALIDATION accuracy from training time, not a TEST metric.",
        }
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2))
        print(f"\nSaved report to {REPORT_PATH}")
        return

    # ------------------------------------------------------------
    # Step 2: real held-out test split + real inference.
    # ------------------------------------------------------------
    print("\nRebuilding the exact 70/15/15 FER2013 split used at training time...")
    X_test, y_test_onehot = _rebuild_test_split()
    y_test = np.argmax(y_test_onehot, axis=1)
    print(f"Held-out TEST samples: {len(X_test)} (never used for training or checkpointing)")

    print("\nRunning real inference in batches...")
    preds = []
    for start in range(0, len(X_test), BATCH_SIZE):
        batch = _preprocess_batch(X_test[start:start + BATCH_SIZE])
        batch_preds = model.predict(batch, verbose=0)
        preds.append(batch_preds)
        if start % (BATCH_SIZE * 20) == 0:
            print(f"  {start}/{len(X_test)}")
    preds = np.concatenate(preds, axis=0)
    y_pred = np.argmax(preds, axis=1)

    # ------------------------------------------------------------
    # Step 3: real metrics -- no fabrication, no confidence-as-accuracy.
    # ------------------------------------------------------------
    from sklearn.metrics import (
        accuracy_score, precision_recall_fscore_support,
        classification_report, confusion_matrix,
    )

    accuracy = accuracy_score(y_test, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="weighted", zero_division=0
    )
    per_class = classification_report(
        y_test, y_pred, target_names=EMOTION_LABELS, output_dict=True, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred).tolist()

    print("\n" + "=" * 70)
    print(f"TEST ACCURACY:        {accuracy:.4f}  ({accuracy*100:.2f}%)")
    print(f"MACRO precision/recall/F1:    {macro_p:.4f} / {macro_r:.4f} / {macro_f1:.4f}")
    print(f"WEIGHTED precision/recall/F1: {weighted_p:.4f} / {weighted_r:.4f} / {weighted_f1:.4f}")
    print("\nPer-class F1:")
    for label in EMOTION_LABELS:
        print(f"  {label:10s}: {per_class[label]['f1-score']:.4f}  (support={int(per_class[label]['support'])})")
    print("\nConfusion matrix (rows=true, cols=predicted):")
    print("        " + " ".join(f"{l[:4]:>6s}" for l in EMOTION_LABELS))
    for label, row in zip(EMOTION_LABELS, cm):
        print(f"{label:8s}" + " ".join(f"{v:6d}" for v in row))
    print("=" * 70)

    result.update({
        "status": "VALID PROJECT-SPECIFIC METRIC",
        "test_samples": int(len(X_test)),
        "accuracy": round(float(accuracy), 4),
        "macro_precision": round(float(macro_p), 4),
        "macro_recall": round(float(macro_r), 4),
        "macro_f1": round(float(macro_f1), 4),
        "weighted_precision": round(float(weighted_p), 4),
        "weighted_recall": round(float(weighted_r), 4),
        "weighted_f1": round(float(weighted_f1), 4),
        "per_class_f1": {l: round(per_class[l]["f1-score"], 4) for l in EMOTION_LABELS},
        "confusion_matrix": cm,
        "labels_order": EMOTION_LABELS,
    })

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nSaved report to {REPORT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
