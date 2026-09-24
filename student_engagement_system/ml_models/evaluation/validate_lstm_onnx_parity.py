"""Keras-vs-ONNX parity check for both LSTM engagement models.

Validates that the .onnx files written by
ml_models/engagement_prediction/export_lstm_onnx.py produce the same
predictions as the original .keras models, BEFORE anything in production
is pointed at them. Read-only: loads both formats side by side, never
modifies either model file, never writes a report file, never touches
the application's real database.

Checks, per model (live: (None, 30, 1); future: (None, 6, 6)):

  1. Model level -- raw tanh delta output, Keras model.predict() vs
     onnxruntime, on:
       - random inputs in the valid 0-1 range
       - random-length inputs padded/truncated by the service's OWN
         _build_model_input() / _build_future_model_input()
       - hand-picked edge cases (all 0, all 1, near-threshold constants,
         alternating extremes, steps, minimum-length padding)
       - REAL sequences reconstructed from engagement_records, shaped by
         the service's own input builders
     plus a batch-size-1 subset (exactly how production calls predict()).
     Pass: max |delta_keras - delta_onnx| <= DELTA_TOLERANCE.

  2. Service level -- the service's own post-processing applied to both
     outputs: (window_mean + delta) * 100, clamped to 0-100, round(.., 2),
     and (live model) the < ATTENTION_DROP_THRESHOLD attention-drop flag.
     Pass: attention-drop flag never differs; any rounded-score
     difference is listed and must be <= SCORE_TOLERANCE (one rounding
     step at a .xx5 boundary).

  3. Evaluation metrics -- the same datasets ml_models/evaluation/
     evaluate_engagement_lstm.py and evaluate_future_engagement_lstm.py
     build (via each training script's own build_dataset()), with the
     same MAE computation, for both formats. Computed in memory only;
     those scripts' report JSON files are not touched.

DATABASE: data comes from a temporary COPY of backend/student_engagement.db
(the local SQLite database), with DB_BACKEND forced to "sqlite" for this
process only -- so this script never connects to MongoDB Atlas and cannot
modify the real local database either.

Requires (dev machine only): tensorflow, onnxruntime, scikit-learn.

Usage (from student_engagement_system/):
    python ml_models/evaluation/validate_lstm_onnx_parity.py
Exit code 0 = all checks passed, 1 = at least one failed.
"""

import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _PROJECT_ROOT / "backend"
MODEL_DIR = _PROJECT_ROOT / "ml_models" / "engagement_prediction"
SOURCE_DB = _BACKEND_ROOT / "student_engagement.db"

DELTA_TOLERANCE = 1e-5
SCORE_TOLERANCE = 0.01
RANDOM_SAMPLES = 10_000
BATCH1_SAMPLES = 200
SEED = 1234


# ------------------------------------------------------------------
# Environment: isolated DB copy, backend on sys.path, backend/ as cwd
# (config.py's LOG_FOLDER etc. are relative to it, same as the app).
# Must run before anything from backend/ is imported.
# ------------------------------------------------------------------
def _prepare_environment() -> Path:
    workdir = Path(tempfile.mkdtemp(prefix="lstm_parity_"))
    db_copy = workdir / "student_engagement.db"
    shutil.copy2(SOURCE_DB, db_copy)

    os.environ["DB_BACKEND"] = "sqlite"
    os.environ["DATABASE_NAME"] = str(db_copy)  # absolute: BASE_DIR / abs == abs

    # backend/ must come BEFORE the project root: the project root has its
    # own unrelated top-level `database/` package that would otherwise
    # shadow backend/database/ (same caveat as train_lstm.py's sys.path
    # comment). The project root is still needed for `ml_models.*`.
    if str(_BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(_BACKEND_ROOT))
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.append(str(_PROJECT_ROOT))
    os.chdir(_BACKEND_ROOT)
    return db_copy


def _load_pair(keras_name: str, onnx_name: str):
    import onnxruntime as ort
    from tensorflow.keras.models import load_model

    keras_model = load_model(MODEL_DIR / keras_name)

    # Same session options the production ONNX sessions use (ai_service.py
    # / onnx_emotion_predictor.py) -- memory-only settings, no numeric effect.
    options = ort.SessionOptions()
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    session = ort.InferenceSession(
        str(MODEL_DIR / onnx_name), sess_options=options, providers=["CPUExecutionProvider"]
    )
    input_name = session.get_inputs()[0].name

    def keras_fn(x):
        return keras_model.predict(x, verbose=0).ravel()

    def onnx_fn(x):
        return session.run(None, {input_name: x})[0].ravel()

    return keras_fn, onnx_fn


def _service_score(window_mean: float, delta: float) -> float:
    """Exactly the service's post-processing (predict() and
    _compute_future_prediction()): Python floats, clamp, round(.., 2)."""
    predicted = (float(window_mean) + float(delta)) * 100.0
    predicted = max(0.0, min(100.0, predicted))
    return round(predicted, 2)


def _compare(label, X, window_means, keras_fn, onnx_fn, threshold=None):
    X = np.ascontiguousarray(X, dtype="float32")
    k = keras_fn(X)
    o = onnx_fn(X)
    diff = np.abs(k.astype("float64") - o.astype("float64"))

    score_mismatches = []
    flag_mismatches = 0
    for i in range(len(X)):
        ks = _service_score(window_means[i], k[i])
        os_ = _service_score(window_means[i], o[i])
        if ks != os_:
            score_mismatches.append((i, ks, os_))
        if threshold is not None and (ks < threshold) != (os_ < threshold):
            flag_mismatches += 1

    worst_score = max((abs(a - b) for _, a, b in score_mismatches), default=0.0)
    passed = (
        diff.max() <= DELTA_TOLERANCE
        and flag_mismatches == 0
        and worst_score <= SCORE_TOLERANCE + 1e-9
    )
    return {
        "label": label,
        "n": len(X),
        "max_delta_diff": float(diff.max()),
        "mean_delta_diff": float(diff.mean()),
        "score_mismatches": score_mismatches,
        "worst_score_diff": worst_score,
        "flag_mismatches": flag_mismatches if threshold is not None else None,
        "passed": bool(passed),
    }


def _compare_batch1(label, X, window_means, keras_fn, onnx_fn, threshold, rng):
    """Batch-size-1 calls, one sample at a time -- how production calls it."""
    idx = rng.choice(len(X), size=min(BATCH1_SAMPLES, len(X)), replace=False)
    k = np.array([keras_fn(X[i:i + 1])[0] for i in idx])
    o = np.array([onnx_fn(X[i:i + 1])[0] for i in idx])
    sub_means = [window_means[i] for i in idx]

    result = _compare(label, X[idx], sub_means, lambda _x: k, lambda _x: o, threshold)
    return result


# ------------------------------------------------------------------
# Live model inputs
# ------------------------------------------------------------------
def _live_inputs_random(service, rng):
    X = rng.uniform(0.0, 1.0, size=(RANDOM_SAMPLES // 2, 30, 1)).astype("float32")
    means = X.reshape(len(X), -1).mean(axis=1)

    built, built_means = [], []
    for _ in range(RANDOM_SAMPLES // 2):
        n = int(rng.integers(service.MIN_SEQUENCE_LENGTH, 46))
        scores = list(rng.uniform(0.0, 100.0, size=n))
        x, m = service.EngagementPredictionService._build_model_input(scores)
        built.append(x[0])
        built_means.append(m)
    return X, list(means), np.stack(built), built_means


def _live_inputs_edge(service):
    L = service.MIN_SEQUENCE_LENGTH
    cases = {
        "all 0": [0.0] * 30,
        "all 100": [100.0] * 30,
        "all 40 (threshold)": [40.0] * 30,
        "all 70 (stable)": [70.0] * 30,
        "alternating 0/100": [0.0, 100.0] * 15,
        "step 100->0": [100.0] * 15 + [0.0] * 15,
        "step 0->100": [0.0] * 15 + [100.0] * 15,
        "ramp 0->100": list(np.linspace(0, 100, 30)),
        f"min length ({L}) padded": list(np.linspace(20, 90, L)),
        f"min length ({L}) all 40": [40.0] * L,
        "45 samples truncated": list(np.linspace(100, 0, 45)),
    }
    xs, means, names = [], [], []
    for name, scores in cases.items():
        x, m = service.EngagementPredictionService._build_model_input(scores)
        xs.append(x[0])
        means.append(m)
        names.append(name)
    return np.stack(xs), means, names


def _live_inputs_real(service, db_copy: Path):
    """Replays _collect_sequence() at every recorded frame: this student's
    own records for this session in the SEQUENCE_WINDOW_SECONDS before that
    frame, no-person frames excluded, skipped when the latest frame is
    no-person or fewer than MIN_SEQUENCE_LENGTH valid scores exist -- i.e.
    every input predict() would actually have fed the model."""
    conn = sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT session_id, student_id, timestamp, engagement_score, engagement_status "
        "FROM engagement_records ORDER BY session_id, student_id, timestamp"
    ).fetchall()
    conn.close()

    groups = {}
    for session_id, student_id, ts, score, status in rows:
        groups.setdefault((session_id, student_id), []).append(
            (datetime.fromisoformat(str(ts)), score, status)
        )

    window = timedelta(seconds=service.SEQUENCE_WINDOW_SECONDS)
    xs, means = [], []
    for records in groups.values():
        start = 0
        for end in range(len(records)):
            now = records[end][0]
            while records[start][0] < now - window:
                start += 1
            recent = records[start:end + 1]
            if recent[-1][2] == service.NO_PERSON_STATUS:
                continue
            scores = [
                float(s) for _, s, st in recent
                if st != service.NO_PERSON_STATUS and s is not None
            ]
            if len(scores) < service.MIN_SEQUENCE_LENGTH:
                continue
            x, m = service.EngagementPredictionService._build_model_input(scores)
            xs.append(x[0])
            means.append(m)
    return np.stack(xs), means, len(groups)


# ------------------------------------------------------------------
# Future model inputs
# ------------------------------------------------------------------
def _session(engagement_mean, rates):
    names = [name for name, _ in _future_features()]
    return {
        "engagement_mean": engagement_mean,
        "alert_rates": dict(zip(names, rates)),
    }


def _future_features():
    from services.engagement_prediction_service import FUTURE_ALERT_FEATURES
    return FUTURE_ALERT_FEATURES


def _future_inputs_random(service, rng):
    n_feat = service.FUTURE_NUM_FEATURES
    X = rng.uniform(0.0, 1.0, size=(RANDOM_SAMPLES // 2, 6, n_feat)).astype("float32")
    means = list(X[:, :, 0].mean(axis=1))

    built, built_means = [], []
    for _ in range(RANDOM_SAMPLES // 2):
        n = int(rng.integers(service.FUTURE_MIN_SESSIONS, 7))
        window = [
            _session(float(rng.uniform(0, 100)), list(rng.uniform(0, 1, size=n_feat - 1)))
            for _ in range(n)
        ]
        x, m = service.EngagementPredictionService._build_future_model_input(window)
        built.append(x[0])
        built_means.append(m)
    return X, means, np.stack(built), built_means


def _future_inputs_edge(service):
    n_rates = service.FUTURE_NUM_FEATURES - 1
    zero, one = [0.0] * n_rates, [1.0] * n_rates
    absent = [1.0] + [0.0] * (n_rates - 1)  # no_person_rate = 1
    cases = {
        "6 sessions all 0": [_session(0.0, zero)] * 6,
        "6 sessions engagement 100, no alerts": [_session(100.0, zero)] * 6,
        "6 sessions all rates 1": [_session(50.0, one)] * 6,
        "absent every session": [_session(0.0, absent)] * 6,
        "3 sessions padded to 6": [
            _session(80.0, zero), _session(60.0, [0.1] * n_rates), _session(40.0, [0.2] * n_rates)
        ],
        "alternating 0/100": [_session(0.0, zero), _session(100.0, zero)] * 3,
        "all 40 (threshold)": [_session(40.0, zero)] * 6,
    }
    xs, means, names = [], [], []
    for name, window in cases.items():
        x, m = service.EngagementPredictionService._build_future_model_input(window)
        xs.append(x[0])
        means.append(m)
        names.append(name)
    return np.stack(xs), means, names


def _future_inputs_real(service):
    """Every input _compute_future_prediction() would build for every
    student, at every point in their completed-session history (each
    prefix of >= FUTURE_MIN_SESSIONS sessions, last 6 of it)."""
    from database.database import SessionLocal
    from models.student import Student

    db = SessionLocal()
    try:
        student_ids = [row[0] for row in db.query(Student.student_id).all()]
        xs, means, students_used = [], [], 0
        for student_id in student_ids:
            history = service.EngagementPredictionService._build_student_session_history(
                db, student_id
            )
            if len(history) < service.FUTURE_MIN_SESSIONS:
                continue
            students_used += 1
            for k in range(service.FUTURE_MIN_SESSIONS, len(history) + 1):
                window = history[:k][-service.FUTURE_SEQUENCE_LENGTH_SESSIONS:]
                x, m = service.EngagementPredictionService._build_future_model_input(window)
                xs.append(x[0])
                means.append(m)
    finally:
        db.close()
    if not xs:
        return None, [], 0
    return np.stack(xs), means, students_used


# ------------------------------------------------------------------
# Evaluation-script metrics (in memory only)
# ------------------------------------------------------------------
def _eval_metrics(dataset, keras_fn, onnx_fn, reshape=None):
    from sklearn.metrics import mean_absolute_error

    out = {}
    for split in ("val", "train"):
        X = dataset[f"X_{split}"]
        if len(X) == 0:
            continue
        if reshape:
            X = X.reshape(-1, *reshape)
        X = np.ascontiguousarray(X, dtype="float32")
        truth = dataset[f"y_{split}_abs"]
        wm = dataset[f"{split}_window_mean"]
        mae_k = mean_absolute_error(truth, np.clip(wm + keras_fn(X), 0.0, 1.0))
        mae_o = mean_absolute_error(truth, np.clip(wm + onnx_fn(X), 0.0, 1.0))
        out[split] = (len(X), mae_k, mae_o)
    return out


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------
def _print_result(r, case_names=None):
    status = "PASS" if r["passed"] else "FAIL"
    flag = "" if r["flag_mismatches"] is None else f"  flag mismatches={r['flag_mismatches']}"
    print(
        f"  [{status}] {r['label']:<44} n={r['n']:>6}  "
        f"max|d|={r['max_delta_diff']:.2e}  mean|d|={r['mean_delta_diff']:.2e}  "
        f"rounded-score diffs={len(r['score_mismatches'])}{flag}"
    )
    for i, a, b in r["score_mismatches"][:10]:
        where = case_names[i] if case_names else f"#{i}"
        print(f"         rounding-boundary case {where}: keras={a}  onnx={b}")


def _print_eval(name, metrics):
    for split, (n, mae_k, mae_o) in metrics.items():
        same = abs(mae_k - mae_o) < 1e-6
        print(
            f"  [{'PASS' if same else 'FAIL'}] {name} {split:<5} n={n:>5}  "
            f"MAE keras={mae_k:.6f}  onnx={mae_o:.6f}  |diff|={abs(mae_k - mae_o):.2e}"
        )
    return all(abs(k - o) < 1e-6 for _, k, o in metrics.values())


def main() -> int:
    db_copy = _prepare_environment()
    try:
        return _run(db_copy)
    finally:
        # Release SQLAlchemy's pooled connections first -- on Windows an
        # open SQLite handle otherwise blocks deleting the copy.
        engine_module = sys.modules.get("database.database")
        if engine_module is not None:
            engine_module.engine.dispose()
        shutil.rmtree(db_copy.parent, ignore_errors=True)


def _run(db_copy: Path) -> int:
    import services.engagement_prediction_service as service

    rng = np.random.default_rng(SEED)
    results, all_passed = [], True

    print("=" * 100)
    print("LIVE MODEL  lstm_engagement_model.keras  vs  lstm_engagement_model.onnx")
    keras_fn, onnx_fn = _load_pair("lstm_engagement_model.keras", "lstm_engagement_model.onnx")
    thr = service.ATTENTION_DROP_THRESHOLD

    Xr, mr, Xb, mb = _live_inputs_random(service, rng)
    Xe, me, names = _live_inputs_edge(service)
    Xreal, mreal, n_groups = _live_inputs_real(service, db_copy)
    live = [
        (_compare("random uniform 0-1", Xr, mr, keras_fn, onnx_fn, thr), None),
        (_compare("random length via _build_model_input", Xb, mb, keras_fn, onnx_fn, thr), None),
        (_compare("edge cases", Xe, me, keras_fn, onnx_fn, thr), names),
        (_compare(f"REAL replayed predict() inputs ({n_groups} groups)", Xreal, mreal,
                  keras_fn, onnx_fn, thr), None),
        (_compare_batch1("REAL, batch size 1 (production call shape)", Xreal, mreal,
                         keras_fn, onnx_fn, thr, rng), None),
    ]
    for r, n in live:
        _print_result(r, n)
        results.append(r)

    print("  evaluation-script metrics (evaluate_engagement_lstm.py's dataset):")
    from ml_models.engagement_prediction.train_lstm import build_dataset as build_live
    try:
        ok = _print_eval("live", _eval_metrics(build_live(), keras_fn, onnx_fn, reshape=(30, 1)))
        all_passed &= ok
    except RuntimeError as exc:
        print(f"  [SKIP] dataset not buildable: {exc}")

    print("=" * 100)
    print("FUTURE MODEL  lstm_future_engagement_model.keras  vs  lstm_future_engagement_model.onnx")
    keras_fn, onnx_fn = _load_pair(
        "lstm_future_engagement_model.keras", "lstm_future_engagement_model.onnx"
    )

    Xr, mr, Xb, mb = _future_inputs_random(service, rng)
    Xe, me, names = _future_inputs_edge(service)
    Xreal, mreal, n_students = _future_inputs_real(service)
    future = [
        (_compare("random uniform 0-1", Xr, mr, keras_fn, onnx_fn), None),
        (_compare("random 3-6 sessions via _build_future_model_input", Xb, mb,
                  keras_fn, onnx_fn), None),
        (_compare("edge cases", Xe, me, keras_fn, onnx_fn), names),
    ]
    if Xreal is not None:
        future += [
            (_compare(f"REAL session histories ({n_students} students)", Xreal, mreal,
                      keras_fn, onnx_fn), None),
            (_compare_batch1("REAL, batch size 1 (production call shape)", Xreal, mreal,
                             keras_fn, onnx_fn, None, rng), None),
        ]
    else:
        print("  [SKIP] no student has enough completed sessions for a real input")
    for r, n in future:
        _print_result(r, n)
        results.append(r)

    print("  evaluation-script metrics (evaluate_future_engagement_lstm.py's dataset):")
    from ml_models.engagement_prediction.train_future_engagement_lstm import (
        build_dataset as build_future,
    )
    try:
        ok = _print_eval("future", _eval_metrics(build_future(), keras_fn, onnx_fn))
        all_passed &= ok
    except RuntimeError as exc:
        print(f"  [SKIP] dataset not buildable: {exc}")

    all_passed &= all(r["passed"] for r in results)
    print("=" * 100)
    print(f"tolerances: raw delta <= {DELTA_TOLERANCE:g}; rounded score <= {SCORE_TOLERANCE} "
          f"(one rounding step); attention-drop flag must match exactly")
    print(f"database: temporary copy {db_copy} (DB_BACKEND=sqlite for this process only)")
    print(f"OVERALL: {'PASS' if all_passed else 'FAIL'}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
