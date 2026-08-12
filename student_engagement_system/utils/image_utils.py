"""
Reusable image and video utility functions shared across every phase of the
Student Engagement Monitoring System.
"""
from pathlib import Path
from typing import List, Optional, Tuple, Union

import cv2
import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)

PathLike = Union[str, Path]


def load_image(path: PathLike, color_mode: str = "bgr") -> np.ndarray:
    """Load an image from disk.

    Args:
        path: Path to the image file.
        color_mode: "bgr" (OpenCV default) or "rgb".

    Returns:
        The loaded image as a NumPy array.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file exists but could not be decoded as an image.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")

    if color_mode.lower() == "rgb":
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image


def save_image(image: np.ndarray, path: PathLike, color_mode: str = "bgr") -> Path:
    """Save an image to disk, creating parent directories if needed.

    Args:
        image: Image array to save.
        path: Destination path.
        color_mode: Color mode of the input ``image`` array ("bgr" or "rgb").

    Returns:
        The resolved path the image was written to.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if color_mode.lower() == "rgb":
        image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    success = cv2.imwrite(str(path), image)
    if not success:
        raise IOError(f"Failed to write image to: {path}")
    logger.debug(f"Saved image to {path}")
    return path.resolve()


def resize_image(image: np.ndarray, target_size: Tuple[int, int],
                  keep_aspect_ratio: bool = False) -> np.ndarray:
    """Resize an image to ``target_size`` (width, height).

    Args:
        image: Source image array.
        target_size: Desired (width, height).
        keep_aspect_ratio: If True, pad with black borders (letterbox) instead
            of stretching.

    Returns:
        The resized image.
    """
    target_w, target_h = target_size
    if not keep_aspect_ratio:
        return cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_AREA)

    h, w = image.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    canvas = np.zeros((target_h, target_w, image.shape[2]), dtype=image.dtype)
    y_off = (target_h - new_h) // 2
    x_off = (target_w - new_w) // 2
    canvas[y_off:y_off + new_h, x_off:x_off + new_w] = resized
    return canvas


def normalize_image(image: np.ndarray, method: str = "0_1") -> np.ndarray:
    """Normalize pixel values for model input.

    Args:
        image: Source image, dtype uint8 in range [0, 255].
        method: "0_1" scales to [0, 1]; "-1_1" scales to [-1, 1];
            "standardize" applies zero-mean/unit-variance per channel.

    Returns:
        A float32 array normalized per ``method``.
    """
    img = image.astype(np.float32)
    if method == "0_1":
        return img / 255.0
    if method == "-1_1":
        return (img / 127.5) - 1.0
    if method == "standardize":
        mean = img.mean(axis=(0, 1), keepdims=True)
        std = img.std(axis=(0, 1), keepdims=True) + 1e-7
        return (img - mean) / std
    raise ValueError(f"Unknown normalization method: {method}")


def extract_frames(video_path: PathLike, output_dir: PathLike,
                    every_n_frames: int = 1, max_frames: Optional[int] = None) -> List[Path]:
    """Extract frames from a video file and save them as JPEGs.

    Args:
        video_path: Path to the input video.
        output_dir: Directory frames are written to.
        every_n_frames: Save every Nth frame (1 = every frame).
        max_frames: Optional cap on the number of frames saved.

    Returns:
        List of paths to the saved frame images, in order.

    Raises:
        FileNotFoundError: If the video cannot be opened.
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    saved_paths: List[Path] = []
    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % every_n_frames == 0:
                out_path = output_dir / f"frame_{frame_idx:06d}.jpg"
                save_image(frame, out_path)
                saved_paths.append(out_path)
                if max_frames is not None and len(saved_paths) >= max_frames:
                    break
            frame_idx += 1
    finally:
        cap.release()

    logger.info(f"Extracted {len(saved_paths)} frames from {video_path.name}")
    return saved_paths


def open_video_capture(source: Union[int, PathLike]) -> cv2.VideoCapture:
    """Open a video capture device or file.

    Args:
        source: Camera index (int) for a live webcam, or a path to a video file.

    Returns:
        An opened ``cv2.VideoCapture`` instance.

    Raises:
        IOError: If the capture device/file could not be opened.
    """
    cap = cv2.VideoCapture(source if isinstance(source, int) else str(source))
    if not cap.isOpened():
        raise IOError(f"Could not open video source: {source}")
    return cap


def draw_label(image: np.ndarray, text: str, position: Tuple[int, int],
               color: Tuple[int, int, int] = (0, 255, 0), font_scale: float = 0.6) -> np.ndarray:
    """Draw a text label with a filled background box (for live overlays).

    Args:
        image: Image to draw on (modified in place and returned).
        text: Label text.
        position: (x, y) of the top-left corner of the text.
        color: BGR color of the background box.
        font_scale: OpenCV font scale.

    Returns:
        The same image array, with the label drawn on it.
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, 1)
    x, y = position
    cv2.rectangle(image, (x, y - text_h - baseline), (x + text_w, y + baseline), color, -1)
    cv2.putText(image, text, (x, y), font, font_scale, (0, 0, 0), 1, cv2.LINE_AA)
    return image
