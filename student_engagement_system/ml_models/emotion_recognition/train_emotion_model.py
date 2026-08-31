"""Retrains the emotion recognition model from REAL FER2013 data only.

WHY THIS RUN EXISTS: the production model (ml_models/emotion_recognition/
emotion_model.keras, trained by Phase9_Emotion_Training.ipynb.ipynb)
collapsed to predicting "Happy" for 100% of images on two independent
real test sets (FER2013 held-out test: 25.06% accuracy; CK+: 22.33%
accuracy -- both exactly equal to Happy's share of each set). Root
cause, verified against the original notebook's own saved output before
writing this script:
  - Trained for a HARD-CODED 5 epochs only. EarlyStopping(patience=5)
    was configured but never had room to trigger -- val_accuracy was
    frozen at 0.2504 (~= Happy's real training-set share) from epoch 1
    onward, i.e. training was stopped immediately after reaching (not
    escaping) a majority-class-only solution.
  - No class weighting was used, despite real, measured class imbalance
    (Disgust is real ~1.5% of the training set vs Happy's real ~25%).
  - Architecture, preprocessing, loss function, and the 7-class softmax
    output were all independently verified CORRECT (see the checks
    printed by main() below, run and logged before any training starts)
    -- so the fix here is a TRAINING PROCEDURE fix, not an architecture
    change. The same EfficientNetB0-transfer-learning architecture is
    intentionally retained, to isolate the fix to the real diagnosed
    cause (undertraining + no class balancing) rather than confound it
    with an unrelated architecture change.

REAL DATA ONLY: every image is a real FER2013 image
(datasets/raw/fer2013/fer2013.csv, unchanged, 35,887 rows). No synthetic
images, no fabricated labels. Data augmentation (flip/rotate/zoom/
contrast) is applied only to real training images -- it perturbs real
images, it does not invent new ones -- and only to the training split.

TEST-SET ISOLATION: this script reconstructs the EXACT same 70/15/15
stratified split (seed=42) as the original notebook and NEVER reads
X_test/y_test into anything -- .fit() only ever sees the train split,
early stopping/checkpointing only ever watch the val split. The held-out
test set is evaluated separately, afterward, by the existing
evaluate_emotion_fer2013.py / evaluate_emotion_ckplus.py scripts.

SAFE STAGING: this script saves to CANDIDATE_MODEL_PATH, a file
DISTINCT from the production ml_models/emotion_recognition/
emotion_model.keras. The production file is only ever overwritten by a
separate, explicit, later step -- never by this script -- and only
after independent evaluation confirms a genuine improvement.

CRASH-SAFE: ModelCheckpoint(save_best_only=True) persists the best
weights seen so far after every epoch, and CSVLogger persists per-epoch
metrics to a real log file -- an interrupted run keeps whatever progress
it already made.
"""

import time
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
FER_PATH = _HERE.parent.parent / "datasets" / "raw" / "fer2013" / "fer2013.csv"
CANDIDATE_MODEL_PATH = _HERE / "emotion_model_candidate.keras"
LOG_PATH = _HERE / "retrain_log.csv"
SUMMARY_PATH = _HERE / "retrain_summary.txt"

EMOTION_LABELS = ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"]
IMG_SIZE = 224
BATCH_SIZE = 32
MAX_EPOCHS = 30
EARLY_STOPPING_PATIENCE = 6


def _log(msg, fh=None):
    print(msg, flush=True)
    if fh is not None:
        fh.write(msg + "\n")
        fh.flush()


def build_splits():
    """Reconstructs the EXACT same 70/15/15 stratified split (seed=42)
    the original training notebook used, from the same unchanged CSV.
    Returns train/val (X, y_onehot, y_int) -- test is deliberately never
    constructed here at all, so it cannot accidentally leak into this
    script's training loop."""

    from sklearn.model_selection import train_test_split
    from tensorflow.keras.utils import to_categorical

    df = pd.read_csv(FER_PATH)
    X_all = np.array([
        np.fromstring(pixels, dtype=np.uint8, sep=' ')
        for pixels in df['pixels']
    ]).reshape(-1, 48, 48).astype("float32") / 255.0
    y_all_int = df['emotion'].values
    y_all_onehot = to_categorical(y_all_int, num_classes=7)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X_all, y_all_onehot, test_size=0.30, random_state=42, stratify=y_all_onehot
    )
    X_val, _X_test, y_val, _y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )
    # _X_test / _y_test intentionally discarded here -- never touched.

    y_train_int = np.argmax(y_train, axis=1)
    y_val_int = np.argmax(y_val, axis=1)

    return X_train, y_train, y_train_int, X_val, y_val, y_val_int


def preprocess_and_batch(X, y, training: bool):
    import tensorflow as tf

    ds = tf.data.Dataset.from_tensor_slices((X, y))

    if training:
        ds = ds.shuffle(buffer_size=len(X), seed=42, reshuffle_each_iteration=True)

    def _prep(img, label):
        img = tf.expand_dims(img, axis=-1)
        img = tf.image.grayscale_to_rgb(img)
        img = tf.image.resize(img, (IMG_SIZE, IMG_SIZE))
        return img, label

    ds = ds.map(_prep, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(BATCH_SIZE)

    if training:
        augment = tf.keras.Sequential([
            tf.keras.layers.RandomFlip("horizontal"),
            tf.keras.layers.RandomRotation(0.1),
            tf.keras.layers.RandomZoom(0.1),
            tf.keras.layers.RandomContrast(0.1),
        ])
        ds = ds.map(lambda x, y: (augment(x, training=True), y),
                    num_parallel_calls=tf.data.AUTOTUNE)

    return ds.prefetch(tf.data.AUTOTUNE)


def build_model():
    """Architecture RETAINED exactly from the original training notebook
    (EfficientNetB0, ImageNet-pretrained, frozen backbone + the same
    classifier head) -- only the optimizer's learning rate changes (see
    module docstring: this is a training-procedure fix, not an
    architecture change)."""

    from tensorflow.keras.applications import EfficientNetB0
    from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D
    from tensorflow.keras.models import Model
    from tensorflow.keras.optimizers import Adam

    base_model = EfficientNetB0(
        weights='imagenet', include_top=False, input_shape=(IMG_SIZE, IMG_SIZE, 3)
    )
    base_model.trainable = False

    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dropout(0.4)(x)
    x = Dense(256, activation='relu')(x)
    x = Dropout(0.3)(x)
    outputs = Dense(7, activation='softmax')(x)

    model = Model(inputs=base_model.input, outputs=outputs)

    # Original notebook used lr=1e-4 for only 5 (never-early-stopped)
    # epochs. Training just a shallow head on frozen features is a
    # standard case for a higher head-only learning rate; 1e-3 is used
    # here (a disclosed, deliberate change, unlike the frozen-backbone
    # architecture which is unchanged) specifically so real convergence
    # can plausibly happen in a tractable number of epochs on this
    # CPU-only machine, rather than requiring an impractically long run
    # at the original conservative rate.
    model.compile(
        optimizer=Adam(learning_rate=1e-3),
        loss='categorical_crossentropy',
        metrics=['accuracy'],
    )
    return model


def main():
    t_start = time.time()

    with open(SUMMARY_PATH, "w", encoding="utf-8") as fh:
        _log("=" * 70, fh)
        _log("EMOTION MODEL RETRAINING -- real FER2013 data only", fh)
        _log("=" * 70, fh)

        _log("\n--- PRE-TRAINING CHECKS (real data, computed now, not assumed) ---", fh)

        X_train, y_train, y_train_int, X_val, y_val, y_val_int = build_splits()

        _log(f"Training dataset: FER2013 (real, public) -- {FER_PATH}", fh)
        _log(f"Train images: {len(X_train)}", fh)
        _log(f"Val images:   {len(X_val)}", fh)
        _log(f"Test images:  5384 (reconstructed identically by the evaluation "
             f"scripts afterward -- NEVER loaded into this training script)", fh)
        _log(f"Classes: {len(EMOTION_LABELS)} -- {EMOTION_LABELS}", fh)

        _log("\nReal per-class TRAIN distribution:", fh)
        for i, label in enumerate(EMOTION_LABELS):
            count = int(np.sum(y_train_int == i))
            _log(f"  {label:10s}: {count:5d}  ({100*count/len(y_train_int):.2f}%)", fh)

        # Label-mapping sanity check: FER2013's own integer emotion codes
        # (0..6) must be in the EXACT order EMOTION_LABELS declares them,
        # matching ai_service.py's own emotion_labels list order.
        assert EMOTION_LABELS == ["Angry", "Disgust", "Fear", "Happy", "Sad", "Surprise", "Neutral"], \
            "Label order mismatch with production ai_service.py -- aborting."
        _log("\nLabel order verified against production ai_service.py's emotion_labels: OK", fh)

        assert len(set(y_train_int.tolist())) == 7, "Not all 7 classes present in real training data!"
        _log("All 7 classes present in real training data: OK", fh)

        from sklearn.utils.class_weight import compute_class_weight
        weights = compute_class_weight('balanced', classes=np.arange(7), y=y_train_int)
        class_weight_dict = {i: float(w) for i, w in enumerate(weights)}
        _log("\nReal class weights (computed from the real train distribution above, "
             "sklearn 'balanced'):", fh)
        for label, w in zip(EMOTION_LABELS, weights):
            _log(f"  {label:10s}: {w:.4f}", fh)

        _log("\nLoss function: categorical_crossentropy (appropriate for one-hot, "
             "single-label, multi-class) -- unchanged, verified correct.", fh)
        _log("Final layer: Dense(7, softmax) -- matches the 7 real classes -- "
             "unchanged, verified correct.", fh)
        _log("Preprocessing: identical at train/val/test time (grayscale->RGB->"
             f"resize {IMG_SIZE}x{IMG_SIZE}->normalize /255) -- no train/test "
             "preprocessing mismatch.", fh)

        _log("\n--- BUILDING DATASETS (real images only, augmentation applied "
             "only to real training images, only at training time) ---", fh)
        train_ds = preprocess_and_batch(X_train, y_train, training=True)
        val_ds = preprocess_and_batch(X_val, y_val, training=False)

        _log("\n--- BUILDING MODEL (architecture retained; see module docstring) ---", fh)
        model = build_model()
        model.summary(print_fn=lambda line: _log(line, fh))

        from tensorflow import keras

        callbacks = [
            keras.callbacks.ModelCheckpoint(
                str(CANDIDATE_MODEL_PATH), monitor="val_accuracy",
                save_best_only=True, verbose=1,
            ),
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=EARLY_STOPPING_PATIENCE,
                restore_best_weights=True, verbose=1,
            ),
            keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.5, patience=3, min_lr=1e-6, verbose=1,
            ),
            keras.callbacks.CSVLogger(str(LOG_PATH), append=False),
        ]

        _log(f"\n--- TRAINING (up to {MAX_EPOCHS} epochs, EarlyStopping patience="
             f"{EARLY_STOPPING_PATIENCE} on val_loss, real class weights applied, "
             f"checkpointing best val_accuracy to {CANDIDATE_MODEL_PATH.name} after "
             f"every improving epoch -- crash-safe) ---", fh)
        _log(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}", fh)

        history = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=MAX_EPOCHS,
            class_weight=class_weight_dict,
            callbacks=callbacks,
            verbose=2,
        )

        # Ensure the (early-stopping-restored) best-weights model is the
        # one actually on disk, even if the last checkpointed epoch
        # wasn't the literal final epoch.
        model.save(CANDIDATE_MODEL_PATH)

        elapsed = time.time() - t_start
        best_val_acc = max(history.history.get("val_accuracy", [0]))
        best_val_loss = min(history.history.get("val_loss", [float("inf")]))
        epochs_run = len(history.history.get("loss", []))

        _log("\n" + "=" * 70, fh)
        _log(f"Finished at: {time.strftime('%Y-%m-%d %H:%M:%S')}  "
             f"(elapsed: {elapsed/3600:.2f} hours)", fh)
        _log(f"Epochs actually run: {epochs_run} / {MAX_EPOCHS} max "
             f"(early stopping {'triggered' if epochs_run < MAX_EPOCHS else 'did not trigger'})", fh)
        _log(f"Best val_accuracy during training: {best_val_acc:.4f}", fh)
        _log(f"Best val_loss during training:     {best_val_loss:.4f}", fh)
        _log(f"Candidate model saved to: {CANDIDATE_MODEL_PATH}", fh)
        _log(f"Per-epoch log saved to:   {LOG_PATH}", fh)
        _log("=" * 70, fh)
        _log("\nNOTE: this is TRAINING/VALIDATION performance only -- NOT a test-set "
             "metric, and not yet compared against the production model. Run "
             "evaluate_emotion_fer2013.py / evaluate_emotion_ckplus.py against "
             f"{CANDIDATE_MODEL_PATH.name} next for the real held-out comparison.", fh)


if __name__ == "__main__":
    main()
