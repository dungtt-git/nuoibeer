import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

GROUPS_FILE = BASE_DIR / "data" / "groups.json"
FIXTURES_FILE = BASE_DIR / "data" / "fixtures.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


groups = load_json(GROUPS_FILE)
fixtures = load_json(FIXTURES_FILE)

# Reset thống kê
for group_name, teams in groups.items():
    for team in teams:

        team["played"] = 0
        team["points"] = 0
        team["goals_for"] = 0
        team["goals_against"] = 0


# Map tên đội -> object đội
team_lookup = {}

for group_name, teams in groups.items():
    for team in teams:
        team_lookup[team["name"]] = team


# Duyệt các trận
for match in fixtures:

    # Chỉ tính vòng bảng
    if match.get("stage") != "Vòng bảng":
        continue

    home_score = match.get("score_home")
    away_score = match.get("score_away")

    # Chưa có kết quả
    if home_score is None or away_score is None:
        continue

    home_name = match["home"]
    away_name = match["away"]

    if home_name not in team_lookup:
        continue

    if away_name not in team_lookup:
        continue

    home = team_lookup[home_name]
    away = team_lookup[away_name]

    # Số trận
    home["played"] += 1
    away["played"] += 1

    # Bàn thắng
    home["goals_for"] += home_score
    home["goals_against"] += away_score

    away["goals_for"] += away_score
    away["goals_against"] += home_score

    # Điểm
    if home_score > away_score:

        home["points"] += 3

    elif home_score < away_score:

        away["points"] += 3

    else:

        home["points"] += 1
        away["points"] += 1


save_json(GROUPS_FILE, groups)

print("✅ Đã cập nhật groups.json thành công")