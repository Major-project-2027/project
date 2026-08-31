"""
emotion_model.py
----------------
Model architecture definition for the Emotion Detection module.

Per the architecture document (Section 8 — Pretrained Models & Transfer
Learning Strategy): "MobileNetV2 (ImageNet pretrained). Transfer learning:
freeze early conv blocks, replace classifier head, fine-tune on FER-2013."

This module only builds the Keras model graph. Training orchestration
(callbacks, two-phase fine-tuning loop, class weights) lives in trainer.py;
this keeps the architecture reusable and independently testable.
"""

from __future__ import annotations

from tensorflow import keras
from tensorflow.keras import layers

from config import DROPOUT_RATE, INPUT_SHAPE, NUM_CLASSES


def build_emotion_model(
    input_shape: tuple = INPUT_SHAPE,
    num_classes: int = NUM_CLASSES,
    dropout_rate: float = DROPOUT_RATE,
) -> keras.Model:
    """Build a MobileNetV2-backed emotion classifier.

    Architecture:
        Input -> preprocess_input (MobileNetV2 scaling) -> MobileNetV2 base
        (ImageNet weights, frozen initially) -> GlobalAveragePooling2D ->
        Dropout -> Dense(128, relu) -> Dropout -> Dense(num_classes, softmax)

    The base model is returned already attached to the functional graph;
    trainer.py accesses `model.get_layer("mobilenetv2_1.00_96")`-style base
    via the `base_model` attribute stashed on the returned model object for
    convenient freezing/unfreezing during the fine-tuning phase.
    """
    inputs = keras.Input(shape=input_shape, name="image_input")

    # MobileNetV2 expects inputs preprocessed to [-1, 1]; our pipeline
    # produces [0, 1] float32 images, so we rescale ourselves inside the
    # graph. This keeps preprocessing baked into the exported model, so
    # predictor.py just needs to feed [0, 1] floats.
    x = layers.Rescaling(scale=2.0, offset=-1.0, name="rescale_to_pm1")(inputs)

    base_model = keras.applications.MobileNetV2(
        input_shape=input_shape,
        include_top=False,
        weights="imagenet",
        pooling=None,
    )
    base_model.trainable = False  # frozen for the initial "head" training phase

    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D(name="global_avg_pool")(x)
    x = layers.Dropout(dropout_rate, name="dropout_1")(x)
    x = layers.Dense(128, activation="relu", name="dense_128")(x)
    x = layers.Dropout(dropout_rate / 2, name="dropout_2")(x)
    outputs = layers.Dense(num_classes, activation="softmax", name="emotion_output")(x)

    model = keras.Model(inputs, outputs, name="emotion_mobilenetv2")

    # Stash a reference to the base model so trainer.py can toggle
    # `.trainable` and iterate `.layers` during the fine-tuning phase
    # without needing to know Keras's internal layer-naming scheme.
    model.base_model = base_model
    return model


def compile_model(model: keras.Model, learning_rate: float) -> keras.Model:
    """(Re)compile the model with a given learning rate. Called once for
    the frozen-head phase and again (with a lower LR) for fine-tuning,
    since Keras requires a re-compile after changing layer trainability."""
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


if __name__ == "__main__":
    m = build_emotion_model()
    m.summary()
