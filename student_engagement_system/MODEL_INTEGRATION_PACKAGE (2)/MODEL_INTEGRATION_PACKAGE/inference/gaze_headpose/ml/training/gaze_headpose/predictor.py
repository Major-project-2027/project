"""
predictor.py
------------
Production inference API for the Gaze & Head Pose Estimation module.

Purpose
-------
`GazeHeadPosePredictor` is the single integration point other modules
(and a future Celery inference worker under
`ml/inference-services/gaze-headpose-worker/`) should import. It wires
together every component in this package — landmark detection, face
quality, gaze estimation, head-pose estimation, blink detection,
drowsiness detection, and temporal smoothing — into one coherent
per-frame result, and exposes convenience methods for every inference
mode required by the module spec:

  - `predict_frame()`       — single in-memory BGR frame (streaming use)
  - `predict_image_file()`  — a single image file (no temporal state)
  - `predict_batch_files()` — a list of independent image files
  - `run_webcam()`          — real-time webcam demo with on-screen overlay
  - `run_video_file()`      — process a saved video file, optional annotated export

Output format
-------------
`GazeHeadPoseFrameResult.to_dict()` returns a flat, JSON-serializable
dict designed to slot directly into the architecture document's Feature
Aggregator (Section 4.1: "all 4 workers publish to frame.features keyed
by session_id+student_id+timestamp") alongside Module 1 (Emotion) and
Module 2 (Face Authentication) output, and ahead of Module 4 (Object
Detection) — with no architectural changes required to integrate them.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from ml.training.gaze_headpose import config, utils
from ml.training.gaze_headpose.blink_detector import BlinkDetector, BlinkFrameResult
from ml.training.gaze_headpose.drowsiness_detector import DrowsinessDetector, DrowsinessResult
from ml.training.gaze_headpose.face_quality import FaceQualityAssessor, FaceQualityResult
from ml.training.gaze_headpose.gaze_estimator import GazeEstimationResult, GazeEstimator
from ml.training.gaze_headpose.headpose_estimator import HeadPoseEstimator, HeadPoseResult
from ml.training.gaze_headpose.landmark_detector import FaceLandmarkDetector, FaceLandmarkResult
from ml.training.gaze_headpose.temporal_filter import MultiSignalSmoother

logger = utils.get_logger(__name__)

_SMOOTHED_SIGNALS = ("yaw", "pitch", "roll", "gaze_horizontal_ratio", "gaze_vertical_ratio")


@dataclass
class GazeHeadPoseFrameResult:
    """Unified, per-frame result combining every sub-component's output."""

    timestamp: float
    face_detected: bool
    quality: Optional[FaceQualityResult] = None
    gaze: Optional[GazeEstimationResult] = None
    headpose: Optional[HeadPoseResult] = None
    blink: Optional[BlinkFrameResult] = None
    drowsiness: Optional[DrowsinessResult] = None
    overall_confidence: float = 0.0
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict:
        """Flat, JSON-serializable representation for downstream fusion/storage."""
        return {
            "timestamp": self.timestamp,
            "face_detected": self.face_detected,
            "overall_confidence": self.overall_confidence,
            "processing_time_ms": self.processing_time_ms,
            "quality_score": self.quality.quality_score if self.quality else None,
            "quality_accepted": self.quality.accepted if self.quality else None,
            "gaze_direction": self.gaze.direction if self.gaze else None,
            "gaze_confidence": self.gaze.confidence if self.gaze else None,
            "gaze_horizontal_ratio": self.gaze.horizontal_ratio if self.gaze else None,
            "gaze_vertical_ratio": self.gaze.vertical_ratio if self.gaze else None,
            "gaze_screen_x": self.gaze.screen_coordinate[0] if (self.gaze and self.gaze.screen_coordinate) else None,
            "gaze_screen_y": self.gaze.screen_coordinate[1] if (self.gaze and self.gaze.screen_coordinate) else None,
            "head_pitch_deg": self.headpose.pitch if self.headpose else None,
            "head_yaw_deg": self.headpose.yaw if self.headpose else None,
            "head_roll_deg": self.headpose.roll if self.headpose else None,
            "head_pose_classification": self.headpose.classification if self.headpose else None,
            "ear_average": self.blink.average_ear if self.blink else None,
            "eyes_closed": self.blink.eyes_closed if self.blink else None,
            "blink_count": self.blink.total_blink_count if self.blink else None,
            "blink_rate_per_minute": self.blink.blink_rate_per_minute if self.blink else None,
            "drowsiness_state": self.drowsiness.state if self.drowsiness else None,
            "drowsiness_confidence": self.drowsiness.confidence if self.drowsiness else None,
        }


class GazeHeadPosePredictor:
    """
    Stateful, real-time-ready predictor. Instantiate once per monitored
    stream/session (mirrors the architecture document's "per student, per
    session" framing) and call `predict_frame()` once per sampled frame.
    Call `reset()` when a new session starts for the same predictor
    instance (e.g. a new student joins using a pooled worker).
    """

    def __init__(self, use_temporal_smoothing: bool = True):
        self.use_temporal_smoothing = use_temporal_smoothing

        self.landmark_detector = FaceLandmarkDetector()
        self.quality_assessor = FaceQualityAssessor()
        self.gaze_estimator = GazeEstimator()
        self.headpose_estimator = HeadPoseEstimator()
        self.blink_detector = BlinkDetector()
        self.drowsiness_detector = DrowsinessDetector()
        self.smoother = MultiSignalSmoother(_SMOOTHED_SIGNALS) if use_temporal_smoothing else None

    def close(self) -> None:
        self.landmark_detector.close()

    def __enter__(self) -> "GazeHeadPosePredictor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def reset(self) -> None:
        """Reset all temporal/stateful sub-components for a new session."""
        self.blink_detector.reset()
        self.drowsiness_detector.reset()
        if self.smoother is not None:
            self.smoother.reset()

    # ------------------------------------------------------------------
    # Core per-frame prediction
    # ------------------------------------------------------------------
    def predict_frame(self, bgr_frame: np.ndarray, timestamp: Optional[float] = None) -> GazeHeadPoseFrameResult:
        start = time.perf_counter()
        now = timestamp if timestamp is not None else time.time()

        landmark_result = self.landmark_detector.process(bgr_frame)
        if not landmark_result.detected or not landmark_result.is_valid:
            return GazeHeadPoseFrameResult(
                timestamp=now, face_detected=False, processing_time_ms=(time.perf_counter() - start) * 1000.0
            )

        quality_result = self.quality_assessor.assess(bgr_frame, landmark_result)
        gaze_result = self.gaze_estimator.estimate(landmark_result)
        headpose_result = self.headpose_estimator.estimate(landmark_result)
        blink_result = self.blink_detector.update(landmark_result, now)
        drowsiness_result = self.drowsiness_detector.update(
            blink_result, self.blink_detector.current_closure_duration_seconds
        )

        if self.smoother is not None and headpose_result.valid and gaze_result.valid:
            smoothed = self.smoother.update(
                {
                    "yaw": headpose_result.yaw,
                    "pitch": headpose_result.pitch,
                    "roll": headpose_result.roll,
                    "gaze_horizontal_ratio": gaze_result.horizontal_ratio,
                    "gaze_vertical_ratio": gaze_result.vertical_ratio,
                }
            )
            headpose_result.yaw = smoothed["yaw"]
            headpose_result.pitch = smoothed["pitch"]
            headpose_result.roll = smoothed["roll"]
            headpose_result.classification = self.headpose_estimator._classify(
                headpose_result.pitch, headpose_result.yaw
            )
            gaze_result.horizontal_ratio = smoothed["gaze_horizontal_ratio"]
            gaze_result.vertical_ratio = smoothed["gaze_vertical_ratio"]
            gaze_result.direction = self.gaze_estimator._classify_direction(
                gaze_result.horizontal_ratio, gaze_result.vertical_ratio
            )
            stability = self.smoother.stability_score(
                {"yaw": headpose_result.yaw, "gaze_h": gaze_result.horizontal_ratio}
            )
        else:
            stability = 1.0

        overall_confidence = self._compute_overall_confidence(
            landmark_result, quality_result, stability
        )

        return GazeHeadPoseFrameResult(
            timestamp=now,
            face_detected=True,
            quality=quality_result,
            gaze=gaze_result,
            headpose=headpose_result,
            blink=blink_result,
            drowsiness=drowsiness_result,
            overall_confidence=overall_confidence,
            processing_time_ms=(time.perf_counter() - start) * 1000.0,
        )

    @staticmethod
    def _compute_overall_confidence(
        landmark_result: FaceLandmarkResult, quality_result: FaceQualityResult, stability: float
    ) -> float:
        weights = config.CONFIDENCE_WEIGHTS
        detection_component = landmark_result.detection_confidence
        quality_component = quality_result.quality_score if quality_result.valid else 0.0
        raw = (
            weights["detection"] * detection_component
            + weights["quality"] * quality_component
            + weights["stability"] * stability
        )
        return utils.clamp(raw, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Single image / batch (no cross-image temporal state)
    # ------------------------------------------------------------------
    def predict_image_file(self, image_path: Path) -> GazeHeadPoseFrameResult:
        import cv2

        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"Could not read image at {image_path}")
        self.reset()
        return self.predict_frame(frame)

    def predict_batch_files(self, image_paths: List[Path]) -> List[GazeHeadPoseFrameResult]:
        """
        Predict on a list of independent images. Temporal state is reset
        before each image so unrelated images never smooth into one
        another.
        """
        results = []
        for path in image_paths:
            results.append(self.predict_image_file(path))
        return results

    # ------------------------------------------------------------------
    # Webcam real-time demo
    # ------------------------------------------------------------------
    def run_webcam(self, camera_index: int = config.DEFAULT_CAMERA_INDEX, window_name: str = "Gaze & Head Pose") -> None:
        import cv2

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError(
                f"Could not open webcam at index {camera_index}. "
                "In a headless/server environment, use predict_image_file() "
                "or run_video_file() instead."
            )

        self.reset()
        fps_meter = utils.FPSMeter()
        print("Press 'q' to quit the webcam demo.")

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                result = self.predict_frame(frame)
                self._draw_overlay(frame, result)
                fps = fps_meter.tick()
                utils.draw_text_with_background(frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 10), (255, 255, 0))

                cv2.imshow(window_name, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

    # ------------------------------------------------------------------
    # Video file processing
    # ------------------------------------------------------------------
    def run_video_file(self, video_path: Path, output_path: Optional[Path] = None) -> List[GazeHeadPoseFrameResult]:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video file at {video_path}")

        self.reset()
        results: List[GazeHeadPoseFrameResult] = []

        writer = None
        if output_path is not None:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            fps = cap.get(cv2.CAP_PROP_FPS) or config.REALTIME_TARGET_FPS
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                result = self.predict_frame(frame)
                results.append(result)
                if writer is not None:
                    self._draw_overlay(frame, result)
                    writer.write(frame)
        finally:
            cap.release()
            if writer is not None:
                writer.release()

        return results

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    @staticmethod
    def _draw_overlay(frame: np.ndarray, result: GazeHeadPoseFrameResult) -> None:
        import cv2

        if not result.face_detected:
            utils.draw_text_with_background(frame, "No face detected", (10, 30), (0, 0, 255))
            return

        lines = []
        if result.headpose and result.headpose.valid:
            lines.append(
                f"Pose: {result.headpose.classification} "
                f"(yaw {result.headpose.yaw:.0f}, pitch {result.headpose.pitch:.0f})"
            )
        if result.gaze and result.gaze.valid:
            lines.append(f"Gaze: {result.gaze.direction} ({result.gaze.confidence:.0%})")
        if result.blink:
            lines.append(f"EAR: {result.blink.average_ear:.2f} | Blinks: {result.blink.total_blink_count}")
        if result.drowsiness and result.drowsiness.valid:
            lines.append(f"State: {result.drowsiness.state}")
        lines.append(f"Confidence: {result.overall_confidence:.0%}")

        for i, line in enumerate(lines):
            utils.draw_text_with_background(frame, line, (10, 30 + i * 26))


def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Gaze & Head Pose Estimation inference CLI")
    parser.add_argument("--webcam", action="store_true", help="Run the real-time webcam demo")
    parser.add_argument("--image", type=str, default=None, help="Path to a single image to analyze")
    parser.add_argument("--video", type=str, default=None, help="Path to a video file to analyze")
    parser.add_argument("--output", type=str, default=None, help="Optional annotated output video path")
    args = parser.parse_args()

    with GazeHeadPosePredictor() as predictor:
        if args.webcam:
            predictor.run_webcam()
        elif args.image:
            result = predictor.predict_image_file(Path(args.image))
            import json

            print(json.dumps(result.to_dict(), indent=2))
        elif args.video:
            output_path = Path(args.output) if args.output else None
            results = predictor.run_video_file(Path(args.video), output_path=output_path)
            print(f"Processed {len(results)} frames.")
        else:
            parser.print_help()


if __name__ == "__main__":
    _cli()
