"""Model-selection config and safe loaders for the friend's AI components.

SOURCE SELECTION
----------------
Three independent environment variables choose, per component, whether
the LIVE pipeline (backend/services/ai_service.py) uses this project's
own existing implementation ("current") or the friend's integrated one
("friend"). Each defaults to "friend" -- per the task's explicit
instruction to "initially make my friend's model available for testing"
-- but flipping back to "current" is a one-line env var change, and nothing
about the "current" code path is touched by this module:

    AI_OBJECT_DETECTION_MODEL          current | friend   (default: friend)
        current -> yolov8n.pt (this project's existing production weights)
        friend  -> her yolo11n.pt (MODEL_INTEGRATION_PACKAGE (2), stock
                   COCO-pretrained YOLOv11n -- NOT fine-tuned, same as the
                   current model's own status; see MODEL_INVENTORY.md #2).
                   Byte-identical to the weights shipped in her first
                   package -- confirmed via md5sum -- so this update did
                   not change object detection at all.

    AI_LOOKING_AWAY_DROWSINESS_SOURCE  current | friend   (default: friend)
        current -> this project's existing solvePnP + iris-ratio + EAR
                   logic in ai_service.py (unchanged, still runs every
                   frame regardless of this setting -- see that file)
        friend  -> her MediaPipe-FaceMesh + solvePnP + adaptive-EAR
                   gaze/head-pose/drowsiness pipeline (see
                   gaze_headpose_pkg/), whose result OVERRIDES gaze/
                   head_pose/sleeping for engagement scoring when active.
                   Every gaze_headpose/*.py file in her second package is
                   byte-identical to the first (confirmed via `diff -rq`),
                   so gaze_headpose_pkg/ (which already carries a required
                   compatibility patch to landmark_detector.py -- see this
                   package's own docstring) is intentionally left as-is;
                   there is nothing to update here.

    AI_EMOTION_MODEL_SOURCE            current | friend   (default: friend)
        current -> this project's own emotion_model.keras (224x224 input)
        friend  -> her emotion_model.keras (MobileNetV2, 96x96 input,
                   FER2013 -- retrained in her second package: 51.7% test
                   accuracy, up from the first package's 44%; same
                   architecture/label_map/preprocessing/output contract,
                   only the trained weights changed -- see
                   MODEL_INTEGRATION_PACKAGE (2)/MODEL_INTEGRATION_PACKAGE/
                   MODEL_INVENTORY.md #1)

Every loader below degrades honestly and never raises into the live
pipeline: if the friend's model/dependency is unavailable for any reason,
it returns None (object detection: falls back to CURRENT_YOLO_MODEL_PATH;
emotion/gaze: ai_service.py falls back to the "current" branch) and prints
one clear warning, exactly mirroring the existing face_model/emotion_model
None-fallback pattern already used elsewhere in ai_service.py.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Points at her SECOND (updated) package. Her first package
# (MODEL_INTEGRATION_PACKAGE/MODEL_INTEGRATION_PACKAGE) is left on disk
# untouched, not deleted, and not referenced by any code below -- see
# loader.py's module docstring for exactly what changed between the two
# (only the emotion model's trained weights; object detection and
# gaze/head-pose/drowsiness code+weights are byte-identical).
FRIEND_PACKAGE_ROOT = (
    _PROJECT_ROOT / "MODEL_INTEGRATION_PACKAGE (2)" / "MODEL_INTEGRATION_PACKAGE"
)

FRIEND_EMOTION_DIR = FRIEND_PACKAGE_ROOT / "inference" / "emotion"
FRIEND_OBJECT_DETECTION_DIR = FRIEND_PACKAGE_ROOT / "inference" / "object_detection"
FRIEND_GAZE_HEADPOSE_PKG_DIR = (
    Path(__file__).resolve().parent / "gaze_headpose_pkg"
)

# .onnx, not .pt: ai_service.py runs object detection through ONNX
# Runtime, not ultralytics/torch (torch alone cost ~267MB resident --
# import + model load + first real inference -- against onnxruntime's
# ~90MB for the identical job; verified detection output matches
# ultralytics exactly on real test images, both person-count and
# phone-detection, after matching its letterbox preprocessing and
# NMS IoU=0.7 default). Exported via
# YOLO('yolo11n.pt').export(format='onnx', imgsz=640, simplify=True) --
# same weights, not retrained. The .pt file is left on disk, unused by
# any code path now, not deleted.
FRIEND_YOLO_WEIGHTS_PATH = (
    FRIEND_PACKAGE_ROOT / "models" / "object_detection" / "yolo11n.onnx"
)

# See onnx_emotion_predictor.py's module docstring for why this replaced
# the friend's original Keras-based predictor.py.
FRIEND_EMOTION_ONNX_PATH = FRIEND_PACKAGE_ROOT / "models" / "emotion" / "emotion_model.onnx"
FRIEND_EMOTION_LABEL_MAP_PATH = FRIEND_PACKAGE_ROOT / "models" / "emotion" / "label_map.json"


def _source(env_var: str) -> str:
    value = os.environ.get(env_var, "friend").strip().lower()
    return value if value in ("current", "friend") else "friend"


OBJECT_DETECTION_SOURCE = _source("AI_OBJECT_DETECTION_MODEL")
LOOKING_AWAY_DROWSINESS_SOURCE = _source("AI_LOOKING_AWAY_DROWSINESS_SOURCE")
EMOTION_SOURCE = _source("AI_EMOTION_MODEL_SOURCE")


# ============================================================
# Bare-module-name isolation
# ============================================================
# The friend's emotion/object_detection code does `import config`,
# `from utils import ...`, `from predictor import ...` (object_detection
# additionally: `from tracker import ObjectTracker`) -- generic bare
# names this project's OWN code also uses in places (e.g.
# backend/database/database.py does `from config import DATABASE_PATH`,
# and ml_models/object_detection/object_detector.py does
# `from utils.logger import get_logger`). Loading her modules under
# those same bare names would silently shadow this project's own
# same-named modules for any *later* bare import, anywhere in the
# process. This context manager makes that window as small as possible:
# it inserts her module's directory at the front of sys.path, clears
# any current bindings for the given bare names, lets the caller do the
# import, then restores exactly what was there before (whether or not an
# exception occurred) -- so once a friend predictor has been constructed
# and its bound methods captured, nothing about this process's bare
# "config"/"utils"/etc. imports is left different from before.
@contextmanager
def _isolated_bare_imports(directory: Path, bare_names: tuple):
    directory_str = str(directory)
    path_inserted = directory_str not in sys.path
    if path_inserted:
        sys.path.insert(0, directory_str)

    saved = {name: sys.modules.get(name) for name in bare_names}
    for name in bare_names:
        sys.modules.pop(name, None)

    try:
        yield
    finally:
        if path_inserted:
            try:
                sys.path.remove(directory_str)
            except ValueError:
                pass
        for name, module in saved.items():
            if module is not None:
                sys.modules[name] = module
            else:
                sys.modules.pop(name, None)


# ============================================================
# Object detection -- just a weights path; ai_service.py loads it through
# the SAME `ultralytics.YOLO(...)` call it already uses for the current
# model, so no wrapper class is needed here.
# ============================================================
def resolve_object_detection_weights_path(current_weights_path: str) -> tuple:
    """Returns (weights_path, source_actually_used)."""
    if OBJECT_DETECTION_SOURCE == "friend":
        if FRIEND_YOLO_WEIGHTS_PATH.exists():
            return str(FRIEND_YOLO_WEIGHTS_PATH), "friend"
        print(
            f"WARNING: AI_OBJECT_DETECTION_MODEL=friend but "
            f"{FRIEND_YOLO_WEIGHTS_PATH} was not found. "
            f"Falling back to the current model ({current_weights_path})."
        )
    return current_weights_path, "current"


# ============================================================
# Emotion
# ============================================================
_friend_emotion_predictor = None
_friend_emotion_load_attempted = False
_friend_emotion_error: Optional[str] = None


def get_friend_emotion_predictor():
    """Lazily loads and caches the friend's emotion predictor once per
    process. Returns None (and prints one warning) if unavailable --
    never raises.

    Uses ONNXEmotionPredictor (onnx_emotion_predictor.py), not her
    original Keras-based predictor.py -- same weights, same
    preprocessing, numerically verified matching output, ~67MB lighter.
    See that module's docstring for the full explanation."""
    global _friend_emotion_predictor, _friend_emotion_load_attempted, _friend_emotion_error

    if _friend_emotion_load_attempted:
        return _friend_emotion_predictor

    _friend_emotion_load_attempted = True

    if not FRIEND_EMOTION_ONNX_PATH.exists():
        _friend_emotion_error = f"Friend emotion ONNX model not found at {FRIEND_EMOTION_ONNX_PATH}"
        print(f"WARNING: {_friend_emotion_error}. Emotion source falls back to 'current'.")
        return None

    try:
        from services.friend_ai.onnx_emotion_predictor import ONNXEmotionPredictor

        _friend_emotion_predictor = ONNXEmotionPredictor(
            FRIEND_EMOTION_ONNX_PATH, FRIEND_EMOTION_LABEL_MAP_PATH
        )
    except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
        _friend_emotion_error = str(exc)
        print(
            f"WARNING: Friend emotion model failed to load ({exc}). "
            f"Emotion source falls back to 'current'."
        )
        _friend_emotion_predictor = None

    return _friend_emotion_predictor


# ============================================================
# Gaze / head-pose / drowsiness
# ============================================================
_gaze_headpose_import_error: Optional[str] = None
_gaze_headpose_import_attempted = False


def _import_gaze_headpose_predictor_class():
    """Adds the (compatibility-patched) gaze_headpose package directory
    to sys.path once and returns the GazeHeadPosePredictor class, or None
    if it can't be imported."""
    global _gaze_headpose_import_error, _gaze_headpose_import_attempted

    if _gaze_headpose_import_attempted:
        if _gaze_headpose_import_error is not None:
            return None
    else:
        _gaze_headpose_import_attempted = True

        directory_str = str(FRIEND_GAZE_HEADPOSE_PKG_DIR)
        if directory_str not in sys.path:
            sys.path.insert(0, directory_str)

    try:
        from ml.training.gaze_headpose.predictor import GazeHeadPosePredictor  # type: ignore

        return GazeHeadPosePredictor
    except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
        _gaze_headpose_import_error = str(exc)
        print(
            f"WARNING: Friend gaze/head-pose/drowsiness module failed to "
            f"import ({exc}). This source falls back to 'current'."
        )
        return None


def new_friend_gaze_headpose_predictor():
    """Creates a NEW, per-student-session GazeHeadPosePredictor instance
    (it is stateful -- adaptive EAR baseline, blink counters, temporal
    smoothers -- so it must not be shared across students/sessions; see
    INTEGRATION_GUIDE.md "Instantiate ONCE PER STUDENT SESSION"). Returns
    None (never raises) if the module or its dependencies are unavailable.
    """
    cls = _import_gaze_headpose_predictor_class()
    if cls is None:
        return None
    try:
        return cls()
    except Exception as exc:  # noqa: BLE001 -- must degrade, never crash.
        print(f"WARNING: Failed to instantiate friend gaze/head-pose predictor ({exc}).")
        return None


def status() -> dict:
    """Side-effect-free-ish (loaders are cached) health/status summary,
    for a manual-verification endpoint and the integration report --
    never fabricated, reflects exactly what actually loaded."""
    return {
        "object_detection": {
            "source_configured": OBJECT_DETECTION_SOURCE,
            "friend_weights_path": str(FRIEND_YOLO_WEIGHTS_PATH),
            "friend_weights_found": FRIEND_YOLO_WEIGHTS_PATH.exists(),
        },
        "looking_away_drowsiness": {
            "source_configured": LOOKING_AWAY_DROWSINESS_SOURCE,
            "friend_module_dir": str(FRIEND_GAZE_HEADPOSE_PKG_DIR),
            "friend_import_error": _gaze_headpose_import_error,
        },
        "emotion": {
            "source_configured": EMOTION_SOURCE,
            "friend_onnx_path": str(FRIEND_EMOTION_ONNX_PATH),
            "friend_onnx_found": FRIEND_EMOTION_ONNX_PATH.exists(),
            "friend_load_attempted": _friend_emotion_load_attempted,
            "friend_loaded": _friend_emotion_predictor is not None,
            "friend_error": _friend_emotion_error,
        },
    }
