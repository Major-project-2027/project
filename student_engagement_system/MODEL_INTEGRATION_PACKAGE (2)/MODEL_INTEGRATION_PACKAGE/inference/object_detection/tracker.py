"""
tracker.py
----------
Multi-object tracking for Module 5.

Primary implementation: Ultralytics' built-in **ByteTrack** (via
`model.track(tracker="bytetrack.yaml")`), which `detector.py` already
supports through its `track=True` argument — this module's job is to
orchestrate that call correctly across a video/stream (persisting state
frame-to-frame, resetting between unrelated videos, falling back to
BoT-SORT if ByteTrack's dependencies are unavailable) and to provide a
last-resort custom IOU tracker for the (rare) case neither Ultralytics
tracker can run.

Why not hand-roll ByteTrack from scratch: it is a real, published
algorithm (Zhang et al., 2022) with a non-trivial two-stage
high/low-confidence association strategy and a Kalman-filter motion
model — re-implementing it would be slower, more bug-prone, and
duplicate a maintained, tested implementation already shipped with the
`ultralytics` dependency this whole module is built on.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

import config
from detector import ObjectDetector
from utils import BoundingBox, Detection, FrameResult, build_frame_events, get_logger

logger = get_logger(__name__)


class CustomIOUTracker:
    """Lightweight, dependency-free greedy IOU tracker — the fallback of
    last resort if neither `bytetrack.yaml` nor `botsort.yaml` can be
    used (e.g. the `lap` package ByteTrack needs for linear assignment
    isn't installed). Matching is restricted to detections of the SAME
    class_name, so a chair can never be matched against a person track
    even if their boxes happen to overlap.

    This is intentionally simple (no Kalman filter, no re-identification
    on long occlusion) — it exists to guarantee the module still returns
    *some* persistent IDs rather than hard-failing, not to match
    ByteTrack's accuracy.
    """

    def __init__(
        self,
        iou_threshold: float = config.CUSTOM_TRACKER_IOU_THRESHOLD,
        max_missed_frames: int = config.CUSTOM_TRACKER_MAX_MISSED_FRAMES,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed_frames = max_missed_frames
        self._next_id = 1
        self._tracks: dict[int, dict] = {}  # track_id -> {"class_name": str, "bbox": BoundingBox, "missed": int}

    def reset(self) -> None:
        self._next_id = 1
        self._tracks.clear()

    def update(self, detections: list[Detection]) -> list[Detection]:
        """Assigns `track_id` (and `person_id` where applicable) to each
        Detection in-place and returns the same list."""
        unmatched_detection_indices = list(range(len(detections)))
        matched_track_ids: set[int] = set()

        for track_id, track in list(self._tracks.items()):
            best_iou, best_idx = 0.0, None
            for idx in unmatched_detection_indices:
                det = detections[idx]
                if det.class_name != track["class_name"]:
                    continue
                iou = track["bbox"].iou(det.bbox)
                if iou > best_iou:
                    best_iou, best_idx = iou, idx

            if best_idx is not None and best_iou >= self.iou_threshold:
                det = detections[best_idx]
                det.track_id = track_id
                det.person_id = track_id if det.class_name in config.PERSON_LIKE_CLASSES else None
                track["bbox"] = det.bbox
                track["missed"] = 0
                matched_track_ids.add(track_id)
                unmatched_detection_indices.remove(best_idx)
            else:
                track["missed"] += 1

        for track_id in list(self._tracks.keys()):
            if self._tracks[track_id]["missed"] > self.max_missed_frames:
                del self._tracks[track_id]

        for idx in unmatched_detection_indices:
            det = detections[idx]
            new_id = self._next_id
            self._next_id += 1
            det.track_id = new_id
            det.person_id = new_id if det.class_name in config.PERSON_LIKE_CLASSES else None
            self._tracks[new_id] = {"class_name": det.class_name, "bbox": det.bbox, "missed": 0}
            matched_track_ids.add(new_id)

        return detections


class ObjectTracker:
    """High-level tracking entry point used by predictor.py. Wraps an
    `ObjectDetector` and drives it in tracking mode, with automatic
    ByteTrack -> BoT-SORT -> CustomIOUTracker fallback.

    Usage:
        tracker = ObjectTracker(detector)
        for frame in video_frames:
            result = tracker.track_frame(frame)   # FrameResult with populated track_id/person_id
        tracker.reset()  # call between unrelated videos/streams
    """

    def __init__(self, detector: Optional[ObjectDetector] = None) -> None:
        self.detector = detector or ObjectDetector()
        self._active_tracker_config = config.TRACKER_PRIMARY
        self._ultralytics_tracking_failed = False
        self._fallback_tracker = CustomIOUTracker()

    def track_frame(self, frame: np.ndarray) -> FrameResult:
        if not self._ultralytics_tracking_failed:
            try:
                return self.detector.detect(frame, track=True, tracker_config=self._active_tracker_config)
            except Exception as e:  # noqa: BLE001 - genuinely many possible failure modes (missing `lap`, etc.)
                if self._active_tracker_config == config.TRACKER_PRIMARY:
                    logger.warning(
                        "Primary tracker '%s' failed (%s) — retrying with fallback tracker '%s'.",
                        config.TRACKER_PRIMARY, e, config.TRACKER_FALLBACK,
                    )
                    self._active_tracker_config = config.TRACKER_FALLBACK
                    try:
                        return self.detector.detect(frame, track=True, tracker_config=self._active_tracker_config)
                    except Exception as e2:  # noqa: BLE001
                        logger.error(
                            "Fallback tracker '%s' also failed (%s) — switching to CustomIOUTracker for "
                            "the remainder of this session.",
                            config.TRACKER_FALLBACK, e2,
                        )
                        self._ultralytics_tracking_failed = True
                else:
                    logger.error(
                        "Fallback tracker '%s' failed (%s) — switching to CustomIOUTracker.",
                        self._active_tracker_config, e,
                    )
                    self._ultralytics_tracking_failed = True

        # Ultralytics tracking unavailable — detect (stateless) then track with the custom IOU tracker.
        if not config.USE_CUSTOM_IOU_TRACKER_FALLBACK:
            raise RuntimeError(
                "Ultralytics tracking failed and config.USE_CUSTOM_IOU_TRACKER_FALLBACK is False — "
                "no tracker available."
            )

        frame_result = self.detector.detect(frame, track=False)
        frame_result.detections = self._fallback_tracker.update(frame_result.detections)
        frame_result.events = build_frame_events(frame_result.detections)
        return frame_result

    def reset(self) -> None:
        """Reset all tracker state — call between unrelated videos/streams
        so track IDs (and hence person_ids) don't carry over."""
        self.detector.reset_tracker_state()
        self._fallback_tracker.reset()
        self._active_tracker_config = config.TRACKER_PRIMARY
        self._ultralytics_tracking_failed = False
        logger.info("ObjectTracker fully reset.")


if __name__ == "__main__":
    detector = ObjectDetector()
    tracker = ObjectTracker(detector)
    dummy_frame = np.zeros((480, 640, 3), dtype="uint8")
    result = tracker.track_frame(dummy_frame)
    print(result.to_dict())
