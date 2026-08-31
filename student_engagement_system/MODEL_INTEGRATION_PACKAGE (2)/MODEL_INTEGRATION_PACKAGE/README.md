# Model Integration Package — Student Engagement / Cognitive Monitoring

## 1. Purpose

A portable, self-contained copy of every trained/pretrained ML component
found in `D:\student-engagement-system` (inspected 2026-08-23), plus the
inference code needed to run each one independently, for integration into
your friend's separate Student Engagement / Cognitive Monitoring project.
**Nothing in the original project was modified, retrained, fine-tuned, or
deleted** to produce this package — every model file here is a byte-for-byte
copy, and every prediction shown in `MODEL_INVENTORY.md` was verified by
actually running the code, not estimated or assumed.

## 2. Models found (full detail in `MODEL_INVENTORY.md`)

| Component | Found? | Trained model, or pretrained/rule-based? |
|---|---|---|
| Emotion detection | Yes | Trained (MobileNetV2 transfer learning on FER2013) |
| Object detection (person + phone, one model) | Yes | Pretrained only (stock YOLOv11n on COCO, not fine-tuned) |
| Gaze / head-pose / blink / drowsiness | Yes | Rule-based + pretrained geometric (MediaPipe + solvePnP + EAR) — not a trained model |
| Face authentication | Yes | Pretrained frozen embedding model (ArcFace) + a calibrated threshold (not a model) |
| Voice speech-confidence calibrator | Yes | Trained (small GradientBoostingClassifier), layered on a pretrained VAD |
| Engagement / LSTM attention-drop predictor | **No** | Not present anywhere in the project — stub only |

## 3. Models included in this package

- `models/emotion/emotion_model.keras` + `label_map.json`
- `models/object_detection/yolo11n.pt`
- `models/voice/speech_confidence_calibrator.joblib` + `feature_scaler.joblib`
- `models/face_authentication/calibrated_threshold.json`
- Inference code for all of the above, plus gaze/head-pose (no weight file needed — MediaPipe supplies its own)

## 4. Models / files explicitly excluded, and why

| Excluded | Reason |
|---|---|
| `models/emotion/checkpoints/phase1_head_best.keras`, `phase2_finetune_best.keras` | Intermediate training checkpoints, superseded by the final `emotion_model.keras`; not required at runtime |
| `models/emotion/emotion_model_fixed.keras` | **Unresolved anomaly** — structurally identical to `emotion_model.keras`, same saved Keras version, but referenced by **no code anywhere in the repository** and last modified the same day as this inspection. I could not determine its origin from the source code, so I did not include it. See `MODEL_INVENTORY.md` §1 for full detail. If you need it, it's at `models/emotion/emotion_model_fixed.keras` in the original project — recommend confirming with whoever created it before using it. |
| `ml/training/face_authentication/embeddings/student_registry.json` | **Contains real personal data** — 5 students' real names + 512-D face embeddings + enrollment timestamps. See §12 below. |
| `ml/training/face_authentication/registered_students/DEMO00{1..5}/*.jpg` | **Contains real face photographs.** See §12 below. |
| `datasets/` (all of FER2013, COCO2017, MPIIGaze, ESC-50, Speech Commands, LFW) | Training/evaluation datasets, not required at inference time; large; not personal-data-safe to bulk-copy without review (FER2013/LFW/MPIIGaze all contain real face images) |
| Training/preprocessing/exploration notebooks (`dataset_download.ipynb`, `dataset_preprocessing.ipynb`, `dataset_exploration.ipynb`, `train_model.ipynb`, `evaluate_model.ipynb`, `trainer.py` files, `register_faces.ipynb`) | Training/evaluation/enrollment tooling, not inference code. Referenced by name in `MODEL_INVENTORY.md`/`INTEGRATION_GUIDE.md` where relevant, not copied. |
| `runs/detect/val*` (YOLO validation plots) | Visualization artifacts from a training-time validation run, not required for inference |
| Evaluation artifact PNGs (confusion matrices, ROC curves, PR curves, training curves) | Visualizations, not runtime dependencies. The underlying numeric metrics they visualize ARE reproduced as real numbers in `MODEL_INVENTORY.md`. |
| `backend/`, `frontend/`, `ml/inference-services/`, `ml/feature-aggregator/`, `ml/engagement-score-engine/` | Either empty scaffolding or backend orchestration code that doesn't currently do anything (see `LIVE_PIPELINE.md`) — nothing there to usefully copy |

## 5. Exact model filenames, original paths, architectures, frameworks

See `MODEL_INVENTORY.md` — a complete table plus a detailed per-model
section with input/output, preprocessing, thresholds, and measured metrics
for every component. Not duplicated here to avoid the two documents
drifting out of sync.

## 6. Dependencies

See `requirements_models.txt` — pinned to the exact versions installed in
the source project's own `.venv`, which is what every "Test" result in
`MODEL_INVENTORY.md` was verified against.

## 7. Input/output, preprocessing, thresholds, feature order

Documented per-model in `MODEL_INVENTORY.md` and with copy-pasteable code
in `INTEGRATION_GUIDE.md`. There is **no LSTM feature order to document**
(§10 of the original request) because no LSTM exists in the source
project — see §10 below and `MODEL_INVENTORY.md` item 6.

## 8. Evaluation metrics (all real, measured — none fabricated or estimated)

| Component | Headline metric | Source file |
|---|---|---|
| Emotion | 51.7% test accuracy (7,178 FER2013 test images, same set as before) — retrained 2026-08-23 (checkpoint-selection bug fix + CK+ data), up from 44%, still below the module's own 65% target | `ml/training/emotion_model/evaluation_artifacts/classification_report.txt` |
| Object detection | Classroom-taxonomy: P 0.803 / R 0.408 / F1 0.541 (200 images); person-count exact-match 74%; official COCO-80 mAP was skipped (not run). Two improvement attempts (OIV7 secondary model, a coco_subset fine-tune) were tested 2026-08-23 and both regressed the result — reverted, this is still the best available | `ml/training/object_detection/evaluation_artifacts/metrics_summary.json` |
| Gaze/head-pose | Gaze mean angular error 16.43° (277,906 MPIIGaze samples). Head-pose classification: 81.0% accuracy on `head_pose_300w_lp` (836 full-face samples, added 2026-08-23) — the original MPIIGaze-based eval undercounted this at 44.2% because MPIIGaze is eye-crop-only and the method needs a full face. Blink accuracy still reports 0 samples (no compatible ground truth available yet) | `ml/training/gaze_headpose/evaluation/evaluation_report.json` |
| Face authentication | EER 13.65% (6,968 genuine / 1,999 impostor pairs) | `ml/training/face_authentication/checkpoints/calibrated_threshold.json` |
| Voice calibrator | 94.84% test accuracy, F1 94.89%, ROC-AUC 98.89% (601 test samples) — accuracy target of 95% narrowly missed | `ml/training/voice_analysis/evaluation_artifacts/metrics.json` |

## 9. Live pipeline

**No end-to-end live pipeline currently exists in the source project.**
Every model above works in isolation (verified), but nothing in the
backend calls any of the Celery task wrappers that would invoke them — see
`LIVE_PIPELINE.md` for the full trace, including exactly which files are
empty and which grep commands confirm no caller exists.

## 10. Testing status

Every model was tested twice: once from its **original location** in the
source project, and once from **this package's copies**, in a way that
verifies no hidden reference to the original project remains (fresh
working directory, package-relative paths only). Both passed for all five
components. Full detail, including the exact inputs used and outputs
produced, is in `MODEL_INVENTORY.md`'s "Test — original file" / "Test —
packaged copy" rows for each model.

One side effect encountered and corrected during testing: loading the YOLO
model by its original code path (`YOLO("yolo11n.pt")`, a bare filename)
caused Ultralytics to auto-download a second copy of the weights into the
source project's repo root. This stray file was identified and deleted
immediately after the test — **the original project was left exactly as
found.** `INTEGRATION_GUIDE.md` §2 documents the correct way to point the
loader at the packaged weights file instead, which avoids this entirely.

**2026-08-27 update — sample images added, package is now fully self-contained for smoke-testing.** The three non-personal-data test images the "Test" rows above reference (`happy.jpg`, `phone.jpg`, `face.jpg`) previously only existed in the *original* project, meaning a copy of just this package couldn't be smoke-tested without also having the source repo. They're now bundled under `samples/` (`emotion_happy.jpg`, `object_detection_phone.jpg`, `gaze_headpose_face.jpg`) and re-verified from that new location on a Windows path with no source-project files present — all three reproduced their documented outputs exactly (emotion: `fear` 35.74%; object detection: `Person` 0.843 / `Cell Phone` 0.577; gaze/head-pose: gaze `center` 92.4%, head-pose `focused`, yaw 2.6°/pitch 4.2°). Face authentication and voice analysis need no bundled sample: face auth's original test image is real student data and is correctly excluded (§12), and voice's test uses a synthetic tone generated in code.

## 11. Known limitations (real, found during inspection/testing — not hypothetical)

- **No LSTM / engagement-score fusion exists.** This is the single biggest gap — see §2 and `MODEL_INVENTORY.md` item 6.
- **No live pipeline wiring exists** — see §9. The five working models are not currently reachable from any API, WebSocket, or scheduler in the source project.
- **Emotion model accuracy (51.7%, up from 44% after a 2026-08-23 retrain) is still below its own project's 65% target.** Still usable, but the confidence/probability outputs should be treated accordingly — consider thresholding on `confidence` in your integration rather than trusting the raw label unconditionally.
- **Object detection has real, documented class-coverage gaps**: 5 of 17 classroom-taxonomy classes (Notebook, Pen, Tablet, Calculator, Headphones) have no COCO equivalent and will not be detected by the shipped model (per-class metrics for these are 0/0/0 in `metrics_summary.json`, confirming this empirically, not just per the docs).
- **Gaze estimation is an uncalibrated approximation** (16.43° mean angular error measured against MPIIGaze) — the module's own docs describe it as such; do not present it as precision eye-tracking.
- **Face authentication has a real EER of ~13.65%** on its own calibration pairs — a non-trivial false-accept/false-reject rate. Consider this before using it as a hard access-control gate.
- **Voice's Silero VAD backend does not load in the verified environment** (missing `torchaudio`) — falls back cleanly to WebRTC VAD, which is what was actually tested. Functionally fine, but the "highest accuracy" backend documented in the module's own comments is not the one active by default in this environment.
- **The `emotion_model_fixed.keras` anomaly** (see §4) is unresolved — flagging it rather than guessing at or including it.

## 12. Personal / student data that must NOT be transferred

The following exist in the source project and were **deliberately excluded**
from this package:

- `ml/training/face_authentication/embeddings/student_registry.json` — 5 real student names (e.g. "Abdoulaye Wade", "Abdullah"), each paired with a 512-dimensional face embedding vector and an enrollment timestamp. A face embedding is biometric data — treat it with the same sensitivity as the source photo it was derived from.
- `ml/training/face_authentication/registered_students/DEMO001/` through `DEMO005/` — 3 to 8 raw enrollment face photographs per student.

**Do not copy these into your friend's project, a shared drive, a chat, or
anywhere else without explicit authorization from whoever owns this data
and the students' (or their guardians') consent, per your institution's
data-protection policy.** If your friend's project genuinely needs
enrolled-student data to test the face-authentication component,
`INTEGRATION_GUIDE.md` §4 shows how to enroll fresh, consented test
subjects using the packaged code instead.

## 13. Integration instructions

See `INTEGRATION_GUIDE.md` — working, copy-pasteable code for every model,
using the project's actual classes (`EmotionPredictor`,
`ObjectDetectionPredictor`, `GazeHeadPosePredictor`, `FaceAuthenticator`,
`VoiceAnalyzer`), plus a table of documented integration gotchas found
during testing (not theoretical) and a "files that must stay together"
table.

## 14. Files that must stay together

See `INTEGRATION_GUIDE.md`'s dedicated table — summarized: the emotion
model needs its `label_map.json`; the voice calibrator needs its scaler;
every `inference/<module>/predictor.py` needs that same directory's
`config.py`/`utils.py` alongside it; and `gaze_headpose`'s files must keep
their nested `ml/training/gaze_headpose/` subpath intact (that module uses
qualified imports, unlike the other four).

## 15. Compatibility notes

- Emotion model was saved with **Keras 3.15.0**, TensorFlow **2.18.0** (read directly from the model file's own embedded `metadata.json`, not assumed). This exact combination was confirmed installed and working. A different major Keras/TensorFlow version may fail to load it — I did not test other versions and did not alter the model to "fix" compatibility for any version.
- Voice analysis's Silero VAD backend requires `torchaudio`, which is not in `requirements_models.txt` by default (kept optional — see that file's comments) because it was not present in the verified environment and the module correctly falls back to WebRTC VAD without it.
- Face authentication's `retinaface` detector backend and `deepface`'s model downloads require network access on first use (weights are cached locally afterward, same as MediaPipe and Ultralytics).

## 16. File manifest (every copied file)

| Package path | Original path | Purpose | Required at runtime? |
|---|---|---|---|
| `models/emotion/emotion_model.keras` | `models/emotion/emotion_model.keras` | Final trained emotion classifier | Yes |
| `models/emotion/label_map.json` | `models/emotion/label_map.json` | Class index → emotion name mapping | Yes |
| `models/object_detection/yolo11n.pt` | `ml/training/object_detection/yolo11n.pt` | Pretrained YOLOv11n weights (person + phone + 15 other classes) | Yes |
| `models/voice/speech_confidence_calibrator.joblib` | `ml/training/voice_analysis/checkpoints/speech_confidence_calibrator.joblib` | Trained speech-confidence classifier | Yes |
| `models/voice/feature_scaler.joblib` | `ml/training/voice_analysis/checkpoints/feature_scaler.joblib` | Feature scaler paired with the classifier above | Yes |
| `models/face_authentication/calibrated_threshold.json` | `ml/training/face_authentication/checkpoints/calibrated_threshold.json` | Calibrated cosine-similarity accept/reject threshold | Yes (falls back to a hardcoded default if absent) |
| `inference/emotion/{config,utils,emotion_model,predictor}.py` | `ml/training/emotion_model/{same}.py` | Emotion inference code (verbatim copies) | Yes |
| `inference/object_detection/{config,utils,detector,tracker,predictor}.py` | `ml/training/object_detection/{same}.py` | Object detection inference code (verbatim copies) | Yes |
| `inference/gaze_headpose/ml/training/gaze_headpose/*.py` (10 files + `__init__.py`) | `ml/training/gaze_headpose/*.py` | Gaze/head-pose/blink/drowsiness inference code (verbatim copies, original subpath preserved — see §14) | Yes |
| `inference/face_authentication/{config,utils,embedding_model,predictor}.py` | `ml/training/face_authentication/{same}.py` | Face authentication inference code (verbatim copies) | Yes |
| `inference/face_authentication/checkpoints/calibrated_threshold.json` | (duplicate of the `models/` copy above) | Lets the module's own `config.py` auto-discover the threshold with zero configuration | Yes (convenience duplicate — see `INTEGRATION_GUIDE.md` gotcha #3) |
| `inference/voice/{config,utils,voice_analyzer}.py` | `ml/training/voice_analysis/{same}.py` | Voice analysis inference code (verbatim copies) | Yes |
| `inference/voice/checkpoints/{speech_confidence_calibrator,feature_scaler}.joblib` | (duplicates of the `models/` copies above) | Same auto-discovery convenience as above | Yes (convenience duplicate) |
| `configs/thresholds.example.yaml` | `configs/thresholds.example.yaml` | Reference copy of the project's example threshold config (not consumed by any code in this package — provided for context only) | No |
| `samples/emotion_happy.jpg` | `ml/training/emotion_model/happy.jpg` | Smoke-test input for emotion detection (not personal data, not a benchmark image) | No (test convenience — added 2026-08-27) |
| `samples/object_detection_phone.jpg` | `ml/training/object_detection/phone.jpg` | Smoke-test input for object detection | No (test convenience — added 2026-08-27) |
| `samples/gaze_headpose_face.jpg` | `ml/training/gaze_headpose/face.jpg` | Smoke-test input for gaze/head-pose/blink/drowsiness | No (test convenience — added 2026-08-27) |

No file in this package was edited — every `.py`/`.json`/`.keras`/`.pt`/`.joblib` file listed above is a byte-for-byte copy of the original, verified via the tests documented in `MODEL_INVENTORY.md`.
