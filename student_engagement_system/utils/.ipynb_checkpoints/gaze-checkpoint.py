import numpy as np

def iris_center(landmarks, iris):

    xs = [landmarks[i].x for i in iris]
    ys = [landmarks[i].y for i in iris]

    return np.mean(xs), np.mean(ys)