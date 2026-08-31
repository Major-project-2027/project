"""
ml/training/voice_analysis/utils.py
=====================================
Reusable, stateless utility functions for the Voice Analysis module:
logging setup, audio I/O (load/resample/validate), corrupted-file
filtering, sliding-window generation, and acoustic feature extraction
(RMS energy, pitch, ZCR, spectral centroid/bandwidth/rolloff, chroma,
MFCC, SNR, audio-quality score).

No VAD model-loading or fusion logic lives here (see voice_analyzer.py)
- this module is pure signal-processing plumbing, kept free of any
speech-to-text, NLP, or sentiment-analysis code by design.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

import config as voice_config

try:
    import librosa
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "librosa is required by ml/training/voice_analysis. "
        "Install it with: pip install librosa soundfile"
    ) from exc


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def get_logger(name: str) -> logging.Logger:
    """Return a module-local logger writing to both stdout and a
    rotating file under `config.LOG_DIR`. Safe to call multiple times
    (handlers are only attached once per logger name).
    """
    logger = logging.getLogger(f"voice_analysis.{name}")
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, voice_config.LOG_LEVEL.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            voice_config.LOG_DIR / f"{name}.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
        )
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except OSError:
        # Read-only filesystem or similar - stdout logging is enough.
        pass

    logger.propagate = False
    return logger


logger = get_logger("utils")


class ProgressTracker:
    """Lightweight progress/ETA printer used by dataset notebooks and
    trainer.py, avoiding a hard dependency on tqdm inside library code
    (tqdm is still used interactively inside the notebooks themselves).
    """

    def __init__(self, total: int, label: str = "processing"):
        self.total = max(total, 1)
        self.label = label
        self.start_time = time.time()
        self.count = 0

    def update(self, n: int = 1) -> None:
        self.count += n
        elapsed = time.time() - self.start_time
        rate = self.count / elapsed if elapsed > 0 else 0.0
        eta = (self.total - self.count) / rate if rate > 0 else float("inf")
        pct = 100.0 * self.count / self.total
        sys.stdout.write(
            f"\r{self.label}: {self.count}/{self.total} ({pct:5.1f}%) "
            f"| {rate:6.1f} files/s | ETA {eta:6.1f}s"
        )
        sys.stdout.flush()
        if self.count >= self.total:
            sys.stdout.write("\n")


# ---------------------------------------------------------------------------
# Audio I/O
# ---------------------------------------------------------------------------
class CorruptedAudioError(RuntimeError):
    """Raised when an audio file cannot be decoded or contains no usable signal."""


def load_audio(
    path: str | Path,
    sample_rate: int = voice_config.SAMPLE_RATE,
    mono: bool = True,
) -> np.ndarray:
    """Load an audio file, resample to `sample_rate`, and return a
    float32 array normalized to [-1, 1]. Raises `CorruptedAudioError`
    on decode failure, empty signal, or all-zero/NaN content.
    """
    path = Path(path)
    if not path.exists():
        raise CorruptedAudioError(f"Audio file not found: {path}")

    try:
        audio, _ = librosa.load(str(path), sr=sample_rate, mono=mono)
    except Exception as exc:
        raise CorruptedAudioError(f"Failed to decode {path}: {exc}") from exc

    if audio.size == 0:
        raise CorruptedAudioError(f"Empty audio signal: {path}")
    if not np.isfinite(audio).all():
        raise CorruptedAudioError(f"Non-finite samples (NaN/Inf) in: {path}")
    if np.allclose(audio, 0.0):
        raise CorruptedAudioError(f"Silent/all-zero audio signal: {path}")

    return normalize_amplitude(audio)


def normalize_amplitude(audio: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Peak-normalize audio to `target_peak` to avoid clipping while
    keeping a consistent input scale for downstream feature extraction.
    """
    peak = np.max(np.abs(audio))
    if peak < 1e-8:
        return audio
    return (audio / peak) * target_peak


def float_to_pcm16(audio: np.ndarray) -> bytes:
    """Convert float32 [-1, 1] audio to little-endian 16-bit PCM bytes,
    the format required by WebRTC VAD frames.
    """
    clipped = np.clip(audio, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    return pcm16.tobytes()


def is_valid_audio_file(path: str | Path, min_duration_sec: float = 0.2) -> bool:
    """Cheap validity check used by dataset preprocessing to discard
    corrupted files before the (more expensive) full load/resample.
    """
    try:
        audio = load_audio(path)
        duration = len(audio) / voice_config.SAMPLE_RATE
        return duration >= min_duration_sec
    except CorruptedAudioError:
        return False


# ---------------------------------------------------------------------------
# Sliding-window generation
# ---------------------------------------------------------------------------
def sliding_windows(
    audio: np.ndarray,
    window_samples: int = voice_config.WINDOW_SAMPLES,
    hop_samples: int = voice_config.HOP_SAMPLES,
    pad_last: bool = True,
) -> Iterator[tuple[np.ndarray, float]]:
    """Yield (window, window_start_time_sec) tuples over `audio`. The
    final partial window is zero-padded to `window_samples` if
    `pad_last` is True, so every window fed to the analyzer has a
    consistent length (required by fixed-size spectral transforms).
    """
    n = len(audio)
    if n == 0:
        return
    start = 0
    while start < n:
        end = start + window_samples
        chunk = audio[start:end]
        if len(chunk) < window_samples:
            if not pad_last:
                break
            chunk = np.pad(chunk, (0, window_samples - len(chunk)))
        yield chunk, start / voice_config.SAMPLE_RATE
        start += hop_samples


# ---------------------------------------------------------------------------
# Acoustic feature extraction
# ---------------------------------------------------------------------------
@dataclass
class AcousticFeatures:
    """Raw acoustic measurements for a single audio window. This is an
    internal, richer representation than the final API output
    (`voice_analyzer.VoiceAnalysisResult`) - it also feeds the
    speech-confidence calibrator in trainer.py.
    """
    rms_energy: float
    volume_dbfs: float
    pitch_hz: float
    pitch_voiced_fraction: float
    zero_crossing_rate: float
    spectral_centroid: float
    spectral_bandwidth: float
    spectral_rolloff: float
    mfcc_mean: np.ndarray      # shape (N_MFCC,)
    chroma_mean: np.ndarray    # shape (12,)


def compute_rms_energy(window: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(window)) + 1e-12))


def rms_to_dbfs(rms: float) -> float:
    """Convert linear RMS (on a [-1, 1]-normalized signal) to dBFS.
    Full-scale sine RMS (~0.707) maps to ~0 dBFS; silence floors at
    a clamped -100 dBFS to avoid -inf.
    """
    return float(max(20.0 * np.log10(rms + 1e-12), -100.0))


def compute_zero_crossing_rate(window: np.ndarray) -> float:
    return float(np.mean(librosa.feature.zero_crossing_rate(
        window, frame_length=voice_config.N_FFT, hop_length=voice_config.HOP_LENGTH
    )))


def compute_pitch(
    window: np.ndarray,
    sample_rate: int = voice_config.SAMPLE_RATE,
    method: str = voice_config.PITCH_METHOD,
) -> tuple[float, float]:
    """Estimate fundamental frequency (F0). Returns (median_pitch_hz
    over voiced frames, voiced_fraction). Returns (0.0, 0.0) for
    windows with no detected voicing (silence, noise, or pitch
    below/above the configured range).

    Two interchangeable estimators are supported (see
    `config.PITCH_METHOD`):
      - "yin"  (default): deterministic YIN, ~2-5 ms per 1 s window -
        used by the real-time predictor.
      - "pyin": probabilistic YIN with an HMM voicing decoder, more
        accurate but ~30-40x slower - offline/notebook use only.
    """
    frame_length = voice_config.N_FFT * 2
    hop_length = voice_config.HOP_LENGTH

    try:
        if method == "pyin":
            f0, voiced_flag, _voiced_prob = librosa.pyin(
                window, fmin=voice_config.PITCH_FMIN_HZ, fmax=voice_config.PITCH_FMAX_HZ,
                sr=sample_rate, frame_length=frame_length, hop_length=hop_length,
            )
            voiced_flag = np.nan_to_num(voiced_flag.astype(float))
            voiced_fraction = float(np.mean(voiced_flag)) if voiced_flag.size else 0.0
            voiced_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
            if voiced_f0.size == 0:
                return 0.0, voiced_fraction
            return float(np.median(voiced_f0)), voiced_fraction

        # Fast path: plain YIN. YIN always returns a value per frame
        # (no built-in voicing decision), so voicing is derived from
        # per-frame RMS energy - a frame with an F0 estimate inside
        # range AND non-negligible energy is counted as voiced.
        f0 = librosa.yin(
            window, fmin=voice_config.PITCH_FMIN_HZ, fmax=voice_config.PITCH_FMAX_HZ,
            sr=sample_rate, frame_length=frame_length, hop_length=hop_length,
        )
        frame_rms = librosa.feature.rms(y=window, frame_length=frame_length, hop_length=hop_length)[0]
        n = min(len(f0), len(frame_rms))
        f0, frame_rms = f0[:n], frame_rms[:n]

        energy_floor = max(np.max(frame_rms) * 0.1, 1e-5) if n else 1e-5
        in_range = (f0 >= voice_config.PITCH_FMIN_HZ) & (f0 <= voice_config.PITCH_FMAX_HZ)
        voiced_mask = in_range & (frame_rms >= energy_floor)

        voiced_fraction = float(np.mean(voiced_mask)) if n else 0.0
        if not np.any(voiced_mask):
            return 0.0, voiced_fraction
        return float(np.median(f0[voiced_mask])), voiced_fraction
    except Exception:
        return 0.0, 0.0


def compute_spectral_shape(
    window: np.ndarray,
    sample_rate: int = voice_config.SAMPLE_RATE,
) -> tuple[float, float, float]:
    """Return (spectral_centroid, spectral_bandwidth, spectral_rolloff) in Hz."""
    centroid = librosa.feature.spectral_centroid(
        y=window, sr=sample_rate, n_fft=voice_config.N_FFT, hop_length=voice_config.HOP_LENGTH
    )
    bandwidth = librosa.feature.spectral_bandwidth(
        y=window, sr=sample_rate, n_fft=voice_config.N_FFT, hop_length=voice_config.HOP_LENGTH
    )
    rolloff = librosa.feature.spectral_rolloff(
        y=window, sr=sample_rate, n_fft=voice_config.N_FFT, hop_length=voice_config.HOP_LENGTH
    )
    return float(np.mean(centroid)), float(np.mean(bandwidth)), float(np.mean(rolloff))


def compute_mfcc(
    window: np.ndarray,
    sample_rate: int = voice_config.SAMPLE_RATE,
) -> np.ndarray:
    mfcc = librosa.feature.mfcc(
        y=window, sr=sample_rate, n_mfcc=voice_config.N_MFCC,
        n_fft=voice_config.N_FFT, hop_length=voice_config.HOP_LENGTH,
        n_mels=voice_config.N_MELS,
    )
    return np.mean(mfcc, axis=1)


def compute_chroma(
    window: np.ndarray,
    sample_rate: int = voice_config.SAMPLE_RATE,
) -> np.ndarray:
    chroma = librosa.feature.chroma_stft(
        y=window, sr=sample_rate, n_fft=voice_config.N_FFT, hop_length=voice_config.HOP_LENGTH
    )
    return np.mean(chroma, axis=1)


def compute_log_mel_spectrogram(
    window: np.ndarray,
    sample_rate: int = voice_config.SAMPLE_RATE,
) -> np.ndarray:
    """Return a log-mel spectrogram (n_mels, n_frames) - stored as
    metadata during dataset preprocessing for exploratory notebooks;
    not required for real-time inference.
    """
    mel = librosa.feature.melspectrogram(
        y=window, sr=sample_rate, n_fft=voice_config.N_FFT,
        hop_length=voice_config.HOP_LENGTH, n_mels=voice_config.N_MELS,
    )
    return librosa.power_to_db(mel, ref=np.max)


def extract_acoustic_features(
    window: np.ndarray,
    sample_rate: int = voice_config.SAMPLE_RATE,
) -> AcousticFeatures:
    """Compute the full acoustic feature set for one fixed-length audio window."""
    rms = compute_rms_energy(window)
    pitch_hz, voiced_fraction = compute_pitch(window, sample_rate)
    zcr = compute_zero_crossing_rate(window)
    centroid, bandwidth, rolloff = compute_spectral_shape(window, sample_rate)
    mfcc_mean = compute_mfcc(window, sample_rate)
    chroma_mean = compute_chroma(window, sample_rate)

    return AcousticFeatures(
        rms_energy=rms,
        volume_dbfs=rms_to_dbfs(rms),
        pitch_hz=pitch_hz,
        pitch_voiced_fraction=voiced_fraction,
        zero_crossing_rate=zcr,
        spectral_centroid=centroid,
        spectral_bandwidth=bandwidth,
        spectral_rolloff=rolloff,
        mfcc_mean=mfcc_mean,
        chroma_mean=chroma_mean,
    )


def acoustic_features_to_vector(features: AcousticFeatures) -> np.ndarray:
    """Flatten AcousticFeatures into a fixed-order numeric feature
    vector for the speech-confidence calibrator (trainer.py /
    predictor.py must use this exact ordering).
    """
    return np.concatenate([
        np.array([
            features.rms_energy,
            features.volume_dbfs,
            features.pitch_hz,
            features.pitch_voiced_fraction,
            features.zero_crossing_rate,
            features.spectral_centroid,
            features.spectral_bandwidth,
            features.spectral_rolloff,
        ], dtype=np.float64),
        features.mfcc_mean.astype(np.float64),
        features.chroma_mean.astype(np.float64),
    ])


FEATURE_VECTOR_NAMES: list[str] = (
    [
        "rms_energy", "volume_dbfs", "pitch_hz", "pitch_voiced_fraction",
        "zero_crossing_rate", "spectral_centroid", "spectral_bandwidth",
        "spectral_rolloff",
    ]
    + [f"mfcc_{i}" for i in range(voice_config.N_MFCC)]
    + [f"chroma_{i}" for i in range(12)]
)


# ---------------------------------------------------------------------------
# Noise floor / SNR / audio quality
# ---------------------------------------------------------------------------
class NoiseFloorEstimator:
    """Maintains a rolling estimate of the ambient noise floor (RMS)
    from recent low-energy windows, used to compute per-window SNR
    without requiring an explicit silence-calibration step.
    """

    def __init__(
        self,
        history_size: int = voice_config.NOISE_FLOOR_CALIBRATION_WINDOWS,
        percentile: float = voice_config.NOISE_FLOOR_PERCENTILE,
    ):
        self._history: list[float] = []
        self._history_size = history_size
        self._percentile = percentile

    def update(self, rms_energy: float) -> float:
        """Push a new window's RMS energy and return the current noise-floor estimate."""
        self._history.append(rms_energy)
        if len(self._history) > self._history_size:
            self._history.pop(0)
        return self.current_estimate()

    def current_estimate(self) -> float:
        if not self._history:
            return 1e-4
        return float(np.percentile(self._history, self._percentile)) + 1e-8

    def reset(self) -> None:
        self._history.clear()


def compute_snr_db(signal_rms: float, noise_floor_rms: float) -> float:
    """Simple RMS-ratio SNR estimate in dB. Clamped to a sane range
    since real-world estimates of an unknown noise floor can be noisy.
    """
    ratio = signal_rms / max(noise_floor_rms, 1e-8)
    snr_db = 20.0 * np.log10(max(ratio, 1e-8))
    return float(np.clip(snr_db, -20.0, 60.0))


def compute_audio_quality_score(
    snr_db: float,
    good_db: float = voice_config.SNR_GOOD_DB,
    poor_db: float = voice_config.SNR_POOR_DB,
) -> float:
    """Map SNR (dB) to a normalized [0, 1] audio-quality score via
    linear interpolation between `poor_db` -> 0.0 and `good_db` -> 1.0.
    """
    if good_db == poor_db:
        return 1.0 if snr_db >= good_db else 0.0
    score = (snr_db - poor_db) / (good_db - poor_db)
    return float(np.clip(score, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Speaking-rate estimation (acoustic proxy, not word-based)
# ---------------------------------------------------------------------------
def estimate_speech_rate(
    window: np.ndarray,
    sample_rate: int = voice_config.SAMPLE_RATE,
) -> float:
    """Estimate speech rate in syllable-nuclei-per-second using
    energy-envelope peak-picking (Feature described in prosody
    literature as a lightweight ASR-free syllable-rate proxy). This is
    an acoustic approximation, not a word-count from transcription -
    consistent with this module's "no speech-to-text" scope.
    """
    from scipy.signal import find_peaks

    frame_length = int(sample_rate * voice_config.SPEECH_RATE_ENVELOPE_SMOOTHING_MS / 1000)
    frame_length = max(frame_length, 32)
    hop = max(frame_length // 2, 1)

    envelope = librosa.feature.rms(y=window, frame_length=frame_length, hop_length=hop)[0]
    if envelope.size < 3 or np.max(envelope) < 1e-6:
        return 0.0

    envelope = envelope / (np.max(envelope) + 1e-12)
    min_distance_frames = max(
        int(voice_config.SPEECH_RATE_MIN_PEAK_DISTANCE_SEC * sample_rate / hop), 1
    )
    peaks, _ = find_peaks(envelope, height=0.35, distance=min_distance_frames)

    duration_sec = len(window) / sample_rate
    if duration_sec <= 0:
        return 0.0
    return float(len(peaks) / duration_sec)
