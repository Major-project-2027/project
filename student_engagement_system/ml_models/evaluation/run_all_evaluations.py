"""Runs every real evaluation script in this directory against the
existing production models and writes one consolidated summary.

READ-ONLY / EVALUATION-ONLY: this file only imports and calls the
individual evaluate_*.py scripts' main() functions -- it does not
itself touch any production code, model weights, or database records.
See GROUND_TRUTH_AUDIT.md for the components with no evaluation script
(no real project-specific ground truth exists for them).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

REPORTS_DIR = _HERE / "reports"
SUMMARY_PATH = REPORTS_DIR / "SUMMARY.md"


def _load(name):
    path = REPORTS_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text())


def main():
    print("Running all real, project-specific model evaluations...\n")

    import evaluate_emotion_fer2013
    evaluate_emotion_fer2013.main()
    print("\n")

    import evaluate_emotion_ckplus
    evaluate_emotion_ckplus.main()
    print("\n")

    import evaluate_engagement_lstm
    evaluate_engagement_lstm.main()
    print("\n")

    import evaluate_future_engagement_lstm
    evaluate_future_engagement_lstm.main()
    print("\n")

    fer2013 = _load("emotion_fer2013_report.json")
    ckplus = _load("emotion_ckplus_report.json")
    live_lstm = _load("live_engagement_lstm_report.json")
    future_lstm = _load("future_engagement_lstm_report.json")

    lines = [
        "# Evaluation summary",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "All results below are computed by loading the EXISTING production",
        "model files and running real inference against real, already-present",
        "labelled/held-out data. No retraining occurred. See GROUND_TRUTH_AUDIT.md",
        "for the components with no real project-specific ground truth.",
        "",
        "| Component | Result | Status |",
        "|---|---|---|",
    ]

    def row(name, data, metric_key):
        if data is None:
            lines.append(f"| {name} | NOT RUN | ⚪ |")
            return
        status = data.get("status", "UNKNOWN")
        if data.get("model_runtime_status") == "FAILED_TO_LOAD":
            lines.append(f"| {name} | MODEL FAILED TO LOAD | ⚪ |")
            return
        val = data.get(metric_key)
        lines.append(f"| {name} | {val} | {status} |")

    row("Emotion (FER2013 test split)", fer2013, "accuracy")
    row("Emotion (CK+ independent set)", ckplus, "accuracy")
    if live_lstm and "validation" in live_lstm:
        lines.append(f"| Live Engagement LSTM | MAE={live_lstm['validation']['mae']} | {live_lstm['status']} |")
    else:
        row("Live Engagement LSTM", live_lstm, "status")
    if future_lstm and "validation" in future_lstm:
        lines.append(f"| Future Engagement LSTM | MAE={future_lstm['validation']['mae']} | {future_lstm['status']} |")
    else:
        row("Future Engagement LSTM", future_lstm, "status")

    lines.append("")
    lines.append("See GROUND_TRUTH_AUDIT.md for: phone detection, multiple-person")
    lines.append("detection, looking-away detection, drowsiness, face detection,")
    lines.append("gaze detection, blink detection, and face recognition -- all")
    lines.append("NOT EVALUATABLE, no real project-specific ground truth exists.")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote consolidated summary to {SUMMARY_PATH}")


if __name__ == "__main__":
    sys.exit(main())
