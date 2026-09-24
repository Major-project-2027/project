"""Shared ONNX Runtime session options for the live AI pipeline.

ONNX Runtime's default intra-op thread pool gets one thread per host core,
and its idle workers spin-wait for work. On Render's free tier the
container is limited to 0.1 CPU while still seeing every host core, so
that spinning burned the CPU quota and throttled the process: measured
on the real process_frame() pipeline, total CPU per frame fell from
~1,830ms to ~93ms (YOLO call: ~2,420ms -> ~127ms) with one thread and no
spinning. Same models and inputs, so predictions are unchanged.
"""


def single_thread_ort_options(ort):
    """SessionOptions with one compute thread and spin-waiting disabled.
    `ort` is the already-imported onnxruntime module (callers import it
    lazily)."""

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.add_session_config_entry("session.intra_op.allow_spinning", "0")
    return options
