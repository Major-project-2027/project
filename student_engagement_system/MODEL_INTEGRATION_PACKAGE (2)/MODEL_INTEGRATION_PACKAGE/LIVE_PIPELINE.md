# Live Pipeline — What The Code Actually Does (Not What The Docs Describe)

This document traces the real, current source code, starting from the
application's actual entry points. It intentionally does **not** describe
the architecture document's intended design where that design isn't yet
implemented — every claim below is backed by a specific file.

## Summary finding

**There is no end-to-end live pipeline currently wired up in this project.**
Five of six ML components are fully implemented and independently working
(verified in MODEL_INVENTORY.md). Each has a correctly-written Celery task
wrapper that loads its predictor and would produce correct output if
invoked. But nothing in the codebase currently invokes any of them — there
is no API route, WebSocket handler, or scheduled job that calls
`.delay()`/`apply_async()` on any of these tasks anywhere in `backend/`.

This is not a guess — it is the result of:
```
grep -rE "\.delay\(|apply_async|analyze_emotion|detect_objects|verify_face|analyze_gaze_headpose|analyze_voice_window|predict_attention_drop" backend/
```
which returns matches **only inside the six task-definition files
themselves** (`backend/worker/tasks/*.py`) — no caller anywhere else in the
`backend/` tree.

## 1. Entry point

`backend/app/main.py` — a FastAPI app with exactly one route:
```python
@app.get("/healthz", tags=["infrastructure"])
async def healthz() -> dict:
    return {"status": "ok", "environment": settings.APP_ENV}
```
The file's own docstring says so explicitly: *"This is intentionally NOT
the full backend API... Business routers for the modules under
backend/app/modules/* should be registered here in a later phase."*

## 2. Business modules — all empty

`backend/app/modules/{auth,core_app,ingestion,alerts,dashboard_push,reporting}/__init__.py`
are each **0 bytes**. There is no ingestion WebSocket handler, no session
route, no alert-dispatch code, nothing that would receive a video/audio
frame from a client and route it toward the Celery workers.

## 3. Frontend — placeholders only

`frontend/apps/student-portal/`, `frontend/apps/teacher-portal/`, and
`frontend/shared-ui/` each contain only a `.gitkeep` file. No frontend code
exists that could be a caller either.

## 4. What DOES work: the Celery task layer

`backend/worker/celery_app.py` configures a real Celery app and
autodiscovers tasks under `backend/worker/tasks/`. Each task file
(verified by reading and by live-testing the underlying predictor — see
MODEL_INVENTORY.md) correctly:

1. Adds `ml/training/<module>/` to `sys.path` (`common.py::load_module_dir`) — a deliberate shim because each ML module was built standalone with unqualified `import config`/`import predictor` statements.
2. Imports and lazily instantiates that module's real predictor class as a per-worker-process singleton.
3. Decodes the incoming frame/audio (`common.py::decode_frame` / `decode_audio_window`).
4. Calls the predictor and shapes the result into a dict keyed by `session_id`/`student_id`/`timestamp`, ready for a downstream Feature Aggregator that does not yet exist.

| Task | File | Predictor it calls | Registered Celery task name |
|---|---|---|---|
| Emotion | `backend/worker/tasks/emotion_task.py` | `ml/training/emotion_model/predictor.py::EmotionPredictor` | `ml.emotion.analyze_frame` |
| Object detection | `backend/worker/tasks/object_detection_task.py` | `ml/training/object_detection/predictor.py::ObjectDetectionPredictor` | `ml.object_detection.analyze_frame` |
| Gaze/head-pose | `backend/worker/tasks/gaze_headpose_task.py` | `ml/training/gaze_headpose/predictor.py::GazeHeadPosePredictor` | `ml.gaze_headpose.analyze_frame` |
| Face auth | `backend/worker/tasks/face_auth_task.py` | `ml/training/face_authentication/predictor.py::FaceAuthenticator` | `ml.face_auth.verify_frame` |
| Voice | `backend/worker/tasks/voice_task.py` | `ml/training/voice_analysis/voice_analyzer.py::VoiceAnalyzer` | `ml.voice.analyze_window` + `ml.voice.route_disruption_alert` |
| LSTM | `backend/worker/tasks/lstm_task.py` | none — stub | `ml.lstm.predict_attention_drop` (raises `NotImplementedError` unconditionally) |

## 5. `backend/app/config.py`'s `MODEL_ARTIFACTS` registry is stale/unused

```python
MODEL_ARTIFACTS = {
    "emotion_cnn": MODEL_WEIGHTS_DIR / "emotion_mobilenetv2.onnx",
    "object_detector": MODEL_WEIGHTS_DIR / "yolov8n.onnx",
    "lstm_engagement": MODEL_WEIGHTS_DIR / "lstm_engagement.onnx",
    "voice_disruption": MODEL_WEIGHTS_DIR / "voice_analysis" / "speech_confidence_calibrator.joblib",
    "voice_disruption_scaler": MODEL_WEIGHTS_DIR / "voice_analysis" / "feature_scaler.joblib",
}
```
None of these paths exist on disk (`models/weights/` contains only
`.gitkeep`), and **none of the task wrapper files import or reference
`MODEL_ARTIFACTS` at all** — each task loads its predictor via
`load_module_dir()` instead, which resolves paths through each module's own
`config.py` (e.g. `models/emotion/emotion_model.keras`, not
`models/weights/emotion_mobilenetv2.onnx`). This registry appears to be a
leftover from an earlier planning phase (its comments say "ONNX... per the
Revised Architecture's latency budget") that was never updated once the
five modules were actually built in their current (non-ONNX, except voice's
joblib) formats. **Do not use `MODEL_ARTIFACTS` as a source of truth for
where the real model files are** — use each module's own `config.py`
instead (documented per-model in MODEL_INVENTORY.md).

## 6. The intended (but unbuilt) fusion pipeline

`backend/app/config.py` does define the intended fusion formula, which is
real, current code (not stale) — this is what a future Feature Aggregator
would need to implement:

```python
ENGAGEMENT_FEATURE_WEIGHTS = {
    "eye_focus": 0.30,       # from gaze_headpose's gaze_direction/gaze_confidence
    "emotion": 0.20,         # from emotion's simplified_label
    "head_pose": 0.25,       # from gaze_headpose's head_pose_classification
    "object_detected": 0.15, # from object_detection's object_detected bool
    "multiple_person": 0.10, # from object_detection's multiple_person bool
}
ENGAGEMENT_LEVEL_BANDS = ((0, 40, "low"), (41, 70, "medium"), (71, 100, "high"))
COGNITIVE_STATES = ("focused", "neutral", "distracted", "tired", "confused")
```
Voice's `disruption_detected`/`disruption_confidence` are **deliberately
excluded** from this formula (see MODEL_INVENTORY.md item 5) and instead
feed a separate `classroom_disturbance` alert type
(`backend/app/config.py::ALERT_TYPES`).

**None of this fusion logic is implemented anywhere in the codebase** —
`ml/feature-aggregator/` and `ml/engagement-score-engine/` each contain
only a `.gitkeep`. The weights/bands/states above are configuration values
with no code that reads them yet.

## 7. What a real pipeline would look like once wired up

Based on what each component's own output actually is (not aspirational —
this is literally the union of every task's return dict):

```
Video/audio frame from client (transport: not yet implemented)
        |
        v
[Ingestion — not implemented: backend/app/modules/ingestion is empty]
        |
        +--> ml.emotion.analyze_frame          -> {raw_label, simplified_label, confidence, probabilities}
        +--> ml.object_detection.analyze_frame -> {object_detected, multiple_person, detected_classes}
        +--> ml.gaze_headpose.analyze_frame     -> {gaze_direction, gaze_confidence, head_pose_classification, drowsiness_state, ...}
        +--> ml.face_auth.verify_frame          -> {verified, similarity_score, known_faces_in_frame, ...} (session-start / periodic only, not every frame)
        +--> ml.voice.analyze_window            -> {disruption_detected, disruption_confidence} (routes to alerts, not fusion)
        |
        v
[Feature Aggregator — not implemented: ml/feature-aggregator is empty]
        |
        v
[Engagement Score Engine — not implemented: ml/engagement-score-engine is empty]
   (would apply ENGAGEMENT_FEATURE_WEIGHTS to eye_focus/emotion/head_pose/object_detected/multiple_person)
        |
        v
[LSTM attention-drop predictor — not implemented: ml/training/lstm_engagement is empty, lstm_task.py is a stub]
        |
        v
Final engagement score + cognitive state (not implemented anywhere)
```

## What your friend's project needs to build to actually connect this

1. An ingestion layer (WebSocket or HTTP) that receives frames/audio and calls the five working Celery tasks (or calls the predictor classes directly, if not reusing Celery).
2. A feature aggregator that joins the five workers' outputs by `session_id + student_id + timestamp`.
3. An engagement-score formula implementation (the weights already exist in `backend/app/config.py::ENGAGEMENT_FEATURE_WEIGHTS` — the arithmetic does not).
4. The LSTM attention-drop model itself — genuinely absent, not just unwired (see MODEL_INVENTORY.md item 6).

None of this is included in this package because none of it exists in the
source project to copy.
