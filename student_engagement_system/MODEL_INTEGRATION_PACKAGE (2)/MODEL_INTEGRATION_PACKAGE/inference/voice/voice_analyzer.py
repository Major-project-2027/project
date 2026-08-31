"""
ml/training/voice_analysis/voice_analyzer.py
==============================================
Core Voice Analysis engine (Module 4).

This is a voice BEHAVIOR analysis module, not a speech-to-text system.
For every fixed-length audio window it produces a `VoiceAnalysisResult`
with exactly the fields required by the multimodal fusion pipeline:

    voice_detected, speech_probability, energy, pitch, volume,
    noise_level, snr, speaking_duration, speech_rate,
    audio_quality_score, timestamp, confidence

Architecture
------------
Three interchangeable, pretrained-first VAD backends are supported,
tried in the order given by `config.VAD_BACKEND_PRIORITY`:

  1. Silero VAD (torch.hub, CPU) - highest accuracy, ~1-2 ms/window.
     Used if `torch` is installed and the jit model can be loaded
     (cached locally after first download).
  2. WebRTC VAD (Google's GMM-based VAD, C++ via the `webrtcvad`
     bindings) - no torch dependency, extremely fast (<1 ms/window),
     the strongest CPU-only real-time default.
  3. Energy + zero-crossing-rate heuristic - zero external
     dependencies beyond numpy/scipy, guarantees the module still
     runs (with reduced accuracy) in a minimal environment.

A window's `speech_probability` combines the chosen VAD backend's
frame-level voting with the optional trained "speech-confidence
calibrator" (see trainer.py) when a fitted calibrator is present on
disk; otherwise the raw VAD vote is used directly as the probability.

Integration note (fusion contract)
-----------------------------------
`disruption_detected` / `disruption_confidence` are the ONLY fields
this module contributes to the rest of the system. They flag
sustained, loud, off-pattern speech (a classroom-disturbance signal
for the Alert Rule Engine), and are computed acoustically only - no
transcription. They are deliberately NOT an engagement/attentiveness
score: this module's output is never combined with
`ENGAGEMENT_FEATURE_WEIGHTS` and is never passed to the LSTM
attention-drop predictor, matching the reference "two independent
units" pattern (video attentiveness vs. audio disruption, never
fused) documented in the project's literature survey (Paper #1,
TeacherEye).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np

import config as voice_config
import utils as voice_utils

logger = voice_utils.get_logger("voice_analyzer")


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------
@dataclass
class VoiceAnalysisResult:
    voice_detected: bool
    speech_probability: float
    energy: float
    pitch: float
    volume: float
    noise_level: float
    snr: float
    speaking_duration: float
    speech_rate: float
    audio_quality_score: float
    timestamp: float
    confidence: float

    # -- Classroom-disturbance signal (NEW) --------------------------------
    # Independent of every field above's use in engagement scoring: this
    # is the one thing the Alert Rule Engine should read from this
    # module. See the module docstring's "Integration note" above.
    disruption_detected: bool = False
    disruption_confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# VAD backends
# ---------------------------------------------------------------------------
class BaseVAD:
    name = "base"

    def frame_is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool:
        raise NotImplementedError

    def window_vote(self, window: np.ndarray, sample_rate: int) -> float:
        """Return the fraction of VAD frames inside `window` classified as speech."""
        frame_samples = voice_config.VAD_FRAME_SAMPLES
        n_frames = len(window) // frame_samples
        if n_frames == 0:
            return 0.0

        votes = 0
        for i in range(n_frames):
            start = i * frame_samples
            frame = window[start:start + frame_samples]
            pcm16 = voice_utils.float_to_pcm16(frame)
            if self.frame_is_speech(pcm16, sample_rate):
                votes += 1
        return votes / n_frames


class WebRTCVAD(BaseVAD):
    name = "webrtc"

    def __init__(self, aggressiveness: int = voice_config.VAD_AGGRESSIVENESS):
        import webrtcvad
        self._vad = webrtcvad.Vad(aggressiveness)

    def frame_is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool:
        expected_bytes = voice_config.VAD_FRAME_SAMPLES * 2  # int16 = 2 bytes/sample
        if len(frame_pcm16) != expected_bytes:
            return False
        try:
            return self._vad.is_speech(frame_pcm16, sample_rate)
        except Exception:
            return False


class SileroVAD(BaseVAD):
    name = "silero"

    def __init__(self):
        import torch
        self._torch = torch
        try:
            self._model, _utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                onnx=False,
                trust_repo=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Could not load Silero VAD via torch.hub: {exc}") from exc
        self._model.eval()

    def window_vote(self, window: np.ndarray, sample_rate: int) -> float:
        with self._torch.no_grad():
            tensor = self._torch.from_numpy(window.astype(np.float32))
            prob = self._model(tensor, sample_rate).item()
        return float(np.clip(prob, 0.0, 1.0))

    def frame_is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool:  # pragma: no cover
        # Silero operates on whole windows (see window_vote override);
        # per-frame voting is not used for this backend.
        raise NotImplementedError


class EnergyVAD(BaseVAD):
    """Dependency-free fallback: a window is "speech-like" if its RMS
    energy exceeds a floor AND its zero-crossing rate is not
    noise/hiss-like (very high ZCR with low energy is typically
    fricative noise or line hum, not voiced speech).
    """
    name = "energy"

    def window_vote(self, window: np.ndarray, sample_rate: int) -> float:
        rms = voice_utils.compute_rms_energy(window)
        zcr = voice_utils.compute_zero_crossing_rate(window)
        if rms < voice_config.ENERGY_VAD_RMS_THRESHOLD:
            return 0.0
        if zcr > voice_config.ENERGY_VAD_ZCR_MAX:
            return 0.3  # ambiguous - some energy, but noise-like spectral shape
        # Smoothly scale confidence with how far above threshold the energy is.
        headroom = rms / voice_config.ENERGY_VAD_RMS_THRESHOLD
        return float(np.clip(0.5 + 0.5 * np.tanh(headroom - 1.0), 0.0, 1.0))

    def frame_is_speech(self, frame_pcm16: bytes, sample_rate: int) -> bool:  # pragma: no cover
        raise NotImplementedError


def build_vad_backend(preferred_order: tuple[str, ...] = voice_config.VAD_BACKEND_PRIORITY) -> BaseVAD:
    """Instantiate the first available VAD backend in `preferred_order`,
    logging why any earlier choice was skipped. Always succeeds because
    `EnergyVAD` has no external dependencies.
    """
    builders = {
        "silero": SileroVAD,
        "webrtc": WebRTCVAD,
        "energy": EnergyVAD,
    }
    for name in preferred_order:
        builder = builders.get(name)
        if builder is None:
            continue
        try:
            backend = builder()
            logger.info("VAD backend selected: %s", name)
            return backend
        except Exception as exc:
            logger.warning("VAD backend '%s' unavailable (%s); trying next.", name, exc)
    logger.warning("Falling back to EnergyVAD (no other backend available).")
    return EnergyVAD()


# ---------------------------------------------------------------------------
# Optional trained speech-confidence calibrator
# ---------------------------------------------------------------------------
class SpeechConfidenceCalibrator:
    """Wraps the classifier trained by trainer.py that refines the raw
    VAD vote + acoustic features into a calibrated speech_probability.
    Falls back to identity (returns the raw VAD vote unchanged) if no
    trained model file exists yet, so the module is fully usable before
    any training has been run.
    """

    def __init__(
        self,
        model_path=voice_config.SPEECH_CONFIDENCE_MODEL_FILE,
        scaler_path=voice_config.SPEECH_CONFIDENCE_SCALER_FILE,
    ):
        self._model = None
        self._scaler = None
        if model_path.exists() and scaler_path.exists():
            try:
                import joblib
                self._model = joblib.load(model_path)
                self._scaler = joblib.load(scaler_path)
                logger.info("Loaded speech-confidence calibrator from %s", model_path)
            except Exception as exc:
                logger.warning("Could not load speech-confidence calibrator (%s); using raw VAD vote.", exc)

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    def calibrate(self, raw_vote: float, feature_vector: np.ndarray) -> float:
        if not self.is_fitted:
            return raw_vote
        try:
            scaled = self._scaler.transform(feature_vector.reshape(1, -1))
            proba = self._model.predict_proba(scaled)[0, 1]
            # Blend calibrated model output with the raw VAD vote so a
            # single mispredicted window can't wildly override the
            # signal the VAD backend already agrees on.
            return float(0.6 * proba + 0.4 * raw_vote)
        except Exception as exc:
            logger.warning("Calibration inference failed (%s); using raw VAD vote.", exc)
            return raw_vote


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------
class VoiceAnalyzer:
    """Stateful per-speaker/session analyzer. Call `analyze_window()`
    once per sliding window (see `predictor.py` for file/mic/stream
    drivers) to get a `VoiceAnalysisResult`. State is kept for:

      - the rolling noise-floor estimate (for SNR), and
      - the current contiguous speaking-run duration (reset to 0 as
        soon as a window is not classified as voice_detected).
    """

    def __init__(
        self,
        sample_rate: int = voice_config.SAMPLE_RATE,
        vad_backend: Optional[BaseVAD] = None,
    ):
        self.sample_rate = sample_rate
        self.vad = vad_backend or build_vad_backend()
        self.calibrator = SpeechConfidenceCalibrator()
        self.noise_floor = voice_utils.NoiseFloorEstimator()
        self._speaking_duration_sec = 0.0

    def reset_session_state(self) -> None:
        """Call when starting a new student/session so speaking-duration
        and noise-floor history don't leak across unrelated sessions.
        """
        self._speaking_duration_sec = 0.0
        self.noise_floor.reset()

    def analyze_window(
        self,
        window: np.ndarray,
        window_start_time_sec: float,
        wall_clock_timestamp: Optional[float] = None,
    ) -> VoiceAnalysisResult:
        """Run the full pipeline on one fixed-length audio window and
        return the fused result. `window_start_time_sec` is the
        position within the current audio stream/file (used for
        speaking-duration bookkeeping); `wall_clock_timestamp` is the
        value reported in the output (defaults to `time.time()` for
        live streams, or `window_start_time_sec` for offline files -
        callers decide which is meaningful for their use case).
        """
        t0 = time.perf_counter()

        features = voice_utils.extract_acoustic_features(window, self.sample_rate)
        raw_vote = self.vad.window_vote(window, self.sample_rate)

        feature_vector = voice_utils.acoustic_features_to_vector(features)
        speech_probability = self.calibrator.calibrate(raw_vote, feature_vector)

        voice_detected = speech_probability >= voice_config.VOICE_DETECTED_CONFIDENCE_THRESHOLD

        noise_floor_rms = self.noise_floor.update(features.rms_energy) \
            if not voice_detected else self.noise_floor.current_estimate()
        snr_db = voice_utils.compute_snr_db(features.rms_energy, noise_floor_rms)
        quality_score = voice_utils.compute_audio_quality_score(snr_db)

        if voice_detected:
            self._speaking_duration_sec += (
                voice_config.HOP_DURATION_SEC if window_start_time_sec > 0 else voice_config.WINDOW_DURATION_SEC
            )
            speech_rate = voice_utils.estimate_speech_rate(window, self.sample_rate)
        else:
            self._speaking_duration_sec = 0.0
            speech_rate = 0.0

        # Confidence-of-the-decision (distance of speech_probability
        # from the decision boundary, rescaled to [0, 1]) - distinct
        # from speech_probability itself, which is P(speech).
        confidence = float(2.0 * abs(speech_probability - 0.5))

        disruption_detected, disruption_confidence = self._classify_disruption(
            voice_detected=voice_detected,
            energy=features.rms_energy,
            speaking_duration_sec=self._speaking_duration_sec,
            speech_rate=speech_rate,
            speech_probability=speech_probability,
        )

        latency_ms = (time.perf_counter() - t0) * 1000.0
        if latency_ms > voice_config.MAX_LATENCY_BUDGET_MS:
            logger.debug(
                "Window latency %.2f ms exceeded budget of %.2f ms",
                latency_ms, voice_config.MAX_LATENCY_BUDGET_MS,
            )

        return VoiceAnalysisResult(
            voice_detected=bool(voice_detected),
            speech_probability=round(speech_probability, 4),
            energy=round(features.rms_energy, 6),
            pitch=round(features.pitch_hz, 2),
            volume=round(features.volume_dbfs, 2),
            noise_level=round(noise_floor_rms, 6),
            snr=round(snr_db, 2),
            speaking_duration=round(self._speaking_duration_sec, 3),
            speech_rate=round(speech_rate, 2),
            audio_quality_score=round(quality_score, 4),
            timestamp=wall_clock_timestamp if wall_clock_timestamp is not None else window_start_time_sec,
            confidence=round(confidence, 4),
            disruption_detected=disruption_detected,
            disruption_confidence=round(disruption_confidence, 4),
        )

    @staticmethod
    def _classify_disruption(
        *,
        voice_detected: bool,
        energy: float,
        speaking_duration_sec: float,
        speech_rate: float,
        speech_probability: float,
    ) -> tuple[bool, float]:
        """Acoustic-only classroom-disturbance classifier.

        Deliberately separate from engagement scoring (see module
        docstring). Flags a window as disruptive only when speech is
        sustained, loud, and rapid at the same time - a brief remark
        or a normal question/answer should NOT trip this; it targets
        prolonged loud talking/disruption during instruction.
        """
        if not voice_detected:
            return False, 0.0

        conditions = (
            energy >= voice_config.DISRUPTION_ENERGY_RMS_THRESHOLD,
            speaking_duration_sec >= voice_config.DISRUPTION_MIN_SPEAKING_DURATION_SEC,
            speech_rate >= voice_config.DISRUPTION_MIN_SPEECH_RATE,
        )
        if not all(conditions):
            return False, 0.0

        # Confidence blends how far energy/rate exceed their thresholds
        # with the calibrated speech_probability itself, so a shaky VAD
        # decision doesn't produce a confident disruption flag.
        energy_margin = min(energy / voice_config.DISRUPTION_ENERGY_RMS_THRESHOLD, 2.0) / 2.0
        rate_margin = min(speech_rate / voice_config.DISRUPTION_MIN_SPEECH_RATE, 2.0) / 2.0
        confidence = float(speech_probability * 0.5 + energy_margin * 0.25 + rate_margin * 0.25)

        if confidence < voice_config.DISRUPTION_MIN_CONFIDENCE:
            return False, confidence

        return True, confidence
