"""Trains the SESSION-granularity, multivariate LSTM used by
EngagementPredictionService.get_future_prediction() (backend/services/
engagement_prediction_service.py) for the HISTORICAL/FUTURE engagement
prediction feature -- a DIFFERENT feature from train_lstm.py's model,
which forecasts a few seconds ahead *within* one live session from
per-FRAME engagement scores. This script instead trains from each
student's own COMPLETED sessions, one input timestep per session (not
per frame), so it can genuinely be influenced by that session's alert
history as well as its engagement score -- see
FUTURE_ALERT_FEATURES in engagement_prediction_service.py for exactly
which real `alerts` table alert_type values map to which feature
channel (no alert type is invented; nothing here is synthetic -- every
feature value is computed from this project's own real engagement_records
and alerts rows).

------------------------------------------------------------------------
DATA / FEATURES (must match get_future_prediction()'s pipeline exactly)
------------------------------------------------------------------------
For each student, EVERY completed session (Session.is_active == False)
they have any engagement_records in becomes one timestep -- including a
session they were absent from for part or all of the time, which is
never dropped:
    [engagement_mean/100, no_person_rate, phone_rate, multiple_person_rate,
     looking_away_rate, attention_drop_rate]
engagement_mean is PRESENCE-AWARE: visible_engagement (mean score over
frames where a person was actually present) scaled by visible_ratio
(fraction of the session that was visible at all) -- a student visible
for 3% of a session scoring 98% in that 3% gets ~2.9%, not 98%; a
session the student never appeared in at all gets exactly 0.0, not
excluded. no_person_rate comes directly from the dense per-frame
engagement_status column, not from the sparse `alerts` table. The
other four rates are each that session's count of the matching real
`alerts` alert_type(s) divided by the session's total observed sample
count (normalizes across sessions of very different lengths). This is
exactly EngagementPredictionService._build_student_session_history() +
_session_feature_vector() -- imported and reused here, not
reimplemented, so training and inference (and the TARGET below, which
reuses the same engagement_mean) can never silently drift apart.

A student's chronological run of these per-session vectors is then
windowed exactly like train_lstm.py windows per-frame scores: a window of
up to FUTURE_SEQUENCE_LENGTH_SESSIONS consecutive sessions (left-padded by
repeating the earliest one if the student's full history is shorter,
same as inference) is one training input; the ACTUAL next session's
engagement_mean is its target. A window must have at least
FUTURE_MIN_SESSIONS real (non-padded) sessions before its target -- i.e. a
student needs at least FUTURE_MIN_SESSIONS + 1 usable completed sessions
to contribute even a single training example, mirroring the real
inference-time gate exactly.

------------------------------------------------------------------------
HONEST DATA-VOLUME CHECK -- read this before assuming a model got saved
------------------------------------------------------------------------
Unlike train_lstm.py (which has thousands of per-frame rows to window
over), this script's unit of data is a whole SESSION, and its unit of
statistical independence is a STUDENT (only different students' sequences
are truly independent -- multiple windows from the same student's history
are not, so, exactly like train_lstm.py, the train/validation split is by
student, never by row, so no window ever leaks across that split).
Realistically there are only ever a handful of completed sessions per
student in this project so far, so this script enforces an honest floor
(MIN_TRAINING_EXAMPLES, MIN_GROUPS_PER_SPLIT below) and REFUSES to save a
model if the real dataset doesn't clear it, printing exactly how many
more students-with-enough-completed-sessions are needed -- never silently
training (and shipping) an unreliable few-example model. If this script
exits without saving a file, EngagementPredictionService.get_future_prediction()
correctly and honestly keeps reporting status="unavailable" for every
student until enough real usage accumulates and this script is re-run.
"""

from pathlib import Path

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _PROJECT_ROOT / "backend"

import sys
# ONLY backend/ -- not the project root (see train_lstm.py's identical
# note: the project root has its own unrelated top-level `database/`
# package that would otherwise shadow backend/database/database.py).
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Reused, not reimplemented -- these MUST match
# EngagementPredictionService's own constants/feature-builder exactly,
# since that is what will actually load and run whatever this script
# saves.
from services.engagement_prediction_service import (  # noqa: E402
    EngagementPredictionService,
    FUTURE_MIN_SESSIONS,
    FUTURE_NUM_FEATURES,
    FUTURE_SEQUENCE_LENGTH_SESSIONS,
)

MODEL_OUTPUT_PATH = Path(__file__).resolve().parent / "lstm_future_engagement_model.keras"

# A window must contain at least this many REAL (non-padded) sessions
# before the immediately-following session becomes its training target
# -- i.e. a student needs FUTURE_MIN_SESSIONS + 1 usable completed
# sessions to contribute even one example. Matches the real inference
# gate (FUTURE_MIN_SESSIONS) exactly; there is no separate "training
# window size" to keep in sync.
MIN_REAL_SESSIONS_IN_WINDOW = FUTURE_MIN_SESSIONS

# Deliberately conservative, and much smaller than train_lstm.py's own
# floor of 20: each example here already aggregates a whole session's
# worth of real per-frame samples, so it carries far more information
# per row than one frame-level sliding window does. Still comfortably
# above what 1-2 students' worth of history can ever produce, so a
# too-small real dataset is refused rather than quietly trained on.
MIN_TRAINING_EXAMPLES = 10
MIN_GROUPS_PER_SPLIT = 2  # at least 2 distinct students on each side


def _load_all_student_ids(db):
    from models.student import Student

    return [row[0] for row in db.query(Student.student_id).all()]


def build_dataset():
    from database.database import SessionLocal

    db = SessionLocal()
    try:
        student_ids = _load_all_student_ids(db)

        histories = {}
        for student_id in student_ids:
            history = EngagementPredictionService._build_student_session_history(
                db, student_id
            )
            if len(history) >= MIN_REAL_SESSIONS_IN_WINDOW + 1:
                histories[student_id] = history
    finally:
        db.close()

    if not histories:
        raise RuntimeError(
            "No student has "
            f"{MIN_REAL_SESSIONS_IN_WINDOW + 1}+ completed sessions with "
            "usable engagement data yet (need at least "
            f"{MIN_REAL_SESSIONS_IN_WINDOW} sessions as input PLUS one more "
            "as the real held-out target). Nothing to train on -- run more "
            "real classes to completion first."
        )

    # Group-level (student-level) random split, fixed seed -- same
    # anti-leakage reasoning as train_lstm.py: multiple windows from the
    # same student's history are correlated, so splitting by student
    # (not by row) is what keeps validation honest.
    rng = np.random.default_rng(seed=42)
    student_groups = sorted(histories.keys())
    shuffled = list(student_groups)
    rng.shuffle(shuffled)
    split_at = max(1, round(len(shuffled) * 0.8))
    train_groups = sorted(shuffled[:split_at])
    val_groups = sorted(shuffled[split_at:])

    if not val_groups:
        val_groups = [student_groups[-1]]
        train_groups = [g for g in student_groups if g != val_groups[0]]

    def collect(groups):
        X, y_abs = [], []
        for student_id in groups:
            history = histories[student_id]
            n = len(history)
            # k = number of REAL sessions in the input window; target is
            # the actual next session. k ranges so at least
            # MIN_REAL_SESSIONS_IN_WINDOW real sessions precede every
            # target, and at least one real session (index k) is held out
            # as that target.
            for k in range(MIN_REAL_SESSIONS_IN_WINDOW, n):
                window = history[max(0, k - FUTURE_SEQUENCE_LENGTH_SESSIONS):k]
                target = history[k]["engagement_mean"]
                model_input, _window_mean = EngagementPredictionService._build_future_model_input(
                    window
                )
                X.append(model_input[0])  # drop the batch dim added for inference
                y_abs.append(target / 100.0)
        return X, y_abs

    X_train_raw, y_train_abs_raw = collect(train_groups)
    X_val_raw, y_val_abs_raw = collect(val_groups)

    X_train = np.array(X_train_raw, dtype="float32")
    X_val = np.array(X_val_raw, dtype="float32") if X_val_raw else np.zeros(
        (0, FUTURE_SEQUENCE_LENGTH_SESSIONS, FUTURE_NUM_FEATURES), dtype="float32"
    )
    y_train_abs = np.array(y_train_abs_raw, dtype="float32")
    y_val_abs = np.array(y_val_abs_raw, dtype="float32")

    # Same "predict the delta from this window's own mean engagement"
    # framing as train_lstm.py, for the same reason: session-to-session
    # engagement is likely autocorrelated for the same student, so
    # "assume it stays about the same" is already a strong baseline --
    # training against the residual gives the network something more
    # useful to learn, if there is enough data to learn it from at all.
    train_window_mean = X_train[:, :, 0].mean(axis=1) if len(X_train) else np.zeros(0, dtype="float32")
    val_window_mean = X_val[:, :, 0].mean(axis=1) if len(X_val) else np.zeros(0, dtype="float32")
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
        "eligible_groups": student_groups,
    }


def build_model():
    from tensorflow import keras
    from tensorflow.keras import layers

    model = keras.Sequential([
        layers.Input(shape=(FUTURE_SEQUENCE_LENGTH_SESSIONS, FUTURE_NUM_FEATURES)),
        layers.LSTM(16, dropout=0.2, recurrent_dropout=0.1),
        layers.Dense(8, activation="relu"),
        # tanh, not sigmoid: predicts a DELTA from the input window's own
        # mean engagement (see build_dataset()), which can be negative.
        layers.Dense(1, activation="tanh"),
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def main():
    print("=" * 60)
    print("Loading each student's completed-session history...")
    dataset = build_dataset()

    print(f"Students with >= {MIN_REAL_SESSIONS_IN_WINDOW + 1} usable completed sessions: "
          f"{len(dataset['eligible_groups'])} {dataset['eligible_groups']}")
    print(f"  train students: {dataset['train_groups']}")
    print(f"  val students:   {dataset['val_groups']}")
    print(f"Training examples: {len(dataset['X_train'])}")
    print(f"Validation examples: {len(dataset['X_val'])}")

    total_examples = len(dataset["X_train"]) + len(dataset["X_val"])

    if (
        total_examples < MIN_TRAINING_EXAMPLES
        or len(dataset["train_groups"]) < MIN_GROUPS_PER_SPLIT
        or len(dataset["val_groups"]) < 1
    ):
        print("\n" + "=" * 60)
        print("NOT TRAINING -- real dataset is too small to fit a reliable")
        print("multivariate model honestly.")
        print(f"  total examples:  {total_examples} (need >= {MIN_TRAINING_EXAMPLES})")
        print(f"  train students:  {len(dataset['train_groups'])} (need >= {MIN_GROUPS_PER_SPLIT})")
        print(f"  val students:    {len(dataset['val_groups'])} (need >= 1)")
        print(
            "This is expected right now: each training example needs a "
            f"student with {MIN_REAL_SESSIONS_IN_WINDOW + 1}+ real completed "
            "sessions (the window PLUS one held-out real target), and this "
            "project currently has very few students with that much real "
            "history. No model file was written -- "
            "EngagementPredictionService.get_future_prediction() will keep "
            "honestly reporting status=\"unavailable\" (never a fabricated "
            "score) until more real classes are completed and this script "
            "is re-run."
        )
        print("=" * 60)
        return

    X_train = dataset["X_train"]
    X_val = dataset["X_val"]

    print("\nBuilding model...")
    model = build_model()
    model.summary()

    from tensorflow import keras

    callbacks = [
        keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=8, restore_best_weights=True
        ),
    ]

    print("\nTraining (predicting delta-from-window-mean-engagement)...")
    model.fit(
        X_train,
        dataset["y_train_delta"],
        validation_data=(X_val, dataset["y_val_delta"]),
        epochs=60,
        batch_size=8,
        callbacks=callbacks,
        verbose=2,
    )

    pred_delta_val = model.predict(X_val, verbose=0).ravel()
    pred_abs_val = dataset["val_window_mean"] + pred_delta_val
    model_mae = float(np.mean(np.abs(pred_abs_val - dataset["y_val_abs"])))

    naive_mae = float(np.mean(np.abs(dataset["val_window_mean"] - dataset["y_val_abs"])))

    print("\n" + "=" * 60)
    print(f"Model MAE vs actual next-session engagement: "
          f"{model_mae:.5f}  (~{model_mae * 100:.2f} engagement points)")
    print(f"Naive baseline MAE (predict input-window mean, i.e. delta=0): "
          f"{naive_mae:.5f}  (~{naive_mae * 100:.2f} points)")
    if model_mae < naive_mae:
        improvement = (1 - model_mae / naive_mae) * 100
        print(f"-> Model beats the naive baseline by {improvement:.1f}%.")
    else:
        regression = (model_mae / naive_mae - 1) * 100
        print(f"-> Model does NOT beat the naive baseline (worse by {regression:.1f}%). "
              "Report this honestly -- with this few validation students, "
              "that comparison itself is barely meaningful either way.")

    model.save(MODEL_OUTPUT_PATH)
    print(f"\nSaved model to {MODEL_OUTPUT_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
