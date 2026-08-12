"""
Webcam capture module for the Face Authentication subsystem.

Every module that needs a live camera stream (registration, live
authentication) goes through WebcamStream instead of calling
cv2.VideoCapture directly, so device selection, resolution, FPS, and
cleanup are handled consistently everywhere.
"""
from typing import Optional, Tuple

import cv2
import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)


class WebcamError(Exception):
    """Raised when a webcam cannot be opened or read from."""


class WebcamStream:
    """Context-manager wrapper around cv2.VideoCapture.

    Example:
        >>> with WebcamStream(device_index=0, width=640, height=480) as cam:
        ...     frame = cam.read_frame()
    """

    def __init__(self, device_index: int = 0, width: int = 640, height: int = 480,
                 fps: int = 30) -> None:
        self.device_index = device_index
        self.width = width
        self.height = height
        self.fps = fps
        self._cap: Optional[cv2.VideoCapture] = None

    def open(self) -> "WebcamStream":
        """Open the configured camera device.

        Raises:
            WebcamError: If the device cannot be opened.
        """
        self._cap = cv2.VideoCapture(self.device_index)
        if not self._cap.isOpened():
            self._cap = None
            raise WebcamError(f"Could not open camera at index {self.device_index}.")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logger.info(
            f"Camera {self.device_index} opened -- requested {self.width}x{self.height}, "
            f"actual {actual_w}x{actual_h}"
        )
        return self

    def read_frame(self) -> np.ndarray:
        """Read a single frame from the open camera.

        Returns:
            The captured BGR frame as a NumPy array.

        Raises:
            WebcamError: If the camera is not open or the frame could not be read.
        """
        if self._cap is None or not self._cap.isOpened():
            raise WebcamError("Camera is not open. Call open() or use as a context manager.")
        ret, frame = self._cap.read()
        if not ret or frame is None:
            raise WebcamError("Failed to read a frame from the camera.")
        return frame

    def release(self) -> None:
        """Release the camera device, if open. Safe to call multiple times."""
        if self._cap is not None:
            self._cap.release()
            logger.info(f"Camera {self.device_index} released.")
            self._cap = None

    def __enter__(self) -> "WebcamStream":
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def verify_camera(device_index: int = 0) -> Tuple[bool, str]:
    """Check whether a camera index can be opened and read from, without raising.

    Args:
        device_index: Camera device index to test.

    Returns:
        A (success, message) tuple describing the result.
    """
    cap = cv2.VideoCapture(device_index)
    try:
        if not cap.isOpened():
            return False, f"Camera {device_index} could not be opened."
        ret, frame = cap.read()
        if not ret or frame is None:
            return False, f"Camera {device_index} opened but returned no frame."
        return True, f"Camera {device_index} OK -- frame shape {frame.shape}."
    finally:
        cap.release()


def list_available_cameras(max_index: int = 5) -> list:
    """Probe camera indices 0..max_index-1 and report which ones are usable.

    Args:
        max_index: Number of indices to probe.

    Returns:
        List of device indices that opened successfully.
    """
    available = []
    for idx in range(max_index):
        ok, _ = verify_camera(idx)
        if ok:
            available.append(idx)
    return available
