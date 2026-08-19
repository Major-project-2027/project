"""Evaluates the EXISTING PRODUCTION historical/future-engagement LSTM
(ml_models/engagement_prediction/lstm_future_engagement_model.keras --
the exact file EngagementPredictionService.get_future_prediction() loads)
using the SAME real held-out student-level validation split the
production training script (train_future_engagement_lstm.py) already
builds -- imported, not modified, not retrained.

READ-ONLY / EVALUATION-ONLY -- see evaluate_engagement_lstm.py's
docstring for the same guarantees.

HONESTY REQUIREMENT (explicit, per instruction): this script does NOT
present a 1-example validation result as reliable. It computes the
metric because it is real and non-fabricated, then explicitly labels
it STATISTICALLY INSUFFICIENT rather than letting a small MAE number
imply the model works.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from ml_models.engagement_prediction.train_future_engagement_lstm import (  # noqa: E402
    build_dataset, MIN_TRAINING_EXAMPLES, MIN_GROUPS_PER_SPLIT,
)

MODEL_PATH = _PROJECT_ROOT / "ml_models" / "engagement_prediction" / "lstm_future_engagement_model.keras"
REPORT_PATH = Path(__file__).resolve().parent / "reports" / "future_engagement_lstm_report.json"

MIN_VAL_EXAMPLES_FOR_RELIABLE_EVAL = 5  # explicit, documented floor for this script's judgment only


def _metrics(y_true, y_pred):
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    r2 = r2_score(y_true, y_pred) if len(y_true) >= 2 else None
    return mae, mse, rmse, r2


def main():
    result = {
        "component": "Historical/Future Engagement LSTM (production model)",
        "model_path": str(MODEL_PATH),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "Real engagement_records + real alerts, held-out student-level split reused from train_future_engagement_lstm.py's own build_dataset()",
    }

    print("=" * 70)
    print("FUTURE ENGAGEMENT LSTM EVALUATION -- real held-out student split")
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

    print("\nBuilding the real dataset via train_future_engagement_lstm.py's own build_dataset()...")
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

    print(f"Eligible students (>=4 real usable completed sessions): {len(dataset['eligible_groups'])} {dataset['eligible_groups']}")
    print(f"  train students: {train_groups}")
    print(f"  val students:   {val_groups}")

    X_val = dataset["X_val"]
    X_train = dataset["X_train"]
    n_val = len(X_val)
    n_train = len(X_train)

    print(f"\nVAL examples: {n_val}  |  TRAIN examples: {n_train}")

    if n_val == 0:
        result["status"] = "NOT EVALUATABLE -- 0 validation examples in the current real dataset"
        print(result["status"])
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(result, indent=2))
        return

    print("\nRunning real inference (model.predict only -- no training)...")
    val_delta_pred = model.predict(X_val, verbose=0).ravel()
    val_abs_pred = np.clip(dataset["val_window_mean"] + val_delta_pred, 0.0, 1.0)
    val_abs_true = dataset["y_val_abs"]
    val_baseline_pred = dataset["val_window_mean"]

    val_mae, val_mse, val_rmse, val_r2 = _metrics(val_abs_true, val_abs_pred)
    base_mae, base_mse, base_rmse, base_r2 = _metrics(val_abs_true, val_baseline_pred)

    if n_train > 0:
        train_delta_pred = model.predict(X_train, verbose=0).ravel()
        train_abs_pred = np.clip(dataset["train_window_mean"] + train_delta_pred, 0.0, 1.0)
        train_mae, train_mse, train_rmse, train_r2 = _metrics(dataset["y_train_abs"], train_abs_pred)
    else:
        train_mae = train_mse = train_rmse = train_r2 = None

    print("\n" + "=" * 70)
    print("METRIC: MAE (this is a regression model -- prediction_score is NOT an accuracy percentage)")
    print(f"VALIDATION  -- MAE={val_mae:.5f} MSE={val_mse:.5f} RMSE={val_rmse:.5f} "
          f"R2={'N/A (needs >=2 samples)' if val_r2 is None else f'{val_r2:.4f}'}  "
          f"(~{val_mae*100:.2f} engagement points)")
    print(f"NAIVE BASELINE (predict window mean) on the SAME val set -- "
          f"MAE={base_mae:.5f} RMSE={base_rmse:.5f}  (~{base_mae*100:.2f} points)")
    if train_mae is not None:
        print(f"TRAINING    -- MAE={train_mae:.5f} RMSE={train_rmse:.5f}  "
              f"(reported separately -- NOT validation performance)")
    print("=" * 70)

    if n_val < MIN_VAL_EXAMPLES_FOR_RELIABLE_EVAL:
        reliability = "STATISTICALLY INSUFFICIENT"
        print(f"\n*** STATISTICALLY INSUFFICIENT FOR RELIABLE EVALUATION ***")
        print(f"n={n_val} validation example(s) from {len(val_groups)} student(s) is not enough")
        print(f"to compute a meaningful MAE/R2 -- a single point cannot establish variance,")
        print(f"and R2 is mathematically undefined below 2 points. The number above is REAL")
        print(f"(genuinely computed, not fabricated) but must NOT be reported as evidence the")
        print(f"model generalizes. Training's own bar for even attempting a fit is")
        print(f"MIN_TRAINING_EXAMPLES={MIN_TRAINING_EXAMPLES}, MIN_GROUPS_PER_SPLIT={MIN_GROUPS_PER_SPLIT}")
        print(f"(unchanged, not lowered by this evaluation).")
    elif n_val < 20:
        reliability = "LIMITED EVIDENCE"
    else:
        reliability = "VALID PROJECT-SPECIFIC METRIC"

    result.update({
        "status": reliability,
        "sequence_length_sessions": 6,
        "num_features": 6,
        "eligible_students": dataset["eligible_groups"],
        "train_examples": int(n_train),
        "val_examples": int(n_val),
        "train_students": train_groups,
        "val_students": val_groups,
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
        "training_performance_NOT_validation": None if train_mae is None else {
            "mae": round(float(train_mae), 5),
            "rmse": round(float(train_rmse), 5),
            "r2": None if train_r2 is None else round(float(train_r2), 4),
        },
        "reliability_reason": (
            f"n={n_val} validation example(s) from {len(val_groups)} student(s) -- "
            "R2 undefined/meaningless below 2 points; MAE on 1 point is not a "
            "statistically valid generalization estimate."
            if reliability == "STATISTICALLY INSUFFICIENT" else None
        ),
    })

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, indent=2))
    print(f"\nSaved report to {REPORT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
