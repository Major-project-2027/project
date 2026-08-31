# Evaluation summary
Generated: 2026-08-19T17:32:19.310495+00:00

All results below are computed by loading the EXISTING production
model files and running real inference against real, already-present
labelled/held-out data. No retraining occurred. See GROUND_TRUTH_AUDIT.md
for the components with no real project-specific ground truth.

| Component | Result | Status |
|---|---|---|
| Emotion (FER2013 test split) | 0.2506 | VALID PROJECT-SPECIFIC METRIC |
| Emotion (CK+ independent set) | 0.2233 | VALID PROJECT-SPECIFIC METRIC (6 of 7 classes -- no Neutral ground truth in this dataset) |
| Live Engagement LSTM | MAE=0.0376 | VALID PROJECT-SPECIFIC METRIC |
| Future Engagement LSTM | MAE=0.00034 | STATISTICALLY INSUFFICIENT |

See GROUND_TRUTH_AUDIT.md for: phone detection, multiple-person
detection, looking-away detection, drowsiness, face detection,
gaze detection, blink detection, and face recognition -- all
NOT EVALUATABLE, no real project-specific ground truth exists.