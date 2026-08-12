"""
Object class label definitions for the Phase 5 Object Detection and Classroom
Monitoring module.

YOLOv11 (Ultralytics) ships pretrained on the 80-class COCO dataset. This module
defines the small subset of COCO classes the classroom-monitoring pipeline cares
about, plus lookup helpers so no other Phase 5 module needs to hard-code class
names or COCO class IDs directly.
"""
from typing import Dict, FrozenSet

# Full COCO class-ID -> class-name map is not required here; we only need the
# handful of classes relevant to classroom monitoring. Keeping this explicit
# (rather than importing the full 80-class list from the model backend) keeps
# this module import-safe even when Ultralytics is not installed.
COCO_CLASS_IDS: Dict[str, int] = {
    "person": 0,
    "cell phone": 67,
    "laptop": 63,
    "book": 73,
    "mouse": 64,
    "keyboard": 66,
    # COCO has no separate "monitor" class -- "tv" is the closest standard
    # class and is what a monitor/external display is detected as. We expose
    # it under the friendlier alias "monitor" for this project's API surface.
    "monitor": 62,
}

COCO_ID_TO_CLASS: Dict[int, str] = {v: k for k, v in COCO_CLASS_IDS.items()}

# Classes the functional requirements explicitly require the system to detect.
REQUIRED_CLASSES: FrozenSet[str] = frozenset({"person", "cell phone"})

# Additional classes the functional requirements list as optional.
OPTIONAL_CLASSES: FrozenSet[str] = frozenset({"laptop", "book", "mouse", "keyboard", "monitor"})

# Every class this module/pipeline is aware of.
ALL_TARGET_CLASSES: FrozenSet[str] = REQUIRED_CLASSES | OPTIONAL_CLASSES

# The class name used to flag "phone usage" in the returned payload.
PHONE_CLASS_NAME: str = "cell phone"

# The class name used to count students in the frame.
PERSON_CLASS_NAME: str = "person"


def is_target_class(class_name: str) -> bool:
    """Return True if class_name is one this pipeline tracks."""
    return class_name in ALL_TARGET_CLASSES


def class_id_for_name(class_name: str) -> int:
    """Look up the COCO class ID for a tracked class name.

    Raises:
        KeyError: If class_name is not one of the classes this module tracks.
    """
    if class_name not in COCO_CLASS_IDS:
        raise KeyError(
            f"'{class_name}' is not a tracked class. Tracked classes: "
            f"{sorted(ALL_TARGET_CLASSES)}"
        )
    return COCO_CLASS_IDS[class_name]


def class_name_for_id(class_id: int) -> str:
    """Look up the tracked class name for a COCO class ID.

    Raises:
        KeyError: If class_id does not correspond to a tracked class.
    """
    if class_id not in COCO_ID_TO_CLASS:
        raise KeyError(f"COCO class id {class_id} is not a tracked class id.")
    return COCO_ID_TO_CLASS[class_id]
