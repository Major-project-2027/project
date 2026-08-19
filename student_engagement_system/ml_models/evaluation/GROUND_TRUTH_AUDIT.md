# Ground-truth audit — what real labelled data actually exists in this project

This file records exactly what was searched, where, and what was found, for
every production AI/CV component that does **not** have a working evaluation
script in this directory. No labels were invented for any of these — where
no real ground truth exists, no evaluation script was written.

## Searched locations

- `datasets/raw/*` (every subdirectory, full recursive listing)
- `datasets/processed/*`
- Every `*.csv`, `*annotation*`, `*ground_truth*`, `*labels*.json` file in the
  entire project (excluding `node_modules`)
- Every training/evaluation notebook (`Phase*.ipynb.ipynb`, `training/`)

## Findings, per component

| Component | Directory that exists | Actual contents found | Verdict |
|---|---|---|---|
| Phone detection | `datasets/raw/coco_subset/` | **Empty** — only `.gitkeep` | NOT EVALUATABLE — no labelled frames |
| Multiple-person detection | `datasets/raw/coco_subset/` | **Empty** — only `.gitkeep` | NOT EVALUATABLE — no labelled frames |
| Looking-away detection | `datasets/raw/classroom_distraction/` | **Empty** — only `.gitkeep` | NOT EVALUATABLE — no labelled frames |
| Head pose | `datasets/raw/head_pose_300w_lp/` | **Empty** — only `.gitkeep` (directory scaffolded for the real public "300W-LP" dataset, but the data itself was never downloaded into the project) | NOT EVALUATABLE — no labelled frames |
| Gaze detection | `datasets/raw/mpiigaze/` | **Empty** — only `.gitkeep` (directory scaffolded for the real public "MPIIGaze" dataset, never populated) | NOT EVALUATABLE — no labelled frames |
| Blink detection | *(no directory exists at all)* | No blink/eye-state dataset of any kind found anywhere in the project | NOT EVALUATABLE — no labelled frames |
| Drowsiness/attention | *(no directory, and no such detector exists)* | Confirmed in the production code audit: there is no persisted "drowsy" detector at all — "drowsy" is only a client-side UI label (`cognitiveState`) derived live from a low *current* engagement score, never written to any table, never a distinct model or rule with its own output | NOT EVALUATABLE — no such detector exists to evaluate, and no ground truth exists either |
| Face detection (bounding box) | `datasets/raw/enrolled_faces/Disha/` | 201 real face photos, but **all one identity, no negatives, no bounding-box annotations** — this is a face-*recognition* enrollment set, not a face-*detection* dataset (no images without a face, no labelled boxes) | NOT EVALUATABLE — wrong dataset shape for a detection metric |
| Face recognition (custom CNN, `face_recognition_model.keras`) | `datasets/raw/enrolled_faces/` | Single identity only (one folder, "Disha") | NOT EVALUATABLE — a discrimination metric (precision/recall between people) requires 2+ labelled identities, which do not exist in this project |

## What DOES have real, usable ground truth (evaluated — see the scripts in this directory)

| Component | Real dataset found | Used by |
|---|---|---|
| Emotion recognition | `datasets/raw/fer2013/fer2013.csv` (35,887 real images, 7 classes, unchanged since training) | `evaluate_emotion_fer2013.py` |
| Emotion recognition (2nd, independent) | `datasets/raw/ckplus/` (981 real images, 7 folders; 6 usable classes after excluding "contempt", which has no matching model class) | `evaluate_emotion_ckplus.py` |
| Live engagement LSTM | Real `engagement_records` in `student_engagement.db`, held out via `train_lstm.py`'s own group-level split | `evaluate_engagement_lstm.py` |
| Future engagement LSTM | Real `engagement_records` + `alerts` in `student_engagement.db`, held out via `train_future_engagement_lstm.py`'s own student-level split | `evaluate_future_engagement_lstm.py` |

Note: `datasets/processed/synthetic_engagement/` also exists but is **empty**
(only `.gitkeep`) and, per its name, would not have been usable as genuine
ground truth even if populated — confirmed unused, not touched.
