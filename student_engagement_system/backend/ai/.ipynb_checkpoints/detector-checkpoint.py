from ultralytics import YOLO

yolo_model = YOLO("yolov8n.pt")


def detect(frame):

    results = yolo_model(frame)[0]

    return results