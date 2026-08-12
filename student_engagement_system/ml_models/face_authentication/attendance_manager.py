"""
High-level attendance operations: mark_attendance() with duplicate
prevention, plus an optional MongoDB mirror.
"""
from pathlib import Path
from typing import Optional

from ml_models.face_authentication.attendance_database import AttendanceCSVStore, AttendanceEntry
from utils.logger import get_logger

logger = get_logger(__name__)


class DuplicateAttendanceError(Exception):
    """Raised when a student already has an attendance record for today."""


class AttendanceManager:
    """Coordinates CSV (always) and MongoDB (optional) attendance writes."""

    def __init__(self, csv_path: Path, mongo_uri: Optional[str] = None,
                 mongo_db_name: Optional[str] = None, collection_name: str = "attendance") -> None:
        """
        Args:
            csv_path: Path to the attendance CSV ledger.
            mongo_uri: Optional MongoDB connection URI. If None, MongoDB
                mirroring is skipped entirely (CSV-only mode).
            mongo_db_name: MongoDB database name to write to.
            collection_name: Collection name -- defaults to "attendance",
                matching configs/database.yaml from Phase 1.
        """
        self.store = AttendanceCSVStore(csv_path)
        self._mongo_collection = None
        if mongo_uri and mongo_db_name:
            try:
                from pymongo import MongoClient
                client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
                client.admin.command("ping")
                self._mongo_collection = client[mongo_db_name][collection_name]
                logger.info(f"AttendanceManager connected to MongoDB collection '{collection_name}'.")
            except Exception as exc:  # noqa: BLE001 -- MongoDB is optional for this module
                logger.warning(f"MongoDB unavailable, continuing in CSV-only mode: {exc}")
                self._mongo_collection = None

    def mark_attendance(self, student_id: str, name: str, confidence: float,
                         allow_duplicate: bool = False) -> AttendanceEntry:
        """Mark a student present, preventing duplicate attendance for today.

        Args:
            student_id: Matched student's ID.
            name: Matched student's name.
            confidence: Match confidence (cosine similarity) from FaceMatcher.
            allow_duplicate: If True, bypass the duplicate-attendance check
                (useful for tests or manual corrections).

        Returns:
            The AttendanceEntry that was recorded.

        Raises:
            DuplicateAttendanceError: If the student already has an entry
                for today and ``allow_duplicate`` is False.
        """
        if not allow_duplicate and self.store.has_attendance_today(student_id):
            raise DuplicateAttendanceError(
                f"Student {student_id} already has attendance recorded today."
            )

        entry = AttendanceEntry.now(student_id=student_id, name=name, confidence=confidence)
        self.store.append(entry)

        if self._mongo_collection is not None:
            try:
                self._mongo_collection.insert_one(entry.__dict__.copy())
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"MongoDB insert failed, CSV record still saved: {exc}")

        return entry
