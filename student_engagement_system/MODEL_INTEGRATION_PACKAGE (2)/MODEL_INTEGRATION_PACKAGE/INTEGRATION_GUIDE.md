# Integration Guide

This shows exactly how to load and call each model, using the project's
actual classes/functions — not a hypothetical API. Every snippet below was
run successfully against the files in this package (see MODEL_INVENTORY.md
"Test — packaged copy" rows). Install `requirements_models.txt` first.

All five components are stateless-to-load / cheap-to-instantiate-once,
stateful-per-call — instantiate each predictor **once** (e.g. as a
module-level singleton or per-worker-process, exactly like the original
project's own `backend/worker/tasks/*.py` pattern) and reuse it across
frames.

**Quick smoke test after transferring this package to a new machine:**
`samples/emotion_happy.jpg`, `samples/object_detection_phone.jpg`, and
`samples/gaze_headpose_face.jpg` are bundled so you can verify emotion,
object detection, and gaze/head-pose all load and run correctly using
just this package — no access to the original project needed. Feed each
one through the corresponding snippet below in place of your own frame;
expected outputs are in `MODEL_INVENTORY.md`'s "Test — packaged copy" rows.
(Face authentication and voice analysis have no bundled sample — face
auth's test image is real student data, correctly excluded per §12 of
`README.md`, and voice's test uses a synthetic tone generated in code.)

---

## 1. Emotion detection

```python
import os, sys

PACKAGE_ROOT = r"/path/to/MODEL_INTEGRATION_PACKAGE"
os.environ["ENGAGEMENT_REPO_ROOT"] = PACKAGE_ROOT   # config.py reads this env var to
                                                      # resolve models/emotion/emotion_model.keras
                                                      # relative to PACKAGE_ROOT instead of assuming
                                                      # the original project's directory depth
sys.path.insert(0, f"{PACKAGE_ROOT}/inference/emotion")

from predictor import EmotionPredictor

predictor = EmotionPredictor()   # loads models/emotion/emotion_model.keras once
result = predictor.predict(cropped_face_bgr_or_gray_image)
# {"raw_label": "happy", "simplified_label": "Happy", "confidence": 0.91, "probabilities": {...}}
```
**Input:** a cropped face image (`numpy.ndarray`, BGR color or grayscale — face detection/cropping is NOT part of this model, do it upstream, e.g. with the gaze/headpose module's landmark detector, or your own face detector).
**No threshold is applied** — `raw_label`/`simplified_label` are always the argmax; if you need an "uncertain" bucket, threshold on `confidence` yourself.

## 2. Object detection (person + phone + 15 other classes)

```python
import sys
PACKAGE_ROOT = r"/path/to/MODEL_INTEGRATION_PACKAGE"
sys.path.insert(0, f"{PACKAGE_ROOT}/inference/object_detection")

import config
# IMPORTANT: detector.py loads weights by bare filename via Ultralytics'
# YOLO(name) constructor, which resolves against the CURRENT WORKING
# DIRECTORY / Ultralytics' own cache — NOT this package's models/ folder —
# and will silently re-download from GitHub if it can't find a same-named
# file locally. Point it at the packaged weights explicitly before
# instantiating the predictor:
config.PRIMARY_WEIGHTS_SPEED = f"{PACKAGE_ROOT}/models/object_detection/yolo11n.pt"
config.FALLBACK_WEIGHTS_SPEED = f"{PACKAGE_ROOT}/models/object_detection/yolo11n.pt"

from predictor import ObjectDetectionPredictor

predictor = ObjectDetectionPredictor()   # loads the pinned weights exactly once
result = predictor.predict_image(full_frame_bgr)   # NOT cropped — full frame
for d in result.detections:
    print(d.class_name, d.confidence, d.bbox)       # e.g. "Person" 0.843, "Cell Phone" 0.577
print(result.person_count, result.events)            # multi-person / derived heuristic events
```
**Input:** a full (uncropped) BGR frame.
**Confidence threshold 0.35 / NMS IoU 0.45** are baked into `config.py` (`CONFIDENCE_THRESHOLD`, `NMS_IOU_THRESHOLD`) and applied automatically inside `predict_image`.
**For video/streaming with persistent track IDs**, use `predictor.predict_video()` / `predictor.predict_stream()` instead of `predict_image` (see `predictor.py` for the full API — folder batch, webcam demo, and LSTM-ready feature-sequence export are all included).

## 3. Gaze / head-pose / blink / drowsiness

```python
import sys
PACKAGE_ROOT = r"/path/to/MODEL_INTEGRATION_PACKAGE"
# NOTE: this module's own code uses `from ml.training.gaze_headpose import
# config, utils` (a qualified import, unlike every other module in this
# package). To avoid editing any of its source, this package preserves
# that exact subpath under inference/gaze_headpose/ — add THAT directory
# (not inference/gaze_headpose/ml/...) to sys.path:
sys.path.insert(0, f"{PACKAGE_ROOT}/inference/gaze_headpose")

from ml.training.gaze_headpose.predictor import GazeHeadPosePredictor

# Instantiate ONCE PER STUDENT SESSION — it is stateful (adaptive EAR
# threshold, blink counters, temporal smoothers). Call .reset() when
# reusing a pooled instance for a new session.
predictor = GazeHeadPosePredictor()
result = predictor.predict_frame(full_frame_bgr, timestamp=frame_timestamp)
d = result.to_dict()
# {"gaze_direction": "center", "head_pose_classification": "focused",
#  "drowsiness_state": "alert", "ear_average": 0.46, "blink_count": 0, ...}
predictor.close()   # release the MediaPipe FaceMesh graph when done
```
**Input:** a full BGR frame (this module runs its own MediaPipe face-landmark detection — no upstream face crop needed).
**No local weight file to manage** — MediaPipe downloads its own pretrained FaceMesh/Iris models automatically on first use (requires network access the first time only; cached afterward).
**All thresholds** (head-pose angle cutoffs, EAR, drowsiness durations, blink rate) are in `inference/gaze_headpose/ml/training/gaze_headpose/config.py` — override by editing that file's constants before import, or by monkey-patching the `config` module the same way as the object-detection example above.

## 4. Face authentication

```python
import sys
PACKAGE_ROOT = r"/path/to/MODEL_INTEGRATION_PACKAGE"
sys.path.insert(0, f"{PACKAGE_ROOT}/inference/face_authentication")

from predictor import FaceAuthenticator

authenticator = FaceAuthenticator()   # loads ArcFace (via DeepFace, auto-downloaded)
                                       # + the calibrated threshold from
                                       # inference/face_authentication/checkpoints/calibrated_threshold.json
                                       # gallery will be EMPTY — see "Enrollment" below
result = authenticator.authenticate_image(full_frame_bgr)
for r in result.results:
    print(r.student_id, r.accepted, r.similarity_score, r.confidence)
```
**You must enroll your own students before this is useful** — this package deliberately ships **no** student registry or face photos (see README.md "Personal data"). To enroll:
```python
from embedding_model import get_default_embedding_model
from utils import detect_single_face
import json, numpy as np

model = get_default_embedding_model()
face = detect_single_face(enrollment_image_bgr)       # one clear frontal photo per student, several recommended
embedding = model.embed_face(face).embedding

# Build your own student_registry.json (schema, from the original project):
# {"students": [{"student_id": "...", "student_name": "...", "embedding": [...512 floats...],
#                "embedding_model": "ArcFace", "embedding_dim": 512,
#                "num_enrollment_images": N, "registered_at": "<ISO8601>"}]}
```
Then point `StudentGallery` at your file:
```python
from predictor import StudentGallery, FaceAuthenticator
gallery = StudentGallery(registry_path="/path/to/your/student_registry.json")
authenticator = FaceAuthenticator(gallery=gallery)
```
The original project's full enrollment flow (multi-image capture, mean/median aggregation, `MIN_ENROLLMENT_IMAGES_PER_STUDENT=3`) lives in `register_faces.ipynb`, which is **not** copied into this package (it's a notebook-driven enrollment tool, not inference code) — replicate the pattern above, or ask for that notebook specifically if you want the exact original enrollment UX.

## 5. Voice — speech-confidence calibrator

```python
import sys
PACKAGE_ROOT = r"/path/to/MODEL_INTEGRATION_PACKAGE"
sys.path.insert(0, f"{PACKAGE_ROOT}/inference/voice")

from voice_analyzer import VoiceAnalyzer
import numpy as np

analyzer = VoiceAnalyzer(sample_rate=16000)   # auto-selects VAD backend: silero -> webrtc -> energy
                                                # (verified: silero unavailable without torchaudio,
                                                # falls back cleanly to webrtc — see README "Compatibility")
                                                # auto-loads checkpoints/speech_confidence_calibrator.joblib
                                                # + feature_scaler.joblib from inference/voice/checkpoints/

window = your_1_second_16khz_mono_float32_pcm_array   # shape (16000,), values in [-1, 1]
result = analyzer.analyze_window(window, window_start_time_sec=elapsed_seconds_in_stream)
# VoiceAnalysisResult(voice_detected=True, speech_probability=0.87, ...,
#                      disruption_detected=False, disruption_confidence=0.0)
```
**Input:** a 1.0-second (`config.WINDOW_DURATION_SEC`), 16kHz, mono, float32 PCM window in `[-1, 1]`. Use a 0.5s hop (`config.HOP_DURATION_SEC`) for 50%-overlapping sliding windows.
**Use ONLY `disruption_detected`/`disruption_confidence`** if you're replicating this project's fusion contract — they are explicitly documented (both in code and in MODEL_INVENTORY.md) as NOT meant to feed an engagement score or LSTM, only a separate disruption alert.
**Call `analyzer.reset_session_state()`** when starting a new student/session so speaking-duration and noise-floor history don't leak across sessions.

---

## Files that must stay together

| If you copy... | ...you must also copy |
|---|---|
| `models/emotion/emotion_model.keras` | `models/emotion/label_map.json` (class index → name mapping; `predictor.py` falls back to a hardcoded order if missing, but do not rely on that) |
| `models/object_detection/yolo11n.pt` | nothing else required — self-contained |
| `models/voice/speech_confidence_calibrator.joblib` | `models/voice/feature_scaler.joblib` (the classifier expects pre-scaled features; using one without the other will silently corrupt the calibration) |
| `models/face_authentication/calibrated_threshold.json` | nothing else required (falls back to a hardcoded default of 0.68 if missing — see MODEL_INVENTORY.md) |
| `inference/gaze_headpose/ml/training/gaze_headpose/predictor.py` | every other `.py` file in that same directory (`landmark_detector.py`, `gaze_estimator.py`, `headpose_estimator.py`, `blink_detector.py`, `drowsiness_detector.py`, `face_quality.py`, `temporal_filter.py`, `utils.py`, `config.py`) — they import from each other directly |
| any `inference/<module>/predictor.py` | that same module's `config.py` and `utils.py` (every module imports its own config/utils by bare unqualified import, resolved by adding that directory to `sys.path`) |

## Known integration gotchas (verified by testing, not theoretical)

1. **Object detection's weight loading is filename-based, not path-based** — see the code comment in §2 above. If you skip the `config.PRIMARY_WEIGHTS_SPEED` override, it will still work, but will download a fresh 5.6MB copy from GitHub on first run instead of using the packaged file (harmless functionally, since it's the same stock weights, but wastes bandwidth/time and needs network access).
2. **`gaze_headpose`'s import style differs from the other four modules** — it uses qualified imports (`from ml.training.gaze_headpose import ...`) instead of bare ones (`import config`). This package preserves the original directory nesting under `inference/gaze_headpose/ml/training/gaze_headpose/` specifically so no source file needed editing — add `inference/gaze_headpose/` (not the nested path) to `sys.path`.
3. **Face authentication and voice each need a `checkpoints/` subfolder next to their code**, not next to `models/` — their own `config.py` resolves `CHECKPOINTS_DIR` relative to wherever `config.py` itself lives (`Path(__file__).resolve().parent / "checkpoints"`), unlike emotion/object-detection which resolve paths relative to a project root. This package ships those two small files in **both** `models/<module>/` (for a consistent inventory view) and `inference/<module>/checkpoints/` (so the code's own auto-discovery works with zero configuration) — this is intentional duplication, not an error.
4. **Silero VAD will not load** in the verified environment (`ModuleNotFoundError: No module named 'torchaudio'`) — the voice module falls back to WebRTC VAD automatically and correctly (verified). Install `torchaudio==2.5.1` if you specifically want Silero's higher accuracy.
