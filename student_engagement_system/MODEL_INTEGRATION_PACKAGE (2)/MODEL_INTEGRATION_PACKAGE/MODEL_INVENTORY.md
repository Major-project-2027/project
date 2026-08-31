# Model Inventory

Source project: `D:\student-engagement-system` (as inspected on 2026-08-23).
Every entry below was verified by loading the file and running real
inference, both from the original project location and from the copies
inside this package. See each section's "Test" row for the actual output.

| # | Component | Category (per inspection task) | Exact File | Original Path | Architecture | Framework | Live? |
|---|---|---|---|---|---|---|---|
| 1 | Emotion detection | A — Trained model found | `emotion_model.keras` | `models/emotion/emotion_model.keras` | MobileNetV2 (ImageNet-pretrained backbone) + custom head, transfer learning | TensorFlow/Keras 3.15.0 | Task wrapper exists; no caller found (see LIVE_PIPELINE.md) |
| 2 | Object detection (person + phone, single model) | B — Pretrained model, not custom-trained | `yolo11n.pt` | `ml/training/object_detection/yolo11n.pt` | YOLOv11-nano | Ultralytics / PyTorch | Task wrapper exists; no caller found |
| 3 | Gaze / head-pose / blink / drowsiness | Rule-based + pretrained geometric pipeline (not a trained model) | n/a (MediaPipe auto-downloads its own weights) | `ml/training/gaze_headpose/*.py` | MediaPipe FaceMesh (pretrained) + `cv2.solvePnP` + EAR formula, all rule/geometry-driven | MediaPipe 0.10.18, OpenCV | Task wrapper exists; no caller found |
| 4 | Face authentication | Pretrained dependency (ArcFace, frozen) + a calibrated scalar threshold (not a trained model) | `calibrated_threshold.json` | `ml/training/face_authentication/checkpoints/calibrated_threshold.json` | ArcFace (512-D embeddings) via DeepFace, frozen/no training | DeepFace 0.0.93 (TensorFlow-backed) | Task wrapper exists; no caller found |
| 5 | Voice / speech-confidence calibrator | A — Trained model found (small, on top of a pretrained VAD) | `speech_confidence_calibrator.joblib` + `feature_scaler.joblib` | `ml/training/voice_analysis/checkpoints/` | Gradient Boosting Classifier (scikit-learn) + StandardScaler | scikit-learn 1.5.2 | Task wrapper exists; no caller found |
| 6 | Engagement / LSTM attention-drop predictor | D — No model found | — | `ml/training/lstm_engagement/` contains only `.gitkeep` | n/a | n/a | `backend/worker/tasks/lstm_task.py` is an explicit stub that raises `NotImplementedError` |

"Live?" reflects Step 11 of the inspection: every Celery task wrapper
(`backend/worker/tasks/*.py`, except `lstm_task.py`) correctly imports and
calls its module's real predictor — that wiring works (verified by
`grep`-ing for `.delay(`/`apply_async`/task names across `backend/`: only
the task definition files themselves reference these names). But no route,
WebSocket handler, or scheduler anywhere in `backend/app/` calls any of
these tasks — `backend/app/main.py` only defines a `/healthz` endpoint, and
every `backend/app/modules/*/__init__.py` is empty (0 bytes). See
`LIVE_PIPELINE.md` for the full trace.

---

## 1. Emotion Detection

- **Purpose:** Classify a cropped, aligned face image into an emotion.
- **Model file:** `emotion_model.keras` (26,538,706 bytes) — **retrained 2026-08-23**, replacing the earlier 44%-accuracy version (see updated metrics below)
- **Original path:** `D:\student-engagement-system\models\emotion\emotion_model.keras`
- **Package path:** `models/emotion/emotion_model.keras`
- **Format:** Keras v3 native format (zip archive: `metadata.json`, `config.json`, `model.weights.h5`)
- **Saved with:** `keras_version: "3.15.0"`, saved `2026-08-23@22:55:29` (read directly from the model's own `metadata.json`)
- **Architecture:** `Input(96,96,3)` → `Rescaling` to `[-1,1]` → `MobileNetV2` (ImageNet weights, `include_top=False`) → `GlobalAveragePooling2D` → `Dropout(0.3)` → `Dense(128, relu)` → `Dropout(0.15)` → `Dense(7, softmax)`. Defined in `ml/training/emotion_model/emotion_model.py::build_emotion_model`.
- **Framework:** TensorFlow 2.18.0 / Keras 3.15.0 (confirmed installed and matching in the project's `.venv`)
- **Input size:** 96×96, 3 channels, float32 in `[0,1]` (the model itself rescales to `[-1,1]` internally)
- **Number of classes:** 7 (native FER2013 taxonomy)
- **Class names / indices:** from `models/emotion/label_map.json`: `{0: angry, 1: disgust, 2: fear, 3: happy, 4: sad, 5: surprise, 6: neutral}`
- **Preprocessing:** grayscale conversion (if a color image is given) → resize to 96×96 (`cv2.INTER_AREA`) → replicate to 3 channels → `/255.0`. Implemented in `predictor.py::EmotionPredictor._preprocess`.
- **Simplified label map** (system-wide taxonomy, applied post-hoc, not part of the model): `angry→Angry, disgust→Angry, fear→Confused, happy→Happy, sad→Sad, surprise→Confused, neutral→Neutral` (`config.SIMPLIFIED_LABEL_MAP`).
- **Output format:** `{raw_label, simplified_label, confidence, probabilities}` dict.
- **Confidence/threshold:** none applied at inference — the raw softmax argmax and its probability are returned as-is; no acceptance threshold is enforced in code.
- **Inference function/file:** `EmotionPredictor.predict()` in `ml/training/emotion_model/predictor.py`.
- **Dataset:** FER2013 (`datasets/processed/fer2013/*.npy`).
- **Actual measured metrics** (from `ml/training/emotion_model/evaluation_artifacts/classification_report.txt`, a real test-set run — not estimated): **overall test accuracy = 51.7%** (weighted avg F1 = 0.517) on the same 7,178 held-out FER2013 test images used for the original 44% figure. Per-class F1 ranges from 0.35 (fear) to 0.71 (happy); every class improved or held steady vs. the previous model. The module's own README states a target of "≥65% accuracy" per the architecture doc's NFR — **still below that target, but the gap is now under half of what it was.**
- **What changed and why:** two fixes applied 2026-08-23. (1) A real bug in `trainer.py`: the two-phase training loop always deployed whatever phase-2 (fine-tuning) ended with, even on runs where phase 2 never beat phase 1's checkpoint — it now compares both phases' best validation accuracy and exports whichever is actually better. (2) 927 usable images from the CK+ dataset were folded into the training/validation tensors (54 "contempt"-labeled images were dropped — no matching class in this 7-class taxonomy). The FER2013 test set itself was never touched, so the 44%→51.7% comparison is apples-to-apples, not an easier benchmark.
- **Checkpoints found (not copied — intermediate only):** `models/emotion/checkpoints/phase1_head_best.keras`, `phase2_finetune_best.keras`.
- **Anomaly found, not copied:** `models/emotion/emotion_model_fixed.keras` exists in the original project, is structurally identical (same layer count/config) to `emotion_model.keras`, but is **not referenced by any code in the repository** (`predictor.py` only ever loads `config.BEST_MODEL_PATH`, which points at `emotion_model.keras`). Predates the 2026-08-23 retraining session and its origin still could not be determined — flagged for your attention, not included in this package. If you need it, it is at `models/emotion/emotion_model_fixed.keras` in the original project.
- **Test — original file:** PASS. Loaded via `tf.keras.models.load_model`; ran inference on `ml/training/emotion_model/happy.jpg`; predicted `fear` (35.74% confidence, `happy` a close second at 28.82%) — this is the retrained model re-evaluated on the same ambiguous non-canonical test photo used for the original file (which predicted `neutral` at 76.2%); not a benchmark image, just a smoke test that inference runs end-to-end.
- **Test — packaged copy:** PASS. Identical input → identical output (`fear`, 35.74%), loaded from `MODEL_INTEGRATION_PACKAGE/models/emotion/emotion_model.keras` with `ENGAGEMENT_REPO_ROOT` pointed at the package root (see INTEGRATION_GUIDE.md).

## 2. Object Detection (Person + Phone + 15 other classroom classes)

- **Purpose:** Detect people (for multi-person / occupancy signals) and devices (phone/laptop) in a classroom frame. **One single model handles both person and phone detection** — there is no separate phone-only or person-only model.
- **Model file:** `yolo11n.pt` (5,613,764 bytes at original location)
- **Original path:** `D:\student-engagement-system\ml\training\object_detection\yolo11n.pt`
- **Package path:** `models/object_detection/yolo11n.pt`
- **Format:** Ultralytics/PyTorch checkpoint (`.pt`)
- **Architecture:** YOLOv11-nano (`yolo11n`), single-stage anchor-free detector.
- **Is this custom-trained? No.** Confirmed by `ml/training/object_detection/README.md` and `config.py`/`detector.py` docstrings: this is a **stock, COCO-pretrained** Ultralytics release, auto-downloaded by the `ultralytics` package. No fine-tuning is performed anywhere in this module. `trainer.py` in this module is an **evaluation harness**, not a training script (confirmed by reading it — it only calls `.val()` and custom metric functions, never `.train()`).
- **Which weights the live code actually loads:** `config.PERFORMANCE_MODE = "speed"` (default) → `config.PRIMARY_WEIGHTS_SPEED = "yolo11n.pt"`, with `config.FALLBACK_WEIGHTS_SPEED = "yolov8n.pt"` if YOLO11 can't load. The "accuracy" mode (`yolo11m.pt`/`yolov8m.pt`) exists in config but is not the default and was not found downloaded anywhere in the project — only `yolo11n.pt` is present on disk.
- **Framework:** Ultralytics 8.3.49 / PyTorch 2.5.1, CPU inference (`config.DEVICE = "cpu"`)
- **Input image size:** 640×640 (`config.INFERENCE_IMAGE_SIZE`)
- **Confidence threshold:** 0.35 (`config.CONFIDENCE_THRESHOLD`)
- **NMS IoU threshold:** 0.45 (`config.NMS_IOU_THRESHOLD`)
- **Max detections/image:** 100
- **Classes (17-class classroom taxonomy, remapped from COCO's 80):** Person, Cell Phone, Laptop, Book, Notebook, Pen, Bottle, Cup, Chair, Backpack, Keyboard, Mouse, Monitor, Tablet, Calculator, Headphones, Unknown Object. Only 10 of these 17 have an exact COCO match (see `config.COCO_NAME_TO_TARGET`); Notebook/Pen/Tablet/Calculator/Headphones have **no COCO equivalent** and will not be detected by this model as shipped (documented explicitly in the module's own README, not something I inferred).
- **Preprocessing:** handled internally by Ultralytics (`model.predict(source=frame, conf=..., iou=..., imgsz=640, ...)`) — no separate preprocessing step in this project's code.
- **Postprocessing:** raw Ultralytics `Results` → mapped through `COCO_NAME_TO_TARGET` onto the 17-class taxonomy; anything unmapped becomes `"Unknown Object"` (not dropped).
- **Output format:** `FrameResult` dataclass with a list of `Detection(class_id, class_name, confidence, bbox, track_id, person_id, source_model)`, plus derived `events` (chair occupancy, sitting/standing, person-object interaction — all documented as heuristics, not verified physical state).
- **Object detection → downstream "for LSTM" contract:** `detections_to_feature_vector()` produces a fixed 23-D vector per frame (17 per-class counts + person_count + object_count + mean_confidence + max_confidence + fps + timestamp). This is exported and ready for an LSTM but **there is no LSTM to consume it** (see item 6).
- **Actual measured metrics** (from `ml/training/object_detection/evaluation_artifacts/metrics_summary.json`, a real evaluation run against a 200-image classroom-taxonomy subset of COCO val2017 + a 2000-image count-accuracy pass — not estimated):
  - Official COCO-80 mAP pass: **skipped** (`"note": "Official COCO validation skipped."` — not run, not fabricated).
  - Classroom-taxonomy (17-class, single IoU=0.5, greedy-matched — NOT Ultralytics' official mAP methodology): overall precision **0.803**, recall **0.408**, F1 **0.541**, over 200 evaluated images. Per-class results vary hugely — e.g. Person: P 0.886/R 0.510/F1 0.648; Cell Phone: P 1.0/R 0.6/F1 0.75 (only 5 ground-truth instances); Book: P 0.5/R 0.03/F1 0.057 (COCO's "book" class is notoriously hard for this detector — 64 false negatives out of 66); Notebook/Pen/Tablet/Calculator/Headphones: 0/0/0 across the board (no COCO equivalent, as documented above).
  - Person-count exact-match accuracy: **74%** (MAE 0.891) over 2,000 images.
  - Object-count exact-match accuracy: **31%** (MAE 3.526) — explicitly noted in the metrics file as "not like-for-like" since it compares against all COCO categories, not just the 17-class taxonomy.
  - Latency: mean **88.7 ms/frame** (≈11.3 FPS) on CPU at 640×640, over 50 synthetic frames — meets the module's own `TARGET_FPS_CPU=10.0` target; does **not** meet its `TARGET_PRECISION/RECALL/F1/MAP50 = 0.90` targets (explicitly reported as `false` in `meets_targets`).
  - Tracking accuracy: **not computed** — "No tracking ground truth supplied" (honestly reported, not fabricated).
- **Improvement attempts tried 2026-08-23, both reverted — numbers above are still current:** (1) enabling the shipped-but-disabled `USE_OIV7_SECONDARY_MODEL` flag (meant to add Pen/Tablet/Calculator/Headphones coverage) instead *regressed* precision from 0.803 to 0.437, because those classes have zero ground-truth instances anywhere in this dataset and the extra model's other detections flooded the "Unknown Object" bucket with false positives. (2) Fine-tuning `yolo11n` on a newly-added `coco_subset` (400 images, person+cell_phone), done carefully to avoid two real landmines found during review (16 of its images already sat in this held-out test split; its own 2-class labels would have collapsed the detector's head and destroyed the other 15 classes) — even done safely, 4 epochs on 345 images *regressed* both target classes (Person recall 0.510→0.484, Cell Phone recall 0.600→0.400). Both changes were fully reverted; this model file and `config.py` are unchanged from the original.
- **Test — original file:** PASS. Loaded via `ultralytics.YOLO("yolo11n.pt")` (note: this call resolves by filename, not the local file path — see "Known limitation" below); ran inference on `ml/training/object_detection/phone.jpg`; detected `Person` (0.843) and `Cell Phone` (0.577).
- **Test — packaged copy:** PASS, with a caveat. Loading `YOLO("yolo11n.pt")` by bare filename does **not** use the project's own downloaded copy — Ultralytics resolves bare filenames against the current working directory / its own asset cache, and will **silently download a fresh copy from GitHub** if not found there (confirmed: this happened during my first load test and wrote a stray `yolo11n.pt` into the repo root, which I removed). For the packaged copy, I pointed `config.PRIMARY_WEIGHTS_SPEED`/`FALLBACK_WEIGHTS_SPEED` at the package's absolute file path before instantiating `ObjectDetectionPredictor` — this loaded the exact packaged file (no download) and produced identical detections (`Person` 0.843, `Cell Phone` 0.577). See INTEGRATION_GUIDE.md for the exact code.

## 3. Gaze / Head-Pose / Blink / Drowsiness

- **Purpose:** Eye-focus direction, head-pose classification (focused / slightly_distracted / looking_away), blink counting, and drowsiness state (alert / fatigued / drowsy / microsleep).
- **Is this a trained model? No — confirmed rule-based + pretrained-geometric, not a custom neural network.** Per `ml/training/gaze_headpose/README.md` §1 ("Why geometric methods, not deep learning") and every sub-module's own docstring:
  - Face landmarks: **MediaPipe FaceMesh** (Google's pretrained model, downloaded automatically by the `mediapipe` package — no weight file lives in this repo).
  - Gaze direction: geometric ratio of iris position to eye-corner span (`gaze_estimator.py`) — pure math, thresholded at `config.GAZE_HORIZONTAL_THRESHOLD=0.18` / `GAZE_VERTICAL_THRESHOLD=0.16`.
  - Head pose: `cv2.solvePnP` against a **fixed 6-point 3D face model** (`config.GENERIC_3D_FACE_MODEL`, hardcoded reference geometry, not learned) — classified as focused (≤15° yaw/pitch), slightly_distracted (≤30°/25°), else looking_away.
  - Blink/drowsiness: Eye Aspect Ratio (EAR) formula with an adaptive threshold (75% of a rolling open-eye EMA baseline) — a published geometric formula (Soukupová & Čech, 2016), not a learned classifier. Drowsiness state is a set of fixed duration thresholds (1.0s/2.0s/3.5s sustained closure) plus a blink-rate threshold (25/min).
- **No model weight file exists in this project for this module** (confirmed: no `.pt`/`.h5`/`.keras`/`.onnx`/`.tflite` anywhere under `ml/training/gaze_headpose/`).
- **Framework:** MediaPipe 0.10.18 (FaceMesh + Iris, `refine_landmarks=True`), OpenCV (`solvePnP`), NumPy.
- **Input:** a single BGR frame (`np.ndarray`).
- **Output:** flat dict via `GazeHeadPoseFrameResult.to_dict()` — gaze direction/confidence/ratios, head yaw/pitch/roll/classification, EAR/blink count/rate, drowsiness state/confidence, an overall per-frame confidence (weighted blend of detection confidence 0.40 + face-quality 0.35 + temporal stability 0.25).
- **Temporal smoothing:** EMA filter (default) on yaw/pitch/roll and gaze ratios; optional Kalman filter (`config.KALMAN_ENABLED_DEFAULT=False` by default).
- **Actual measured metrics** (from `ml/training/gaze_headpose/evaluation/evaluation_report.json`, real evaluation runs — not estimated):
  - Head-pose classification originally reported **0 samples evaluated** on MPIIGaze. Two compounding causes: MPIIGaze's own normalization procedure cancels head roll (so the ground truth for it is never present in the form this evaluator needs), and — this part was a real code bug, fixed 2026-08-23 — `trainer.py`'s row filter required a roll value on every row before running a metric that only actually needs pitch/yaw, discarding all 427,316 rows unnecessarily. After the fix, re-evaluating on MPIIGaze alone still only yields a 29.6% landmark-solve rate (MPIIGaze images are eye-region crops, not full faces, so the PnP method often can't find enough landmarks). Re-running instead against `datasets/raw/head_pose_300w_lp` (added 2026-08-23; 1,000 full-face images with real pitch/yaw/roll ground truth) — same unchanged estimator, just matched to appropriate data — gives an 83.6% landmark-solve rate and **81.0% classification accuracy** (precision 0.712 / recall 0.655 / F1 0.667 macro, n=836). This is the honest, real capability of the shipped geometric method; the original "0 samples" was a data/evaluation-methodology artifact, not a reflection of the method's actual accuracy.
  - Gaze: mean angular error **16.43°** over 277,906 samples (MPIIGaze eye crops, unchanged). This is a real, measured number — worth noting it is well above typical calibrated-eye-tracker error (~1-3°), consistent with this being an uncalibrated geometric approximation, exactly as the module's own README documents it ("uncalibrated approximations, not a precision eye-tracker output").
  - Blink accuracy: **still 0 samples evaluated.** MPIIGaze carries no blink ground-truth labels at all (documented gap, not a bug). A `MRL EYE DATASET` (added 2026-08-23, ~82,000 open/closed eye images) was staged to fill this gap via a small supplementary CNN classifier — training was started but paused (CPU-resource-constrained) and not yet completed as of this inventory update.
  - Latency: mean **5.72 ms/frame** (≈175 FPS) over 190 frames — well within budget; landmark detection is by far the dominant cost (5.68 ms of the 5.72 ms total).
- **Test — original file:** PASS. Ran `GazeHeadPosePredictor.predict_frame()` on `ml/training/gaze_headpose/face.jpg`; face detected, gaze="center" (92.4% confidence), head_pose="focused" (yaw 2.6°, pitch 4.2°), 0 blinks, drowsiness="alert".
- **Test — packaged copy:** PASS. Identical result from the packaged copy (`inference/gaze_headpose/ml/training/gaze_headpose/`), with the package's directory added to `sys.path` (see INTEGRATION_GUIDE.md for why the `ml/training/gaze_headpose/` subpath is preserved inside the package).

## 4. Face Authentication

- **Purpose:** Verify a detected face against a gallery of enrolled students via cosine similarity on face embeddings.
- **Is there a trained model of its own? No — a frozen, pretrained embedding model (ArcFace) used as-is, plus a calibrated scalar decision threshold (not a model).**
- **Embedding model:** ArcFace (512-D), loaded via the `deepface` library, which downloads and caches the architecture+weights itself (no local weight file in this repo for it). `config.EMBEDDING_MODEL_PRIORITY = ["ArcFace", "Facenet512", "Facenet"]` — ArcFace is tried first and was confirmed to load successfully.
- **Face detector backend:** `retinaface` (`config.FACE_DETECTOR_BACKEND`), also via `deepface`.
- **Calibrated threshold file:** `calibrated_threshold.json`
  - **Original path:** `ml/training/face_authentication/checkpoints/calibrated_threshold.json`
  - **Package path:** `models/face_authentication/calibrated_threshold.json` (also duplicated to `inference/face_authentication/checkpoints/` so the module's own auto-discovery works out of the box — see INTEGRATION_GUIDE.md)
  - **Content (real, measured, not estimated):** `threshold=0.4649`, `far_at_threshold=0.1366`, `frr_at_threshold=0.1365`, `eer=0.1365`, computed over 6,968 genuine pairs and 1,999 impostor pairs, `similarity_metric="cosine"`, `model_name="ArcFace"`. An EER of ~13.65% is a real, non-trivial error rate — worth flagging to your friend's team as a calibration quality signal, not a "production-grade" biometric EER (state-of-the-art ArcFace systems on curated benchmarks report <1%; this number reflects this project's own dataset/calibration, most likely LFW pairs given `config.ACTIVE_DATASET="lfw"`).
- **Registration data — NOT copied into this package (see "Personal data" below):** `embeddings/student_registry.json` (5 demo students: real names + 512-D embeddings + enrollment timestamps) and `registered_students/DEMO00{1..5}/*.jpg` (raw enrollment face photos).
- **Similarity metric:** cosine similarity, threshold from the calibrated file above (falls back to `config.DEFAULT_COSINE_SIMILARITY_THRESHOLD=0.68` if the file is absent).
- **Output format:** `AuthenticationResult(is_known, student_id, student_name, similarity_score, confidence, bounding_box, detection_confidence, accepted, threshold_used)`.
- **Test — original file:** PASS. Loaded `FaceAuthenticator()` (ArcFace, 512-D, threshold 0.4649, gallery of 5 students loaded from the original `student_registry.json`); authenticated `registered_students/DEMO001/enrollment_00.jpg` against the gallery → matched `DEMO001`, `accepted=True`, similarity 0.7732, confidence 0.746.
- **Test — packaged copy:** PASS (with expected empty gallery). Loaded from the package with no student registry shipped (by design — see "Personal data" section of README.md); ArcFace loaded correctly, threshold resolved correctly to 0.4649 from the packaged `checkpoints/calibrated_threshold.json`, gallery size = 0 as expected. **Your friend's team must run their own enrollment step to populate a `student_registry.json` before this component can accept/reject real students** — the code to do so is `register_faces.ipynb` in the original project (not copied here; it is enrollment tooling, not inference code — see README.md "Files excluded").

## 5. Voice Analysis — Speech-Confidence Calibrator

- **Purpose:** Refine a raw voice-activity-detection (VAD) vote into a calibrated `speech_probability`, and (separately) flag sustained loud/rapid speech as a `classroom_disturbance` alert signal. **This output is explicitly NOT fused into the engagement score or the LSTM** — confirmed by `backend/app/config.py`'s `ENGAGEMENT_FEATURE_WEIGHTS` (voice has no key there) and by this module's own docstrings.
- **Is this a trained model? Yes — a small one.** Voice Activity Detection itself uses pretrained/frozen backends (Silero VAD via `torch.hub`, or WebRTC VAD) — not trained here. What **is** trained is a `GradientBoostingClassifier` (scikit-learn) that recalibrates the raw VAD vote using engineered acoustic features (energy, ZCR, spectral shape, SNR, pitch).
- **Model files:**
  - `speech_confidence_calibrator.joblib` — the fitted `GradientBoostingClassifier`
  - `feature_scaler.joblib` — the fitted `StandardScaler` applied before the classifier
  - **Original path:** `ml/training/voice_analysis/checkpoints/`
  - **Package path:** `models/voice/` (also duplicated to `inference/voice/checkpoints/` for auto-discovery — see INTEGRATION_GUIDE.md)
- **Architecture/hyperparameters** (from `config.TrainerConfig`): `model_type="gradient_boosting"`, `n_estimators=200`, `max_depth=4`, `learning_rate=0.05`.
- **Framework:** scikit-learn 1.5.2, serialized via `joblib`.
- **Dataset:** binary speech-vs-non_speech — Google Speech Commands v0.02 (speech, CC BY 4.0) vs. ESC-50 (non_speech, CC BY-NC 3.0 — non-commercial only; flag this license restriction to your friend's team if the calibrator's training data provenance matters for their use).
- **Input:** the acoustic feature vector produced by `utils.acoustic_features_to_vector()` (energy/ZCR/spectral/pitch/SNR features over a 1.0s window at 16kHz).
- **Output:** blended `speech_probability = 0.6 * calibrator_proba + 0.4 * raw_VAD_vote`.
- **Actual measured metrics** (from `ml/training/voice_analysis/evaluation_artifacts/metrics.json`, a real held-out test run — not estimated): test accuracy **94.84%**, precision **93.81%**, recall **96.0%**, F1 **94.89%**, ROC-AUC **98.89%**, over 601 test samples (2,799 train / 600 val / 601 test). Mean inference latency **0.37 ms** (well within the module's 30ms budget). The module's own `performance_targets` block reports `meets_accuracy_target: false` (target was 95%, actual 94.84% — misses by 0.16 points) but `meets_precision/recall/f1/latency_target: true`.
- **Test — original file:** PASS. `VoiceAnalyzer` selected the `webrtc` VAD backend (Silero was attempted first and unavailable — see "Compatibility" below) and loaded the calibrator successfully; ran on a synthetic 1s test tone (not real speech) → returned a well-formed result with the calibrator active (`calibrator.is_fitted = True`).
- **Test — packaged copy:** PASS. Identical behavior from `inference/voice/checkpoints/*.joblib`.

## 6. Engagement / LSTM Attention-Drop Predictor

- **Category: D — No model found.**
- `ml/training/lstm_engagement/` contains only a `.gitkeep` file — no code, no notebooks, no weights.
- `backend/worker/tasks/lstm_task.py` is an explicit, self-documenting stub:
  > `"""STUB — do not register this task until ml/training/lstm_engagement/ actually exists and exports a predictor."""`
  Its Celery task body is a single `raise NotImplementedError(...)`.
- `backend/app/config.py`'s `MODEL_ARTIFACTS["lstm_engagement"]` points at `models/weights/lstm_engagement.onnx`, which **does not exist** (`models/weights/` contains only a `.gitkeep`).
- **Nothing to copy.** `models/engagement/` and `inference/engagement/` in this package are placeholders only — see the `.gitkeep`-equivalent note inside each.
- Object detection's `predictor.video_to_feature_sequence()` already produces LSTM-ready `(num_frames, 23)` feature sequences, and `backend/app/config.py`'s `ENGAGEMENT_FEATURE_WEIGHTS` documents the intended fusion formula (`eye_focus 0.30, emotion 0.20, head_pose 0.25, object_detected 0.15, multiple_person 0.10`) — but no LSTM exists to consume either. This is the one component your friend's team must build from scratch if they need it; there is no partial implementation to extend.
