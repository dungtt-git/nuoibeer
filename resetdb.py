import sqlite3

conn = sqlite3.connect("database.db")

# Xóa toàn bộ dự đoán
conn.execute("DELETE FROM predictions")

# Reset toàn bộ trận đấu
conn.execute("""
UPDATE matches
SET
    score_home = NULL,
    score_away = NULL,
    handicap_team = NULL,
    handicap_value = 0
""")

conn.commit()
conn.close()

print("Đã reset dữ liệu test")