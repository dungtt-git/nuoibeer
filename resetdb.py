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

conn = sqlite3.connect("database.db")

updates = {
    # Vòng 32 đội - anh chỉnh lại placeholder theo fixtures gốc của anh nếu khác
    73: ("Nhất bảng A", "Nhì bảng B"),
    74: ("Nhất bảng C", "Hạng 3 tốt nhất A/B/F/I/J"),
    75: ("Nhì bảng E", "Nhì bảng I"),
    76: ("Nhất bảng F", "Hạng 3 tốt nhất C/E/H/I/J"),
    77: ("Nhất bảng D", "Nhì bảng F"),
    78: ("Nhất bảng B", "Hạng 3 tốt nhất E/F/I/J/K"),
    79: ("Nhất bảng J", "Nhì bảng H"),
    80: ("Nhất bảng E", "Hạng 3 tốt nhất A/B/C/G/I"),

    81: ("Nhất bảng I", "Hạng 3 tốt nhất C/D/F/G/H"),
    82: ("Nhì bảng A", "Nhì bảng C"),
    83: ("Nhất bảng K", "Hạng 3 tốt nhất D/E/I/J/L"),
    84: ("Nhất bảng H", "Nhì bảng J"),
    85: ("Nhất bảng B", "Hạng 3 tốt nhất A/D/E/F/I"),
    86: ("Nhất bảng L", "Nhì bảng K"),
    87: ("Nhất bảng G", "Hạng 3 tốt nhất A/E/H/I/J"),
    88: ("Nhì bảng D", "Nhì bảng G"),

    # Vòng 16 đội
    89: ("Thắng trận 73", "Thắng trận 74"),
    90: ("Thắng trận 75", "Thắng trận 76"),
    91: ("Thắng trận 77", "Thắng trận 78"),
    92: ("Thắng trận 79", "Thắng trận 80"),
    93: ("Thắng trận 81", "Thắng trận 82"),
    94: ("Thắng trận 83", "Thắng trận 84"),
    95: ("Thắng trận 85", "Thắng trận 86"),
    96: ("Thắng trận 87", "Thắng trận 88"),

    # Tứ kết
    97: ("Thắng trận 89", "Thắng trận 90"),
    98: ("Thắng trận 91", "Thắng trận 92"),
    99: ("Thắng trận 93", "Thắng trận 94"),
    100: ("Thắng trận 95", "Thắng trận 96"),

    # Bán kết
    101: ("Thắng trận 97", "Thắng trận 98"),
    102: ("Thắng trận 99", "Thắng trận 100"),

    # Tranh hạng ba
    103: ("Thua trận 101", "Thua trận 102"),

    # Chung kết
    104: ("Thắng trận 101", "Thắng trận 102"),
}

for match_no, (home, away) in updates.items():
    conn.execute("""
        UPDATE matches
        SET
            home = ?,
            away = ?,
            score_home = NULL,
            score_away = NULL,
            handicap_team = NULL,
            handicap_value = 0
        WHERE match_no = ?
    """, (home, away, match_no))

conn.commit()
conn.close()

print("Đã reset vòng 32 trở đi về placeholder chuẩn.")
