import json
import sqlite3
from pathlib import Path

conn = sqlite3.connect("database.db")
with open("data/fixtures.json", "r", encoding="utf-8") as f:
    fixtures = json.load(f)

conn.execute("DELETE FROM predictions")
conn.execute("DELETE FROM matches")

for match in fixtures:
    conn.execute("""
        INSERT INTO matches (
            match_no, match_date, time_vn, stage, group_name,
            home, away, stadium, city, score_home, score_away,
            handicap_team, handicap_value, note
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        match.get("match_no"), match.get("date"), match.get("time_vn"),
        match.get("stage"), match.get("group"), match.get("home"),
        match.get("away"), match.get("stadium"), match.get("city"),
        match.get("score_home"), match.get("score_away"),
        match.get("handicap_team"), match.get("handicap_value", 0),
        match.get("note"),
    ))

conn.commit()
conn.close()
print("OK: Da import lai fixtures FIFA 2026 vao SQLite.")
print("Luu y: predictions da bi xoa de tranh lech match_no/doi bong.")
