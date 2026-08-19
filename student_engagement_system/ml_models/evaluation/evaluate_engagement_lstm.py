"""Evaluates the EXISTING PRODUCTION live/in-session engagement LSTM
(ml_models/engagement_prediction/lstm_engagement_model.keras -- the
exact file backend/services/engagement_prediction_service.py loads)
using the SAME real held-out validation split the production training
script (train_lstm.py) already builds -- imported, not modified.

READ-ONLY / EVALUATION-ONLY:
- Does NOT call model.fit() anywhere -- the saved model is only loaded
  and used for model.predict(). No retraining occurs.
- Does NOT modify train_lstm.py, engagement_prediction_service.py, or
  any other production file. build_dataset() is imported as-is.
- Uses only real engagement_records already in the project database.

WHY THIS SPLIT IS A GENUINE HOLD-OUT:
train_lstm.py's build_dataset() splits by (session_id, student_id)
GROUP (not by row), with a fixed seed, specifically so no sliding
window from a validation group's session ever appeared in training.
This script reuses that exact split -- it does not re-derive its own.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from ml_models.engagement_prediction.train_lstm import (  # noqa: E402
    build_dataset, SEQUENCE_LENGTH,
)

MODEL_PATH = _PROJECT_ROOT / "ml_models" / "engagement_prediction" / "lstm_engagement_model.keras"
REPORT_PATH = Path(__file__).resolve().parent / "reports" / "live_engagement_lstm_report.json"


def _metrics(y_true, y_pred):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    # R^2 is only meaningful with >= 2 samples and non-degenerate variance.
    r2 = r2_score(y_true, y_pred) if len(y_true) >= 2 else None
    return mae, mse, rmse, r2


def main():
    result = {
        "component": "Live/in-session Engagement LSTM (production model)",
        "model_path": str(MODEL_PATH),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "Real engagement_records, held-out (session_id, student_id) group split reused from train_lstm.py's own build_dataset()",
    }

    print("=" * 70)
    print("LIVE ENGAGEMENT LSTM EVALUATION -- real held-out group split")
    print("=" * 70)

    try:
        from tensorflow.keras.models import load_model
        model = load_model(MODEL_PATH)
        result["model_runtime_status"] = "LOADED_OK"
        print(f"MODEL RUNTIME STATUS: LOADED OK ({MODEL_PATH})")
    except Exception as exc:  # noqa: BLE001
        result["model_runtime_status"] = "FAILED_TO_LOAD"
        result["model_load_error"] = str(exc)[:500]
        result["status"] = "NOT EVALUATABLE -- PRODUCTION MODEL FAILED TO LOAD"
        print("MODEL RUNTIME STATUS: FAILED TO LOAD:", str(exc)[:300])
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2))
        return

    print("\nBuilding the real dataset via train_lstm.py's own build_dataset()...")
    try:
        dataset = build_dataset()
    except RuntimeError as exc:
        result["status"] = f"NOT EVALUATABLE -- {exc}"
        print(str(exc))
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2))
        return

    val_groups = dataset["val_groups"]
    train_groups = dataset["train_groups"]
    val_students = sorted({g[1] for g in val_groups})
    train_students = sorted({g[1] for g in train_groups})

    print(f"Eligible (session,student) groups: {len(dataset['eligible_groups'])}")
    print(f"  train groups: {train_groups}  ({len(train_students)} distinct students)")
    print(f"  val groups:   {val_groups}  ({len(val_students)} distinct students)")

    X_val = dataset["X_val"].reshape(-1, SEQUENCE_LENGTH, 1)
    X_train = dataset["X_train"].reshape(-1, SEQUENCE_LENGTH, 1)

    print(f"\nVAL examples: {len(X_val)}  |  TRAIN examples: {len(X_train)}")

    if len(X_val) == 0:
        result["status"] = "NOT EVALUATABLE -- 0 validation examples in the current real dataset"
        print(result["status"])
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2))
        return

    print("\nRunning real inference (model.predict only -- no training)...")
    val_delta_pred = model.predict(X_val, verbose=0).ravel()
    val_abs_pred = np.clip(dataset["val_window_mean"] + val_delta_pred, 0.0, 1.0)
    val_abs_true = dataset["y_val_abs"]
    val_baseline_pred = dataset["val_window_mean"]  # naive: "assume no change"

    train_delta_pred = model.predict(X_train, verbose=0).ravel()
    train_abs_pred = np.clip(dataset["train_window_mean"] + train_delta_pred, 0.0, 1.0)
    train_abs_true = dataset["y_train_abs"]

    val_mae, val_mse, val_rmse, val_r2 = _metrics(val_abs_true, val_abs_pred)
    base_mae, base_mse, base_rmse, base_r2 = _metrics(val_abs_true, val_baseline_pred)
    train_mae, train_mse, train_rmse, train_r2 = _metrics(train_abs_true, train_abs_pred)

    print("\n" + "=" * 70)
    print("METRIC: MAE (this is a regression model -- there is no accuracy percentage)")
    print(f"VALIDATION  -- MAE={val_mae:.5f} MSE={val_mse:.5f} RMSE={val_rmse:.5f} "
          f"R2={'N/A' if val_r2 is None else f'{val_r2:.4f}'}  (~{val_mae*100:.2f} engagement points)")
    print(f"NAIVE BASELINE (predict window mean) on the SAME val set -- "
          f"MAE={base_mae:.5f} RMSE={base_rmse:.5f}  (~{base_mae*100:.2f} points)")
    print(f"TRAINING    -- MAE={train_mae:.5f} MSE={train_mse:.5f} RMSE={train_rmse:.5f} "
          f"R2={'N/A' if train_r2 is None else f'{train_r2:.4f}'}  "
          f"(reported separately -- NOT validation performance)")
    if val_mae < base_mae:
        print(f"-> Model beats the naive baseline on validation by {(1-val_mae/base_mae)*100:.1f}%.")
    else:
        print(f"-> Model does NOT beat the naive baseline on validation "
              f"(worse by {(val_mae/base_mae-1)*100:.1f}%).")
    print("=" * 70)

    n_val = len(X_val)
    reliability = (
        "STATISTICALLY INSUFFICIENT" if n_val < 5 else
        "LIMITED EVIDENCE" if n_val < 20 else
        "VALID PROJECT-SPECIFIC METRIC"
    )
    print(f"\nReliability judgment (based on n={n_val} validation examples, "
          f"{len(val_students)} student(s)): {reliability}")

    result.update({
        "status": reliability,
        "sequence_length": SEQUENCE_LENGTH,
        "eligible_groups": len(dataset["eligible_groups"]),
        "train_examples": int(len(X_train)),
        "val_examples": int(len(X_val)),
        "train_students": train_students,
        "val_students": val_students,
        "train_groups": [list(g) for g in train_groups],
        "val_groups": [list(g) for g in val_groups],
        "validation": {
            "metric": "MAE (not accuracy)",
            "mae": round(float(val_mae), 5),
            "mse": round(float(val_mse), 5),
            "rmse": round(float(val_rmse), 5),
            "r2": None if val_r2 is None else round(float(val_r2), 4),
            "mae_engagement_points": round(float(val_mae) * 100, 2),
        },
        "naive_baseline_on_val": {
            "mae": round(float(base_mae), 5),
            "mse": round(float(base_mse), 5),
            "rmse": round(float(base_rmse), 5),
            "mae_engagement_points": round(float(base_mae) * 100, 2),
        },
        "training_performance_NOT_validation": {
            "mae": round(float(train_mae), 5),
            "mse": round(float(train_mse), 5),
            "rmse": round(float(train_rmse), 5),
            "r2": None if train_r2 is None else round(float(train_r2), 4),
        },
    })

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nSaved report to {REPORT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
