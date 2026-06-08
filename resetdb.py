import sqlite3

conn = sqlite3.connect("database.db")

conn.execute("""
UPDATE matches
SET
    score_home = NULL,
    score_away = NULL
""")

conn.commit()
conn.close()

print("Đã reset toàn bộ tỷ số")

conn = sqlite3.connect("database.db")

conn.execute("DELETE FROM predictions")

conn.commit()
conn.close()

print("Đã xóa toàn bộ dự đoán")