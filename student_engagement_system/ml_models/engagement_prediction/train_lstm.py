"""Trains the LSTM future-engagement model from REAL engagement_records.

This is the model EngagementPredictionService (backend/services/
engagement_prediction_service.py) loads at inference time. There was no
existing LSTM anywhere in this project (see that module's docstring for
the inspection that established this) -- this script is what actually
produces one, from real data already collected by the live AI monitoring
pipeline. It does NOT use synthetic/fabricated engagement values: every
training example is a slice of real engagement_score history written by
services/ai_service.py during actual monitored sessions.

------------------------------------------------------------------------
DATA
------------------------------------------------------------------------
For each (session_id, student_id) -- the same isolation key the live
prediction service uses -- records are read in timestamp order and split
into contiguous "valid runs" at every engagement_status == "No Person
Detected" row (a no-person frame is not a real engagement observation,
so it must not be bridged across when building a sequence -- consistent
with EngagementPredictionService excluding these at inference time too).

From each valid run, sliding windows of SEQUENCE_LENGTH consecutive
engagement scores become one training input; the mean of the next
HORIZON_STEPS scores immediately following that window becomes its
target (a short-horizon future value, smoothed over a few samples rather
than a single noisy point -- more representative of "engagement level
in the next window" than one instant reading).

------------------------------------------------------------------------
HONEST LIMITATIONS (read before trusting this model's predictions)
------------------------------------------------------------------------
- The dataset is SMALL by deep-learning standards: a few thousand rows
  drawn from a handful of real (session, student) pairs, not thousands of
  distinct students. The model can reflect real short-term engagement
  momentum patterns in this data, but it has not seen nearly enough
  distinct people/situations to be a general-purpose predictor of every
  future student's behavior.
- Train/validation are split by (session_id, student_id) GROUP, not by
  random row, specifically so overlapping sliding windows from the same
  session never leak between train and validation -- but with only ~15
  groups total, the validation signal itself is still limited.
- Retraining this script periodically as more real sessions accumulate
  (via the existing engagement_records pipeline) is expected and will
  only require running this script again -- the model file and its
  consumer (EngagementPredictionService) already support that.
"""

from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _PROJECT_ROOT / "backend"

import sys
# ONLY backend/ -- not the project root. The project root has its own
# (unrelated, empty) top-level `database/` package that would otherwise
# shadow backend/database/database.py on sys.path and break this import.
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Must match services/engagement_prediction_service.py's contract exactly
# -- that module reshapes the live sequence to (1, SEQUENCE_LENGTH, 1)
# (padding/truncating as needed) and reconstructs an absolute prediction
# from this model's tanh delta-from-window-mean output as
# (window_mean + predicted_delta). HORIZON_STEPS is reported to callers
# as PREDICTION_HORIZON_SECONDS there (~1 sample/sec observed rate).
SEQUENCE_LENGTH = 30
HORIZON_STEPS = 10
MIN_RUN_LENGTH = SEQUENCE_LENGTH + HORIZON_STEPS
WINDOW_STRIDE = 3

NO_PERSON_STATUS = "No Person Detected"

MODEL_OUTPUT_PATH = Path(__file__).resolve().parent / "lstm_engagement_model.keras"


def _load_records():
    from database.database import SessionLocal
    from models.engagement import EngagementRecord

    db = SessionLocal()
    try:
        rows = (
            db.query(
                EngagementRecord.session_id,
                EngagementRecord.student_id,
                EngagementRecord.timestamp,
                EngagementRecord.engagement_score,
                EngagementRecord.engagement_status,
            )
            .order_by(
                EngagementRecord.session_id,
                EngagementRecord.student_id,
                EngagementRecord.timestamp,
            )
            .all()
        )
    finally:
        db.close()
    return rows


def _build_valid_runs(rows):
    """Group by (session_id, student_id), then split each group's
    ordered scores into contiguous runs, breaking at every no-person
    frame. Returns {(session_id, student_id): [run1_scores, run2_scores, ...]}."""

    groups: dict[tuple, list] = {}
    for session_id, student_id, _timestamp, score, status in rows:
        key = (session_id, student_id)
        groups.setdefault(key, []).append((score, status))

    runs_by_group: dict[tuple, list] = {}
    for key, entries in groups.items():
        runs: list[list[float]] = []
        current: list[float] = []
        for score, status in entries:
            if status == NO_PERSON_STATUS or score is None:
                if current:
                    runs.append(current)
                    current = []
                continue
            current.append(float(score))
        if current:
            runs.append(current)
        runs_by_group[key] = runs

    return runs_by_group


def _extract_windows(scores: list[float]):
    """One valid run -> list of (input_window, target_absolute) pairs."""

    examples = []
    n = len(scores)
    last_start = n - MIN_RUN_LENGTH
    for start in range(0, last_start + 1, WINDOW_STRIDE):
        window = scores[start : start + SEQUENCE_LENGTH]
        horizon = scores[start + SEQUENCE_LENGTH : start + SEQUENCE_LENGTH + HORIZON_STEPS]
        if len(window) != SEQUENCE_LENGTH or len(horizon) != HORIZON_STEPS:
            continue
        target = sum(horizon) / len(horizon)
        examples.append((window, target))
    return examples


def build_dataset():
    rows = _load_records()
    runs_by_group = _build_valid_runs(rows)

    eligible_groups = sorted(
        key for key, runs in runs_by_group.items()
        if any(len(r) >= MIN_RUN_LENGTH for r in runs)
    )

    if not eligible_groups:
        raise RuntimeError(
            "No (session_id, student_id) group has enough contiguous valid "
            f"samples (need >= {MIN_RUN_LENGTH}) to train on. Run more live "
            "monitoring sessions first."
        )

    # Reproducible (fixed-seed) RANDOM group-level split, not a
    # positional one -- an earlier version of this script took "every
    # 5th group by sorted key" for validation, which happened to put all
    # the lower-engagement, higher-variance groups on one side and left
    # training with an unrepresentatively easy, high/flat-engagement
    # slice. Group-level (not row-level) so no sliding window from a
    # training session's run ever overlaps a validation window from the
    # same session.
    rng = np.random.default_rng(seed=42)
    shuffled = list(eligible_groups)
    rng.shuffle(shuffled)
    split_at = max(1, round(len(shuffled) * 0.8))
    train_groups = sorted(shuffled[:split_at])
    val_groups = sorted(shuffled[split_at:])

    if not val_groups:
        val_groups = [eligible_groups[-1]]
        train_groups = [g for g in eligible_groups if g != val_groups[0]]

    def collect(groups):
        X, y_abs = [], []
        for key in groups:
            for run in runs_by_group[key]:
                for window, target in _extract_windows(run):
                    X.append(window)
                    y_abs.append(target)
        return X, y_abs

    X_train_raw, y_train_abs_raw = collect(train_groups)
    X_val_raw, y_val_abs_raw = collect(val_groups)

    X_train = np.array(X_train_raw, dtype="float32") / 100.0
    X_val = np.array(X_val_raw, dtype="float32") / 100.0
    y_train_abs = np.array(y_train_abs_raw, dtype="float32") / 100.0
    y_val_abs = np.array(y_val_abs_raw, dtype="float32") / 100.0

    # The model predicts the CHANGE from the input window's own mean,
    # not the absolute future value. Engagement scores are highly
    # autocorrelated over a 30-40s span, so "assume it stays the same"
    # (predicting the window's own mean, i.e. delta=0) is already a very
    # strong baseline here -- training directly against the absolute
    # value lets a small model largely just learn to copy that baseline
    # without necessarily picking up the residual temporal signal this
    # feature actually needs. Framing the target as a delta forces the
    # network to focus on that residual instead.
    train_window_mean = X_train.mean(axis=1)
    val_window_mean = X_val.mean(axis=1)
    y_train_delta = y_train_abs - train_window_mean
    y_val_delta = y_val_abs - val_window_mean

    return {
        "X_train": X_train,
        "X_val": X_val,
        "y_train_abs": y_train_abs,
        "y_val_abs": y_val_abs,
        "y_train_delta": y_train_delta,
        "y_val_delta": y_val_delta,
        "train_window_mean": train_window_mean,
        "val_window_mean": val_window_mean,
        "train_groups": train_groups,
        "val_groups": val_groups,
        "eligible_groups": eligible_groups,
    }


def build_model():
    from tensorflow import keras
    from tensorflow.keras import layers

    model = keras.Sequential([
        layers.Input(shape=(SEQUENCE_LENGTH, 1)),
        layers.LSTM(32, dropout=0.2, recurrent_dropout=0.1),
        layers.Dense(16, activation="relu"),
        # tanh, not sigmoid: the model predicts a DELTA from the input
        # window's own mean (see build_dataset()), which can be negative.
        layers.Dense(1, activation="tanh"),
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def main():
    print("=" * 60)
    print("Loading engagement_records...")
    dataset = build_dataset()

    print(f"Eligible (session_id, student_id) groups: {len(dataset['eligible_groups'])}")
    print(f"  train groups: {dataset['train_groups']}")
    print(f"  val groups:   {dataset['val_groups']}")
    print(
        f"  train y (absolute) mean/std: {dataset['y_train_abs'].mean():.3f} / {dataset['y_train_abs'].std():.3f}"
    )
    print(
        f"  val y (absolute) mean/std:   {dataset['y_val_abs'].mean():.3f} / {dataset['y_val_abs'].std():.3f}"
    )
    print(f"Training windows: {len(dataset['X_train'])}")
    print(f"Validation windows: {len(dataset['X_val'])}")

    if len(dataset["X_train"]) < 20:
        raise RuntimeError(
            f"Only {len(dataset['X_train'])} training windows available -- "
            "too few to train a meaningful model. Collect more live "
            "monitoring data first."
        )

    X_train = dataset["X_train"].reshape(-1, SEQUENCE_LENGTH, 1)
    X_val = dataset["X_val"].reshape(-1, SEQUENCE_LENGTH, 1)

    print("\nBuilding model...")
    model = build_model()
    model.summary()

    from tensorflow import keras

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=8, restore_best_weights=True
        ),
    ]

    print("\nTraining (predicting delta-from-window-mean)...")
    model.fit(
        X_train,
        dataset["y_train_delta"],
        validation_data=(X_val, dataset["y_val_delta"]),
        epochs=60,
        batch_size=32,
        callbacks=callbacks,
        verbose=2,
    )

    # Reconstruct ABSOLUTE predictions (window_mean + predicted delta) to
    # report a real, comparable MAE in engagement-point terms, and to
    # honestly compare against the naive "assume no change" baseline
    # (which is exactly "predicted delta = 0").
    pred_delta_val = model.predict(X_val, verbose=0).ravel()
    pred_abs_val = dataset["val_window_mean"] + pred_delta_val
    model_mae = float(np.mean(np.abs(pred_abs_val - dataset["y_val_abs"])))

    naive_mae = float(np.mean(np.abs(dataset["val_window_mean"] - dataset["y_val_abs"])))

    print("\n" + "=" * 60)
    print(f"Model MAE (window_mean + predicted delta) vs actual future value: "
          f"{model_mae:.5f}  (~{model_mae * 100:.2f} engagement points)")
    print(f"Naive baseline MAE (predict input-window mean, i.e. delta=0): "
          f"{naive_mae:.5f}  (~{naive_mae * 100:.2f} points)")
    if model_mae < naive_mae:
        improvement = (1 - model_mae / naive_mae) * 100
        print(f"-> Model beats the naive baseline by {improvement:.1f}%.")
    else:
        regression = (model_mae / naive_mae - 1) * 100
        print(f"-> Model does NOT beat the naive baseline (worse by {regression:.1f}%). "
              "Report this honestly -- see the module docstring's data-volume caveats.")

    model.save(MODEL_OUTPUT_PATH)
    print(f"\nSaved model to {MODEL_OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
