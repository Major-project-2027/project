"""
ml/training/voice_analysis/config.py
=====================================
Centralized configuration for the Voice Analysis module (Module 4).

Every other file in this module (utils.py, voice_analyzer.py,
trainer.py, predictor.py, and all notebooks) imports its settings from
here. Nothing in this module reads environment variables or hardcodes
a path directly - change behavior by editing this file only.

This module is fully independent of Modules 1-3 (Emotion Detection,
Face Authentication, Gaze & Head-Pose Estimation). It does not import
anything from ml/training/emotion_model, ml/training/face_authentication,
or ml/training/gaze_headpose.

Integration contract (IMPORTANT - read before wiring this into the
backend)
-------------------------------------------------------------------
Voice is NOT a weighted input to the Engagement Score Engine and is
NOT consumed by the LSTM attention-drop predictor. Per the project's
architecture document, the engagement score is a fusion of exactly
four video-derived signals (eye_focus, emotion, head_pose,
object/multi-person) - audio is deliberately excluded from that
formula, matching the reference design pattern (TeacherEye, Paper #1
in the literature survey) where a Video Analysis Unit produces the
attentiveness/suspicious-behavior signal and a separate Audio Analysis
Unit produces its own independent disruption signal - the two are
never mixed.

This module's only contract with the rest of the system is therefore
the `disruption_detected` / `disruption_confidence` fields on
`voice_analyzer.VoiceAnalysisResult`, which feed the Alert Rule Engine
directly (a new `classroom_disturbance` alert type) - not the Feature
Aggregator, not the Engagement Score Engine, not the LSTM.

This is NOT a speech-to-text / NLP module. Every setting below concerns
acoustic (paralinguistic) feature extraction only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Path configuration
# ---------------------------------------------------------------------------
MODULE_ROOT = Path(__file__).resolve().parent

DATA_ROOT = MODULE_ROOT / "data"
RAW_DATA_DIR = DATA_ROOT / "raw"
PROCESSED_DATA_DIR = DATA_ROOT / "processed"

CHECKPOINTS_DIR = MODULE_ROOT / "checkpoints"
EVALUATION_ARTIFACTS_DIR = MODULE_ROOT / "evaluation_artifacts"
LOG_DIR = MODULE_ROOT / "logs"

for _dir in (RAW_DATA_DIR, PROCESSED_DATA_DIR, CHECKPOINTS_DIR,
             EVALUATION_ARTIFACTS_DIR, LOG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

MANIFEST_FILE = PROCESSED_DATA_DIR / "manifest.csv"
SPEECH_CONFIDENCE_MODEL_FILE = CHECKPOINTS_DIR / "speech_confidence_calibrator.joblib"
SPEECH_CONFIDENCE_SCALER_FILE = CHECKPOINTS_DIR / "feature_scaler.joblib"
SILERO_VAD_JIT_FILE = CHECKPOINTS_DIR / "silero_vad.jit"

LOG_LEVEL = "INFO"


# ---------------------------------------------------------------------------
# Audio / signal configuration
# ---------------------------------------------------------------------------
SAMPLE_RATE = 16_000          # Hz. WebRTC VAD and Silero VAD both require 8k/16k/32k/48k.
CHANNELS = 1                  # mono only
BIT_DEPTH = 16                # int16 PCM for streaming/VAD frames

# Sliding-window inference parameters. A "window" is the unit an
# engagement fusion step consumes; a "VAD frame" is the smaller unit
# WebRTC VAD itself evaluates.
WINDOW_DURATION_SEC = 1.0     # engagement-analysis window length
HOP_DURATION_SEC = 0.5        # stride between successive windows (50% overlap)

WINDOW_SAMPLES = int(SAMPLE_RATE * WINDOW_DURATION_SEC)
HOP_SAMPLES = int(SAMPLE_RATE * HOP_DURATION_SEC)

# WebRTC VAD only accepts 10/20/30 ms frames.
VAD_FRAME_MS: Literal[10, 20, 30] = 30
VAD_FRAME_SAMPLES = int(SAMPLE_RATE * VAD_FRAME_MS / 1000)

# WebRTC VAD aggressiveness: 0 (least aggressive / most permissive) to
# 3 (most aggressive at filtering out non-speech). 2 is a balanced
# default for classroom microphone audio (some room noise expected).
VAD_AGGRESSIVENESS = 2

# Fraction of VAD-positive frames inside a window required to mark the
# whole window as "voice_detected".
VAD_WINDOW_VOTE_THRESHOLD = 0.3

# VAD backend priority. "silero" is tried first if a torch install and
# cached jit model are available; the pipeline transparently falls back
# to "webrtc", and finally to a dependency-free "energy" VAD so the
# module always runs even on a minimal CPU box with no extra installs.
VAD_BACKEND_PRIORITY: tuple[str, ...] = ("silero", "webrtc", "energy")

# Energy-based VAD fallback threshold (RMS, linear scale, on
# [-1, 1]-normalized float audio). Only used if webrtc/silero are
# unavailable.
ENERGY_VAD_RMS_THRESHOLD = 0.01
ENERGY_VAD_ZCR_MAX = 0.35  # very high ZCR + low energy usually = noise/hiss, not speech

# ---------------------------------------------------------------------------
# Pitch (F0) estimation
# ---------------------------------------------------------------------------
# "yin" (fast, deterministic, ~2-5 ms/window) is the real-time default.
# "pyin" (probabilistic YIN with an HMM voicing decoder) is ~30-40x
# slower on a 1 s window and is offered only for offline/notebook
# exploration where accuracy matters more than the <30 ms/window
# latency budget - do not select it for the live predictor.
PITCH_METHOD: Literal["pyin", "yin"] = "yin"
PITCH_FMIN_HZ = 65.0    # low male voice floor
PITCH_FMAX_HZ = 400.0   # high voice ceiling (covers most adult speakers)

# ---------------------------------------------------------------------------
# Spectral feature configuration (librosa)
# ---------------------------------------------------------------------------
N_FFT = 512
HOP_LENGTH = 160          # 10 ms at 16 kHz
N_MELS = 40
N_MFCC = 13

# ---------------------------------------------------------------------------
# Audio quality / SNR estimation
# ---------------------------------------------------------------------------
# Noise floor is estimated from the lowest-energy percentile of frames
# within a rolling calibration buffer (approximates a "silence" model
# without requiring an explicit calibration step from the user).
NOISE_FLOOR_PERCENTILE = 10
NOISE_FLOOR_CALIBRATION_WINDOWS = 20   # ~10s of history at default window/hop

SNR_GOOD_DB = 20.0    # SNR at/above this -> audio_quality_score saturates near 1.0
SNR_POOR_DB = 0.0     # SNR at/below this -> audio_quality_score floors near 0.0

# ---------------------------------------------------------------------------
# Speaking-rate estimation
# ---------------------------------------------------------------------------
# Speech rate is estimated acoustically (energy-envelope peak-picking,
# a standard syllable-nuclei-rate proxy used in paralinguistic/prosody
# literature) - NOT via ASR/word counting, per the module's scope.
SPEECH_RATE_MIN_PEAK_DISTANCE_SEC = 0.1   # ~10 syllables/sec ceiling
SPEECH_RATE_ENVELOPE_SMOOTHING_MS = 20

# ---------------------------------------------------------------------------
# Output / confidence thresholds
# ---------------------------------------------------------------------------
VOICE_DETECTED_CONFIDENCE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Classroom-disturbance detection (NEW)
# ---------------------------------------------------------------------------
# This is an acoustic disruption classifier, not an engagement signal.
# It flags a window as disruptive when a student is talking loudly /
# at length in a way inconsistent with normal, brief, quiet-listening
# classroom participation. It feeds the Alert Rule Engine's
# `classroom_disturbance` alert type directly - it is never combined
# with `ENGAGEMENT_FEATURE_WEIGHTS` and never passed to the LSTM.
#
# All three conditions below must hold for a window to be flagged;
# tune per-deployment via the admin threshold-config API once that
# exists (see configs/thresholds.example.yaml at the repo root).
DISRUPTION_ENERGY_RMS_THRESHOLD = 0.05      # sustained loudness, above normal speech
DISRUPTION_MIN_SPEAKING_DURATION_SEC = 4.0  # must be a sustained run, not a short remark
DISRUPTION_MIN_SPEECH_RATE = 3.5            # syllables/sec; excited/agitated speech proxy
DISRUPTION_MIN_CONFIDENCE = 0.6             # calibrated confidence floor before flagging

# ---------------------------------------------------------------------------
# Real-time / streaming
# ---------------------------------------------------------------------------
MIC_DEVICE_INDEX: int | None = None   # None = system default input device
STREAM_BLOCK_SAMPLES = VAD_FRAME_SAMPLES  # smallest unit read per audio callback
MAX_LATENCY_BUDGET_MS = 30.0           # performance target: <30 ms per window


# ---------------------------------------------------------------------------
# Dataset registry (for trainer.py / dataset_download.ipynb)
# ---------------------------------------------------------------------------
# The pretrained VAD backends (Silero/WebRTC) need no training data at
# all. The only thing trained from scratch in this module is a small
# "speech-confidence calibrator" - a lightweight classifier that
# refines the raw VAD vote into a smoother, better-calibrated
# speech_probability using the acoustic features already computed
# (energy, ZCR, spectral shape, SNR). It is trained as speech-vs-noise
# binary classification.
@dataclass(frozen=True)
class DatasetSpec:
    display_name: str
    download_url: str
    archive_name: str
    archive_format: Literal["tar_gz", "zip"]
    extracted_dir_name: str
    label: Literal["speech", "non_speech"]
    license_note: str


DATASET_REGISTRY: dict[str, DatasetSpec] = {
    "speech_commands": DatasetSpec(
        display_name="Google Speech Commands v0.02",
        download_url=(
            "https://storage.googleapis.com/download.tensorflow.org/"
            "data/speech_commands_v0.02.tar.gz"
        ),
        archive_name="speech_commands_v0.02.tar.gz",
        archive_format="tar_gz",
        extracted_dir_name="speech_commands_v0.02",
        label="speech",
        license_note="CC BY 4.0 - free for academic/research use.",
    ),
    "esc50": DatasetSpec(
        display_name="ESC-50 (Environmental Sound Classification)",
        download_url=(
            "https://github.com/karolpiczak/ESC-50/archive/refs/heads/master.zip"
        ),
        archive_name="ESC-50-master.zip",
        archive_format="zip",
        extracted_dir_name="ESC-50",
        label="non_speech",
        license_note=(
            "CC BY-NC 3.0 - free for academic/non-commercial research use "
            "only (see the LICENSE file inside the archive)."
        ),
    ),
}

# Train/validation/test split ratios used by trainer.py and the
# preprocessing notebook when building manifest.csv.
TRAIN_SPLIT = 0.70
VAL_SPLIT = 0.15
TEST_SPLIT = 0.15
SPLIT_RANDOM_SEED = 42


# ---------------------------------------------------------------------------
# Training hyperparameters for the speech-confidence calibrator
# ---------------------------------------------------------------------------
@dataclass
class TrainerConfig:
    model_type: Literal["logistic_regression", "gradient_boosting"] = "gradient_boosting"
    n_estimators: int = 200
    max_depth: int = 4
    learning_rate: float = 0.05
    random_state: int = SPLIT_RANDOM_SEED
    class_weight: str | None = "balanced"  # only used by logistic_regression


DEFAULT_TRAINER_CONFIG = TrainerConfig()
