"""Integration layer for the friend's trained/pretrained AI components
(see "MODEL_INTEGRATION_PACKAGE (2)/" at the project root -- her second,
updated, untouched package -- and its own README.md / MODEL_INVENTORY.md /
INTEGRATION_GUIDE.md for what she provided and how she verified it. Her
first package, MODEL_INTEGRATION_PACKAGE/MODEL_INTEGRATION_PACKAGE/, is
kept on disk untouched but is no longer read by any code here -- see
loader.py's module docstring for exactly what changed between the two).

This package wraps her Emotion, Object Detection, and Gaze/Head-Pose/
Drowsiness modules so `backend/services/ai_service.py` can call them
through a simple, uniform, never-crashes API -- selectable per-component
via the AI_OBJECT_DETECTION_MODEL / AI_LOOKING_AWAY_DROWSINESS_SOURCE /
AI_EMOTION_MODEL_SOURCE environment variables (see loader.py), falling
back to this project's own existing (pre-integration) implementation if
her code or model files are ever unavailable.

Nothing here modifies MODEL_INTEGRATION_PACKAGE/ itself -- it is treated
as a read-only vendored copy of her work. The one exception is
`gaze_headpose_pkg/ml/training/gaze_headpose/landmark_detector.py`, a
compatibility-patched COPY (not the original) -- see that file's own
docstring for exactly what changed and why.
"""
