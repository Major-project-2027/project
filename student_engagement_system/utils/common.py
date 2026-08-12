"""
General-purpose utility functions (non-image-specific) shared across the
Student Engagement Monitoring System.
"""
from pathlib import Path
from typing import Any, Dict, Union

import yaml

from utils.logger import get_logger

logger = get_logger(__name__)

PathLike = Union[str, Path]


def validate_directory(path: PathLike, create_if_missing: bool = False) -> Path:
    """Validate that a directory exists (optionally creating it).

    Args:
        path: Directory path to validate.
        create_if_missing: If True, create the directory (and parents) when absent.

    Returns:
        The resolved directory path.

    Raises:
        NotADirectoryError: If the path exists but is not a directory.
        FileNotFoundError: If the directory is missing and ``create_if_missing`` is False.
    """
    path = Path(path)
    if path.exists() and not path.is_dir():
        raise NotADirectoryError(f"Path exists but is not a directory: {path}")
    if not path.exists():
        if create_if_missing:
            path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created missing directory: {path}")
        else:
            raise FileNotFoundError(f"Directory does not exist: {path}")
    return path.resolve()


def load_yaml_config(config_path: PathLike) -> Dict[str, Any]:
    """Load an arbitrary YAML file into a dictionary.

    Args:
        config_path: Path to a .yaml/.yml file.

    Returns:
        Parsed contents as a dictionary.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def clamp(value: float, lower: float, upper: float) -> float:
    """Clamp ``value`` to the inclusive range [lower, upper]."""
    return max(lower, min(value, upper))


def band_for_score(score: float, bands: Dict[str, list]) -> str:
    """Return the named band a score falls into.

    Args:
        score: Numeric score, e.g. an engagement score in [0, 100].
        bands: Mapping of band name -> [lower, upper] inclusive bounds, as
            loaded from configs/thresholds.yaml under "engagement_score".

    Returns:
        The name of the matching band, or "unknown" if no band matches.
    """
    for band_name, (lower, upper) in bands.items():
        if lower <= score <= upper:
            return band_name
    return "unknown"
