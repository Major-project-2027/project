"""One-off ADDITIVE migration for the class-history/attendance/alerts feature.

Safe to re-run: every step checks whether it is already applied before
doing anything. Never drops or modifies existing rows/tables.

Run from the backend/ directory:
    python migrate_history.py
"""

import sqlite3

from config import DATABASE_PATH


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def main():
    print(f"Connecting to {DATABASE_PATH}")

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # ------------------------------------------------------------
    # attendance.session_id
    # ------------------------------------------------------------

    if not table_exists(cursor, "attendance"):
        print("SKIP: 'attendance' table does not exist yet "
              "(will be created by create_database.py / create_all).")
    elif column_exists(cursor, "attendance", "session_id"):
        print("OK: attendance.session_id already exists.")
    else:
        print("Adding attendance.session_id ...")
        cursor.execute(
            "ALTER TABLE attendance ADD COLUMN session_id INTEGER "
            "REFERENCES sessions(session_id)"
        )
        conn.commit()
        print("Added attendance.session_id.")

    # ------------------------------------------------------------
    # alerts table
    # ------------------------------------------------------------

    if table_exists(cursor, "alerts"):
        print("OK: 'alerts' table already exists.")
    else:
        print("Creating 'alerts' table ...")
        cursor.execute(
            """
            CREATE TABLE alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(session_id),
                student_id INTEGER NOT NULL REFERENCES students(student_id),
                class_id INTEGER NOT NULL REFERENCES classrooms(class_id),
                alert_type VARCHAR(50) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        print("Created 'alerts' table.")

    cursor.execute("SELECT COUNT(*) FROM teachers")
    print(f"\nSanity check -- existing teachers rows preserved: "
          f"{cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM engagement_records")
    print(f"Sanity check -- existing engagement_records rows preserved: "
          f"{cursor.fetchone()[0]}")

    conn.close()
    print("\nMigration complete. No existing rows were modified or deleted.")


if __name__ == "__main__":
    main()
