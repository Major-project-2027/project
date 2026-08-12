import cv2
import numpy as np
import face_recognition


class FaceService:

    @staticmethod
    def generate_face_embedding(image):

        rgb = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

        locations = face_recognition.face_locations(rgb)

        if len(locations) == 0:
            raise Exception("No face detected.")

        if len(locations) > 1:
            raise Exception("Multiple faces detected.")

        encoding = face_recognition.face_encodings(
            rgb,
            locations
        )[0]

        return encoding.tolist()

    @staticmethod
    def compare_faces(
        stored_embedding,
        current_embedding
    ):

        result = face_recognition.compare_faces(
            [np.array(stored_embedding)],
            np.array(current_embedding),
            tolerance=0.45
        )

        return result[0]