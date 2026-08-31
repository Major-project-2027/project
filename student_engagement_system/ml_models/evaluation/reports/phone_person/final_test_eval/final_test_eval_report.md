# Final Test-Set Evaluation — Phone/Person YOLOv8n Fine-Tune

**Evaluation type:** Final, held-out TEST set (never used in training, validation, or checkpoint selection at any point).
**Checkpoint evaluated:** `ml_models/research/phone_person/runs/detect/finetune_run/ft1_continue_6to20/weights/best.pt` (best checkpoint from the completed 20-epoch run: 5 original + 15 continuation epochs).
**Settings:** imgsz=640, conf=0.25, iou=0.7, device=cpu, batch=8, COCO-80 class indices (person=0, cell phone=67).
**Test set:** 858 images, 858 label files, from `ml_models/research/phone_person/dataset/test/` — a separate split directory from `train/` and `val/`, referenced explicitly by `data.yaml`'s `test:` key. This split was never referenced in the training script or `args.yaml`/`train_args` of any training run (baseline copy, first 5-epoch run, or 15-epoch continuation) — only `split=val` was ever used during training and checkpoint selection.

## Overall Test Metrics

| Metric | Value |
|---|---|
| Precision | 0.6831 |
| Recall | 0.5331 |
| F1-score | 0.5989 |
| mAP@0.5 | 0.5045 |
| mAP@0.5:0.95 | 0.2893 |
| Test images evaluated | 858 |
| Total GT instances | 3,961 |

## Per-Class Test Metrics

### Person (class 0)
| Metric | Value |
|---|---|
| Precision | 0.7094 |
| Recall | 0.6015 |
| F1-score | 0.6510 |
| mAP@0.5 | 0.5783 |
| mAP@0.5:0.95 | 0.3885 |
| GT instances | 2,035 |
| Images containing this class | 456 |

### Cell Phone (class 67)
| Metric | Value |
|---|---|
| Precision | 0.6568 |
| Recall | 0.4647 |
| F1-score | 0.5443 |
| mAP@0.5 | 0.4307 |
| mAP@0.5:0.95 | 0.1900 |
| GT instances | 1,926 |
| Images containing this class | 294 |

## Test vs. Validation — Important Distinction

These TEST results are **lower** than the validation-set results reported after the 20-epoch run finished (val overall: P=0.739, R=0.538, mAP@0.5=0.612, mAP@0.5:0.95=0.334). This is expected and is a **legitimate, honest signal**, not an error: the validation split was used for checkpoint selection (best.pt was chosen based on validation mAP@0.5:0.95), so validation performance carries some optimistic selection bias. The test set was never touched during training or checkpoint selection, so these numbers are the trustworthy final performance figures for the IEEE paper — do not substitute the validation numbers for these.

## Baseline YOLOv8n vs. Fine-Tuned YOLOv8n (same 858-image test set)

| Model | Class | Precision | Recall | F1 | mAP@0.5 | mAP@0.5:0.95 |
|---|---|---|---|---|---|---|
| Baseline YOLOv8n | Person | 0.3780 | 0.4530 | 0.4120 | 0.3320 | 0.2560 |
| Baseline YOLOv8n | Cell phone | 0.0590 | 0.0005 | 0.0010 | 0.0012 | 0.0002 |
| Baseline YOLOv8n | Overall (macro avg) | 0.2185 | 0.2268 | 0.2065 | 0.1666 | 0.1281 |
| Fine-tuned YOLOv8n (20 ep) | Person | 0.7094 | 0.6015 | 0.6510 | 0.5783 | 0.3885 |
| Fine-tuned YOLOv8n (20 ep) | Cell phone | 0.6568 | 0.4647 | 0.5443 | 0.4307 | 0.1900 |
| Fine-tuned YOLOv8n (20 ep) | Overall | 0.6831 | 0.5331 | 0.5989 | 0.5045 | 0.2893 |
| **Improvement** | Person | +0.3314 | +0.1485 | +0.2390 | +0.2463 | +0.1325 |
| **Improvement** | Cell phone | +0.5978 | +0.4642 | +0.5433 | +0.4295 | +0.1898 |
| **Improvement** | Overall | +0.4646 | +0.3063 | +0.3924 | +0.3379 | +0.1612 |

Baseline numbers are the previously established figures from the same untouched 858-image test set (from the earlier full audit), reused here as-is, not re-measured in this evaluation.

## Generated Files (this directory: `ml_models/evaluation/reports/phone_person/final_test_eval/`)

- `confusion_matrix.png` — raw confusion matrix (test set)
- `confusion_matrix_normalized.png` — normalized confusion matrix (test set)
- `BoxPR_curve.png` — Precision–Recall curve
- `BoxP_curve.png` — Precision vs. confidence curve
- `BoxR_curve.png` — Recall vs. confidence curve
- `BoxF1_curve.png` — F1 vs. confidence curve
- `val_batch{0,1,2}_labels.jpg` / `val_batch{0,1,2}_pred.jpg` — representative test-set ground-truth vs. prediction visualizations (Ultralytics names these "val_batch" generically regardless of which split was evaluated — these are test-set images)
- `final_test_metrics.json` — full precision-float metrics, machine-readable
- `final_test_metrics.csv` — overall + per-class metrics, machine-readable
- `baseline_vs_finetuned_test_comparison.csv` — the comparison table above, machine-readable
- `final_test_eval_report.md` — this file

**Note on mAP curves:** mAP@0.5 and mAP@0.5:0.95 are single summary values computed by integrating precision over recall (and over IoU thresholds for mAP@0.5:0.95) — they are not confidence-threshold-dependent curves like P/R/F1, so no separate "mAP curve" plot exists; this is standard object-detection evaluation practice and matches what Ultralytics produces.

## Confirmations

- Test set was **not** used during training or checkpoint selection — verified via `train_args`/`args.yaml` of every training run, which only ever reference `split=val`.
- No model weights were modified by this evaluation (`val` mode only, read-only).
- No production files were touched (`backend/yolov8n.pt` untouched).
- No new training was started.
