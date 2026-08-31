import os

import cv2
import numpy as np

try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    # face_recognition (dlib) is an optional, heavy dependency. If it isn't
    # installed, the rest of the backend (registration, login, enrollment,
    # live-class join, AI monitoring) must keep working -- only the face
    # registration/verification endpoints degrade, and they must report
    # that clearly rather than silently pretending to authenticate.
    face_recognition = None
    FACE_RECOGNITION_AVAILABLE = False

# face_recognition's compare_faces() default tolerance is 0.6. This project
# uses 0.45 -- stricter than the library default -- because this gate is a
# security check (don't let Student A join as Student B), not a casual
# "find similar photos" search: a false ACCEPT (letting the wrong student
# in) is worse here than an occasional false REJECT (a legitimate student
# has to retry once). 0.45 is also the value this codebase already shipped
# with in compare_faces() below, so verification stays consistent with
# whatever tolerance registration-time tooling assumed.
MATCH_TOLERANCE = 0.45


class FaceBackendUnavailable(Exception):
    """Raised when the face_recognition/dlib backend isn't installed.

    Callers must surface this as a clear "face authentication unavailable"
    condition -- never as a match/no-match result.
    """


class FaceService:

    @staticmethod
    def _require_backend():
        if not FACE_RECOGNITION_AVAILABLE:
            raise FaceBackendUnavailable(
                "Face recognition backend is not installed "
                "(face_recognition/dlib). Face authentication is "
                "unavailable until it is installed."
            )

    @staticmethod
    def generate_face_embedding(image):

        FaceService._require_backend()

        rgb = cv2.cvtColor(
            image,
            cv2.COLOR_BGR2RGB
        )

        # TEMPORARY DIAGNOSTIC -- see routes/student.py's matching
        # AI_FACE_VERIFY_DEBUG block. This is the exact array passed into
        # dlib via face_recognition immediately below -- prints its
        # shape/dtype/contiguity so a dlib "Unsupported image type" error
        # can be matched to the actual array that triggered it. Remove
        # once root-caused.
        if os.environ.get("AI_FACE_VERIFY_DEBUG", "1") != "0":
            print(
                f"[FACE_VERIFY_DEBUG] pre-dlib image: input shape={image.shape} "
                f"input dtype={image.dtype} rgb shape={rgb.shape} "
                f"rgb dtype={rgb.dtype} rgb ndim={rgb.ndim} "
                f"C_CONTIGUOUS={rgb.flags['C_CONTIGUOUS']} "
                f"WRITEABLE={rgb.flags['WRITEABLE']}",
                flush=True,
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

        FaceService._require_backend()

        result = face_recognition.compare_faces(
            [np.array(stored_embedding)],
            np.array(current_embedding),
            tolerance=MATCH_TOLERANCE
        )

        return result[0]

    @staticmethod
    def verify_against_registration(stored_embeddings, current_embedding):
        """Compare one live embedding against every sample captured during
        registration (multiple angles), and match if it is close enough to
        ANY of them.

        Registration stores several samples of the same student (straight,
        left, right, up, down) precisely so a live verification frame --
        which will rarely be a perfect head-on match -- has a good chance
        of being close to at least one registered angle.

        Returns:
            (matched: bool, best_distance: float) -- best_distance is the
            smallest face-distance across all stored samples, for logging/
            debugging. Lower distance = more similar; MATCH_TOLERANCE is
            the cutoff.
        """

        FaceService._require_backend()

        if not stored_embeddings:
            return False, None

        # A single legacy registration may have stored one flat embedding
        # instead of a list of samples -- normalize to a list either way.
        samples = stored_embeddings
        if samples and isinstance(samples[0], (int, float)):
            samples = [samples]

        distances = face_recognition.face_distance(
            [np.array(sample) for sample in samples],
            np.array(current_embedding),
        )

        best_distance = float(min(distances))

        return best_distance <= MATCH_TOLERANCE, best_distance
