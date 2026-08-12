"""
Phase 1 foundation tests.

Run with:  pytest tests/test_phase1_foundation.py -v
"""
import os
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --- Folder creation -------------------------------------------------------

REQUIRED_DIRS = [
    "backend", "backend/app", "backend/app/routers", "backend/app/services",
    "backend/app/core", "frontend", "models", "datasets", "datasets/raw",
    "datasets/processed", "configs", "database", "database/schemas",
    "deployment", "tests", "docs", "logs", "weights", "scripts", "utils",
    "outputs", "notebooks",
]


@pytest.mark.parametrize("relative_dir", REQUIRED_DIRS)
def test_required_directory_exists(relative_dir):
    assert (PROJECT_ROOT / relative_dir).is_dir(), f"Missing directory: {relative_dir}"


# --- Imports ----------------------------------------------------------------

def test_utils_logger_importable():
    from utils.logger import get_logger
    logger = get_logger("test")
    assert logger is not None


def test_utils_image_utils_importable():
    from utils.image_utils import load_image, save_image, resize_image, normalize_image
    assert all(callable(fn) for fn in (load_image, save_image, resize_image, normalize_image))


def test_utils_common_importable():
    from utils.common import validate_directory, load_yaml_config, clamp, band_for_score
    assert all(callable(fn) for fn in (validate_directory, load_yaml_config, clamp, band_for_score))


def test_database_schemas_importable():
    from database.schemas.models import COLLECTION_MODEL_MAP
    expected_collections = {
        "students", "sessions", "attendance", "authentication",
        "engagement", "predictions", "alerts", "system_logs",
    }
    assert set(COLLECTION_MODEL_MAP.keys()) == expected_collections


def test_backend_app_importable():
    from backend.app.main import app
    assert app.title == "Student Engagement Monitoring System"


# --- Configuration ------------------------------------------------------

EXPECTED_CONFIG_FILES = [
    "paths.yaml", "camera.yaml", "database.yaml", "models.yaml",
    "alerts.yaml", "training.yaml", "logging.yaml", "thresholds.yaml",
]


@pytest.mark.parametrize("config_file", EXPECTED_CONFIG_FILES)
def test_config_file_exists_and_parses(config_file):
    config_path = PROJECT_ROOT / "configs" / config_file
    assert config_path.exists(), f"Missing config file: {config_file}"
    with open(config_path) as f:
        content = yaml.safe_load(f)
    assert isinstance(content, dict) and len(content) > 0


def test_thresholds_bands_are_contiguous():
    with open(PROJECT_ROOT / "configs" / "thresholds.yaml") as f:
        thresholds = yaml.safe_load(f)
    bands = thresholds["engagement_score"]
    assert bands["low"][1] + 1 == bands["medium"][0]
    assert bands["medium"][1] + 1 == bands["high"][0]
    assert bands["high"][1] == 100


def test_engagement_weights_sum_to_one():
    with open(PROJECT_ROOT / "configs" / "thresholds.yaml") as f:
        thresholds = yaml.safe_load(f)
    weights = thresholds["engagement_weights"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9


# --- Logging ------------------------------------------------------------

def test_logging_creates_all_four_log_files():
    from utils.logger import get_logger
    for stream in ("application", "training", "predictions"):
        logger = get_logger("test_logging", stream=stream)
        logger.info(f"pytest log check -- stream={stream}")

    log_dir = PROJECT_ROOT / "logs"
    for expected_file in ("application.log", "errors.log", "training.log", "predictions.log"):
        assert (log_dir / expected_file).exists(), f"Missing log file: {expected_file}"


# --- Environment variables -----------------------------------------------

def test_env_file_exists():
    assert (PROJECT_ROOT / ".env").exists()
    assert (PROJECT_ROOT / ".env.example").exists()


def test_dotenv_variables_load():
    from dotenv import dotenv_values
    values = dotenv_values(PROJECT_ROOT / ".env")
    for required_key in ("APP_ENV", "MONGO_URI", "MONGO_DB_NAME", "CAMERA_INDEX"):
        assert required_key in values, f"Missing env var: {required_key}"


def test_requirements_file_has_core_packages():
    requirements = (PROJECT_ROOT / "requirements.txt").read_text()
    for package in ("fastapi", "pymongo", "opencv-python", "tensorflow", "ultralytics", "pytest"):
        assert package in requirements, f"requirements.txt missing package: {package}"
