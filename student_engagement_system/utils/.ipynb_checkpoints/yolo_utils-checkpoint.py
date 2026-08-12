from ultralytics import YOLO

from utils.config import *


class YOLODetector:

    def __init__(self):

        self.model = YOLO("yolov8n.pt")

    def detect(self, frame):

        results = self.model(frame, verbose=False)

        persons = 0
        phone = False

        for box in results[0].boxes:

            cls = int(box.cls[0])

            label = self.model.names[cls]

            if label == PERSON_CLASS:
                persons += 1

            elif label == PHONE_CLASS:
                phone = True

        annotated = results[0].plot()

        return annotated, persons, phone