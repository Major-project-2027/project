# Model evaluation (read-only, separate from production)

This directory evaluates the EXISTING production models exactly as they are.
It never modifies `backend/`, `frontend/`, production inference logic, model
weights, thresholds, or the database. It only *loads* the already-saved
model files and runs real inference against real, already-present data.

## What has a real evaluation script here

- `evaluate_emotion_fer2013.py` — production `emotion_model.keras` vs. the
  genuine held-out 15% FER2013 test split (reconstructed with the exact
  seed/procedure used at training time, never before evaluated).
- `evaluate_emotion_ckplus.py` — the same production model against a
  second, independent real dataset (CK+) already present in the project.
- `evaluate_engagement_lstm.py` — production `lstm_engagement_model.keras`
  vs. the real held-out validation split `train_lstm.py` itself already
  builds (imported, not duplicated or modified).
- `evaluate_future_engagement_lstm.py` — production
  `lstm_future_engagement_model.keras` vs. the real held-out student split
  `train_future_engagement_lstm.py` itself already builds.

Run any of them directly (`python ml_models/evaluation/evaluate_*.py`) or
all of them via `python ml_models/evaluation/run_all_evaluations.py`. Each
prints its results and saves a JSON report to `reports/`.

## What does NOT have an evaluation script, and why

See `GROUND_TRUTH_AUDIT.md` — phone detection, multiple-person detection,
looking-away detection, drowsiness, face detection, gaze, blink, and the
custom face-recognition model all lack real project-specific labelled data
(the relevant `datasets/raw/*` directories exist but are empty placeholders,
or — for drowsiness — no such detector exists in the codebase at all). No
labels were fabricated to produce a number for any of these.
