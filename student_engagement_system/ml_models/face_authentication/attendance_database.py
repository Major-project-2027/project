"""
Attendance record schema and CSV-backed storage.
"""
import csv
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

CSV_COLUMNS = ["student_id", "name", "date", "time", "confidence", "present"]


@dataclass
class AttendanceEntry:
    """A single attendance record.

    This mirrors the fields required by the project report while staying
    compatible with MongoDB's `attendance` collection (see
    attendance_manager.py for the Mongo-insert path).
    """
    student_id: str
    name: str
    date: str
    time: str
    confidence: float
    present: bool = True

    @classmethod
    def now(cls, student_id: str, name: str, confidence: float, present: bool = True) -> "AttendanceEntry":
        """Build an AttendanceEntry stamped with the current date/time."""
        now = datetime.now()
        return cls(student_id=student_id, name=name, date=now.strftime("%Y-%m-%d"),
                    time=now.strftime("%H:%M:%S"), confidence=round(confidence, 4), present=present)


class AttendanceCSVStore:
    """Append-only CSV ledger of attendance entries."""

    def __init__(self, csv_path: Path) -> None:
        self.csv_path = Path(csv_path)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
                writer.writeheader()

    def append(self, entry: AttendanceEntry) -> None:
        """Append one attendance entry as a new CSV row.

        Args:
            entry: The AttendanceEntry to persist.
        """
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            writer.writerow(asdict(entry))
        logger.info(f"Attendance recorded: {entry.student_id} ({entry.name}) at {entry.date} {entry.time}")

    def read_all(self) -> List[AttendanceEntry]:
        """Read every attendance entry currently stored in the CSV.

        Returns:
            List of AttendanceEntry objects, oldest first.
        """
        if not self.csv_path.exists():
            return []
        entries = []
        with open(self.csv_path, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(AttendanceEntry(
                    student_id=row["student_id"], name=row["name"], date=row["date"],
                    time=row["time"], confidence=float(row["confidence"]),
                    present=row["present"] in ("True", "true", "1"),
                ))
        return entries

    def has_attendance_today(self, student_id: str, on_date: Optional[str] = None) -> bool:
        """Check whether a student already has an attendance row for a given date.

        Args:
            student_id: Student identifier to check.
            on_date: Date string "YYYY-MM-DD"; defaults to today.

        Returns:
            True if an entry already exists for that student on that date.
        """
        target_date = on_date or datetime.now().strftime("%Y-%m-%d")
        return any(e.student_id == student_id and e.date == target_date for e in self.read_all())
