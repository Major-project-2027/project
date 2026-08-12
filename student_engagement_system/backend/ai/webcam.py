import cv2

camera = cv2.VideoCapture(0)

def get_frame():
    success, frame = camera.read()

    if not success:
        return None

    return frame