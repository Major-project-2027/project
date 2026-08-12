import sqlite3

conn = sqlite3.connect("student_engagement.db")

cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")

tables = cursor.fetchall()

print("=" * 60)
print("DATABASE TABLES")
print("=" * 60)

for table in tables:
    print(f"✔ {table[0]}")

print("=" * 60)

print(f"Total Tables : {len(tables)}")

conn.close()
