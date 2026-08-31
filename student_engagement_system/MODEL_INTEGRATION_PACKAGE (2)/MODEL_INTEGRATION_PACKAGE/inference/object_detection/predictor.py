"""
predictor.py
------------
High-level inference API for Module 5 — the file most other code
(notebooks, a future backend `object-detection-worker`) should import
from. Wraps `ObjectTracker` (which wraps `ObjectDetector`) and adds:
image / folder / video / webcam / streaming inference, visualization
overlay, FPS/latency reporting, and batch feature-vector export for the
downstream LSTM module.

Every public method returns (or yields) `utils.FrameResult` objects —
the one stable output contract for this whole module.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator, Optional, Union

import numpy as np

import config
from tracker import ObjectTracker
from utils import (
    FPSCounter,
    FrameResult,
    PerformanceTimer,
    detections_to_feature_vector,
    draw_detections,
    get_logger,
    get_system_usage,
)

logger = get_logger(__name__)


class ObjectDetectionPredictor:
    """Single entry point for every inference mode this module supports."""

    def __init__(self, tracker: Optional[ObjectTracker] = None) -> None:
        config.ensure_directories()
        self.tracker = tracker or ObjectTracker()
        self._fps_counter = FPSCounter()

    # ------------------------------------------------------------------
    # Single image
    # ------------------------------------------------------------------
    def predict_image(self, image: Union[str, Path, np.ndarray], use_tracking: bool = False) -> FrameResult:
        """Run inference on a single image (file path or already-loaded
        BGR ndarray). `use_tracking=False` by default since a lone still
        image has no track history to persist — set True only if you're
        feeding sequential frames one at a time via this method (prefer
        `predict_video`/`predict_webcam` for that instead, which handle
        tracker state correctly across the whole sequence).
        """
        import cv2

        if isinstance(image, (str, Path)):
            frame = cv2.imread(str(image))
            if frame is None:
                raise FileNotFoundError(f"Could not read image: {image}")
        else:
            frame = image

        with PerformanceTimer() as timer:
            if use_tracking:
                result = self.tracker.track_frame(frame)
            else:
                result = self.tracker.detector.detect(frame, track=False)
        # detector.detect() already measures its own latency; PerformanceTimer here
        # additionally captures this method's total wall time for logging/debugging.
        logger.debug("predict_image total wall time: %.2f ms", timer.elapsed_ms)
        return result

    # ------------------------------------------------------------------
    # Folder of images (batch inference)
    # ------------------------------------------------------------------
    def predict_folder(
        self,
        folder_path: Union[str, Path],
        extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".bmp"),
        show_progress: bool = True,
    ) -> list[tuple[Path, FrameResult]]:
        """Run inference on every image in a folder. Each image is
        independent (no tracking carried between them, since folder
        images are not assumed to be a temporal sequence)."""
        folder_path = Path(folder_path)
        image_paths = sorted(p for p in folder_path.iterdir() if p.suffix.lower() in extensions)

        if not image_paths:
            logger.warning("No images with extensions %s found in %s", extensions, folder_path)
            return []

        iterator = image_paths
        if show_progress:
            from tqdm import tqdm

            iterator = tqdm(image_paths, desc=f"Detecting objects in {folder_path.name}", unit="img")

        results: list[tuple[Path, FrameResult]] = []
        for path in iterator:
            frame_result = self.predict_image(path, use_tracking=False)
            results.append((path, frame_result))

        return results

    # ------------------------------------------------------------------
    # Video file
    # ------------------------------------------------------------------
    def predict_video(
        self,
        video_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        show_progress: bool = True,
        frame_skip: int = 0,
    ) -> Iterator[FrameResult]:
        """Run tracked inference over every frame of a video file,
        yielding one `FrameResult` per processed frame. If `output_path`
        is given, writes an annotated copy of the video (bounding
        boxes/labels/HUD burned in) to that path.

        `frame_skip`: process every (frame_skip + 1)-th frame (0 = every
        frame). Skipped frames are NOT yielded and do not advance track
        "missed frame" counters artificially fast — this trades temporal
        resolution for throughput on slow hardware, a reasonable
        real-time knob for CPU-only deployments.
        """
        import cv2

        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps_native = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer = None
        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_path), fourcc, fps_native, (frame_width, frame_height))

        self.tracker.reset()

        progress = None
        if show_progress:
            from tqdm import tqdm

            progress = tqdm(total=total_frames, desc=f"Processing {video_path.name}", unit="frame")

        frame_idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if frame_skip > 0 and frame_idx % (frame_skip + 1) != 0:
                    frame_idx += 1
                    if progress:
                        progress.update(1)
                    continue

                result = self.tracker.track_frame(frame)

                if writer is not None:
                    annotated = draw_detections(frame.copy(), result)
                    writer.write(annotated)

                yield result

                frame_idx += 1
                if progress:
                    progress.update(1)
        finally:
            cap.release()
            if writer is not None:
                writer.release()
            if progress:
                progress.close()

    # ------------------------------------------------------------------
    # Webcam (live display)
    # ------------------------------------------------------------------
    def run_webcam(self, camera_index: int = 0, mirror: bool = True, record_to: Optional[Union[str, Path]] = None) -> None:
        """Open the local webcam, run tracked inference live, and display
        an annotated window (bounding boxes, labels, confidence, track
        IDs, person/object counts, FPS, latency). Press 'q' to quit.

        `record_to`: optional path to also save the annotated stream as
        an .mp4 while it plays.
        """
        import cv2

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open webcam at index {camera_index}.")

        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

        writer = None
        if record_to is not None:
            record_to = Path(record_to)
            record_to.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(record_to), fourcc, 20.0, (frame_width, frame_height))

        self.tracker.reset()
        logger.info("Webcam object-detection demo running. Press 'q' to quit.")

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    logger.warning("Failed to read frame from webcam; stopping.")
                    break
                if mirror:
                    frame = cv2.flip(frame, 1)

                result = self.tracker.track_frame(frame)
                annotated = draw_detections(frame, result)

                if writer is not None:
                    writer.write(annotated)

                cv2.imshow("Object Detection (press q to quit)", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            cap.release()
            if writer is not None:
                writer.release()
            cv2.destroyAllWindows()

    # ------------------------------------------------------------------
    # Streaming inference (RTSP / HTTP stream / webcam URL)
    # ------------------------------------------------------------------
    def predict_stream(self, source: str) -> Iterator[FrameResult]:
        """Generator over an arbitrary OpenCV-readable stream source
        (RTSP URL, HTTP MJPEG stream, or a numeric webcam index passed as
        a string). Yields `FrameResult` per frame with no display/window
        — intended for a headless service (e.g. the future
        `object-detection-worker` consuming a classroom's live feed).
        """
        import cv2

        cap_source: Union[str, int] = int(source) if source.isdigit() else source
        cap = cv2.VideoCapture(cap_source)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open stream source: {source}")

        self.tracker.reset()
        logger.info("Streaming inference started for source: %s", source)

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    logger.warning("Stream read failed or ended: %s", source)
                    break
                yield self.tracker.track_frame(frame)
        finally:
            cap.release()

    # ------------------------------------------------------------------
    # Batch feature-vector export (for the downstream LSTM module)
    # ------------------------------------------------------------------
    def video_to_feature_sequence(
        self,
        video_path: Union[str, Path],
        frame_skip: int = 0,
        show_progress: bool = True,
    ) -> np.ndarray:
        """Convenience wrapper: run `predict_video` over a full video and
        stack every frame's `detections_to_feature_vector()` output into
        one (num_frames, FEATURE_VECTOR_LENGTH) array — directly usable
        as the input sequence to an LSTM (Module 6) with no further
        preprocessing.
        """
        vectors = [
            detections_to_feature_vector(result)
            for result in self.predict_video(video_path, frame_skip=frame_skip, show_progress=show_progress)
        ]
        if not vectors:
            return np.empty((0, 23), dtype="float32")
        return np.stack(vectors, axis=0)

    # ------------------------------------------------------------------
    def benchmark_latency(self, num_frames: int = 50, image_size: Optional[int] = None) -> dict:
        """Run `num_frames` synthetic-frame inferences (random noise
        images at the configured/overridden resolution) and report
        latency/FPS/CPU/RAM statistics — used by evaluate_model.ipynb's
        latency report and by trainer.py."""
        size = image_size or config.INFERENCE_IMAGE_SIZE
        dummy_frame = np.random.randint(0, 255, (size, size, 3), dtype="uint8")

        # warm-up (first inference includes model/graph initialization overhead)
        self.tracker.detector.detect(dummy_frame, track=False)

        latencies_ms = []
        for _ in range(num_frames):
            with PerformanceTimer() as timer:
                self.tracker.detector.detect(dummy_frame, track=False)
            latencies_ms.append(timer.elapsed_ms)

        latencies_ms = np.array(latencies_ms)
        usage = get_system_usage()

        return {
            "num_frames": num_frames,
            "image_size": size,
            "mean_latency_ms": float(latencies_ms.mean()),
            "median_latency_ms": float(np.median(latencies_ms)),
            "p95_latency_ms": float(np.percentile(latencies_ms, 95)),
            "min_latency_ms": float(latencies_ms.min()),
            "max_latency_ms": float(latencies_ms.max()),
            "mean_fps": float(1000.0 / latencies_ms.mean()),
            **usage,
        }


if __name__ == "__main__":
    predictor = ObjectDetectionPredictor()
    report = predictor.benchmark_latency(num_frames=20)
    print(report)
