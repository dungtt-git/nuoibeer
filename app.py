import json
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from functools import cmp_to_key
from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import shutil

app = Flask(__name__)
app.secret_key = "nuoibeer_secret_key_2026"

BASE_DIR = Path(__file__).resolve().parent
DB_NAME = BASE_DIR / "database.db"
FIXTURES_FILE = BASE_DIR / "data" / "fixtures.json"
GROUPS_FILE = BASE_DIR / "data" / "groups.json"


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            match_no INTEGER NOT NULL,
            predicted_result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, match_no)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_no INTEGER UNIQUE NOT NULL,
            match_date TEXT,
            time_vn TEXT,
            stage TEXT,
            group_name TEXT,
            home TEXT NOT NULL,
            away TEXT NOT NULL,
            stadium TEXT,
            city TEXT,
            score_home INTEGER,
            score_away INTEGER,
            handicap_team TEXT,
            handicap_value REAL DEFAULT 0,
            note TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL,
            name TEXT UNIQUE NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stage_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT UNIQUE NOT NULL,
            beer_points INTEGER NOT NULL DEFAULT 10
        )
    """)

    migrations = [
        "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'",
        "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE users ADD COLUMN created_at TEXT",
        "ALTER TABLE predictions ADD COLUMN updated_at TEXT",
        "ALTER TABLE matches ADD COLUMN handicap_team TEXT",
        "ALTER TABLE matches ADD COLUMN handicap_value REAL DEFAULT 0",
    ]

    for sql in migrations:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

def seed_stage_points():
    conn = get_db()

    defaults = {
        "Vòng bảng": 10,
        "Vòng 32 đội": 15,
        "Vòng 16 đội": 20,
        "Tứ kết": 30,
        "Bán kết": 40,
        "Tranh hạng ba": 40,
        "Chung kết": 50,
    }

    for stage, beer_points in defaults.items():
        conn.execute("""
            INSERT OR IGNORE INTO stage_points (stage, beer_points)
            VALUES (?, ?)
        """, (stage, beer_points))

    conn.commit()
    conn.close()

# 3) Thêm hàm lấy điểm beer theo vòng:

def get_stage_points(stage):
    conn = get_db()

    row = conn.execute(
        "SELECT beer_points FROM stage_points WHERE stage = ?",
        (stage,)
    ).fetchone()

    conn.close()

    if row:
        return row["beer_points"]

    return 10

def load_fixtures_json():
    with open(FIXTURES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_groups_json():
    with open(GROUPS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_matches_from_json():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS total FROM matches").fetchone()["total"]

    if total > 0:
        conn.close()
        return

    fixtures = load_fixtures_json()

    for match in fixtures:
        conn.execute("""
            INSERT INTO matches (
                match_no,
                match_date,
                time_vn,
                stage,
                group_name,
                home,
                away,
                stadium,
                city,
                score_home,
                score_away,
                handicap_team,
                handicap_value,
                note
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            match.get("match_no"),
            match.get("date"),
            match.get("time_vn") or None,
            match.get("stage"),
            match.get("group"),
            match.get("home"),
            match.get("away"),
            match.get("stadium"),
            match.get("city"),
            match.get("score_home"),
            match.get("score_away"),
            None,
            0,
            match.get("note"),
        ))

    conn.commit()
    conn.close()


def seed_teams_from_json():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS total FROM teams").fetchone()["total"]

    if total > 0:
        conn.close()
        return

    groups = load_groups_json()

    for group_name, teams in groups.items():
        for team in teams:
            conn.execute("""
                INSERT OR IGNORE INTO teams (group_name, name)
                VALUES (?, ?)
            """, (group_name, team["name"]))

    conn.commit()
    conn.close()


def create_default_admin():
    conn = get_db()

    admin = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if admin is None:
        conn.execute("""
            INSERT INTO users (username, password, role, is_active)
            VALUES (?, ?, ?, ?)
        """, (
            "admin",
            generate_password_hash("PQO4WMly5P8Z"),
            "admin",
            1
        ))
    else:
        conn.execute("""
            UPDATE users
            SET role = 'admin', is_active = 1
            WHERE username = 'admin'
        """)

    conn.commit()
    conn.close()


def login_required():
    return "user_id" in session


def admin_required():
    return login_required() and session.get("role") == "admin"


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def get_matches():
    conn = get_db()

    rows = conn.execute("""
        SELECT
            match_no,
            match_date AS date,
            time_vn,
            stage,
            group_name AS "group",
            home,
            away,
            stadium,
            city,
            score_home,
            score_away,
            handicap_team,
            handicap_value,
            note
        FROM matches
        ORDER BY match_no ASC
    """).fetchall()

    conn.close()
    return rows_to_dicts(rows)


def get_handicap_text(match):
    handicap_team = match.get("handicap_team")
    handicap_value = match.get("handicap_value") or 0

    if not handicap_team or handicap_value == 0:
        return "Đồng banh"

    if handicap_team == "home":
        return f"{match.get('home')} chấp {handicap_value:g}"

    if handicap_team == "away":
        return f"{match.get('away')} chấp {handicap_value:g}"

    return "Đồng banh"


def get_handicap_result(match):
    score_home = match.get("score_home")
    score_away = match.get("score_away")

    if score_home is None or score_away is None:
        return None

    handicap_team = match.get("handicap_team")
    handicap_value = float(match.get("handicap_value") or 0)

    adjusted_home = float(score_home)
    adjusted_away = float(score_away)

    if handicap_team == "home":
        adjusted_home -= handicap_value

    elif handicap_team == "away":
        adjusted_away -= handicap_value

    if adjusted_home > adjusted_away:
        return "home"

    if adjusted_away > adjusted_home:
        return "away"

    return "draw"


def is_match_locked(match):
    date = match.get("date")
    time_vn = match.get("time_vn")

    if not date or not time_vn:
        return False

    try:
        match_time = datetime.strptime(
            f"{date} {time_vn}",
            "%Y-%m-%d %H:%M"
        )

        match_time = match_time.replace(
            tzinfo=ZoneInfo("Asia/Ho_Chi_Minh")
        )

    except ValueError:
        return False

    now = datetime.now(
        ZoneInfo("Asia/Ho_Chi_Minh")
    )

    lock_time = match_time - timedelta(hours=1)

    return now >= lock_time

def get_head_to_head_stats(team_a, team_b):
    conn = get_db()

    matches = conn.execute("""
        SELECT
            home,
            away,
            score_home,
            score_away
        FROM matches
        WHERE score_home IS NOT NULL
          AND score_away IS NOT NULL
          AND (
                (home = ? AND away = ?)
             OR (home = ? AND away = ?)
          )
    """, (
        team_a,
        team_b,
        team_b,
        team_a
    )).fetchall()

    conn.close()

    points_a = 0
    gd_a = 0
    goals_a = 0

    for match in matches:

        if match["home"] == team_a:
            scored = match["score_home"]
            conceded = match["score_away"]
        else:
            scored = match["score_away"]
            conceded = match["score_home"]

        goals_a += scored
        gd_a += scored - conceded

        if scored > conceded:
            points_a += 3
        elif scored == conceded:
            points_a += 1

    return (
        points_a,
        gd_a,
        goals_a
    )

def compare_teams(team_a, team_b):

    # 1. Điểm
    if team_a["points"] != team_b["points"]:
        return team_b["points"] - team_a["points"]

    # 2. Hiệu số
    gd_a = team_a["goals_for"] - team_a["goals_against"]
    gd_b = team_b["goals_for"] - team_b["goals_against"]

    if gd_a != gd_b:
        return gd_b - gd_a

    # 3. Bàn thắng
    if team_a["goals_for"] != team_b["goals_for"]:
        return team_b["goals_for"] - team_a["goals_for"]

    # 4. Đối đầu trực tiếp
    h2h_a = get_head_to_head_stats(
        team_a["name"],
        team_b["name"]
    )

    h2h_b = get_head_to_head_stats(
        team_b["name"],
        team_a["name"]
    )

    # điểm đối đầu
    if h2h_a[0] != h2h_b[0]:
        return h2h_b[0] - h2h_a[0]

    # hiệu số đối đầu
    if h2h_a[1] != h2h_b[1]:
        return h2h_b[1] - h2h_a[1]

    # bàn thắng đối đầu
    if h2h_a[2] != h2h_b[2]:
        return h2h_b[2] - h2h_a[2]

    return 0

def get_finished_group_matches():
    conn = get_db()

    rows = conn.execute("""
        SELECT
            group_name,
            home,
            away,
            score_home,
            score_away
        FROM matches
        WHERE stage = ?
          AND score_home IS NOT NULL
          AND score_away IS NOT NULL
    """, ("Vòng bảng",)).fetchall()

    conn.close()

    return rows

def calculate_head_to_head_table(teams, matches):
    team_names = [team["name"] for team in teams]

    h2h = {}

    for name in team_names:
        h2h[name] = {
            "name": name,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0
        }

    for match in matches:
        home = match["home"]
        away = match["away"]

        if home not in h2h or away not in h2h:
            continue

        score_home = match["score_home"]
        score_away = match["score_away"]

        h2h[home]["goals_for"] += score_home
        h2h[home]["goals_against"] += score_away

        h2h[away]["goals_for"] += score_away
        h2h[away]["goals_against"] += score_home

        if score_home > score_away:
            h2h[home]["points"] += 3
        elif score_home < score_away:
            h2h[away]["points"] += 3
        else:
            h2h[home]["points"] += 1
            h2h[away]["points"] += 1

    return h2h

def sort_tied_group(tied_teams, group_matches):
    h2h = calculate_head_to_head_table(tied_teams, group_matches)

    def h2h_key(team):
        data = h2h[team["name"]]
        h2h_gd = data["goals_for"] - data["goals_against"]

        return (
            data["points"],
            h2h_gd,
            data["goals_for"]
        )

    return sorted(
        tied_teams,
        key=h2h_key,
        reverse=True
    )

def sort_group_fifa_style(teams, group_matches):
    # Bước 1: sort theo điểm, hiệu số, bàn thắng
    teams = sorted(
        teams,
        key=lambda team: (
            team["points"],
            team["goals_for"] - team["goals_against"],
            team["goals_for"]
        ),
        reverse=True
    )

    result = []
    index = 0

    while index < len(teams):
        current = teams[index]

        tied_group = [current]
        index += 1

        while index < len(teams):
            next_team = teams[index]

            current_key = (
                current["points"],
                current["goals_for"] - current["goals_against"],
                current["goals_for"]
            )

            next_key = (
                next_team["points"],
                next_team["goals_for"] - next_team["goals_against"],
                next_team["goals_for"]
            )

            if next_key == current_key:
                tied_group.append(next_team)
                index += 1
            else:
                break

        if len(tied_group) > 1:
            tied_group = sort_tied_group(
                tied_group,
                group_matches
            )

        result.extend(tied_group)

    return result

def get_best_third_placed_teams():
    groups = calculate_standings()

    third_teams = []

    for group_name, teams in groups.items():
        if len(teams) >= 3:
            team = teams[2].copy()
            team["group"] = group_name
            team["goal_difference"] = team["goals_for"] - team["goals_against"]
            third_teams.append(team)

    third_teams = sorted(
        third_teams,
        key=lambda team: (
            team["points"],
            team["goal_difference"],
            team["goals_for"]
        ),
        reverse=True
    )

    qualified = third_teams[:8]
    eliminated = third_teams[8:]

    return qualified, eliminated

def get_best_third_team_from_groups(group_options):
    qualified_thirds, eliminated_thirds = get_best_third_placed_teams()

    for team in qualified_thirds:
        if team.get("group") in group_options:
            return team["name"]

    return None

def calculate_standings():
    conn = get_db()

    teams = conn.execute("""
        SELECT group_name, name
        FROM teams
        ORDER BY group_name ASC, name ASC
    """).fetchall()

    groups = {}

    for row in teams:
        group_name = row["group_name"]

        if group_name not in groups:
            groups[group_name] = []

        groups[group_name].append({
            "name": row["name"],
            "played": 0,
            "points": 0,
            "goals_for": 0,
            "goals_against": 0
        })

    team_lookup = {}

    for group_name, team_list in groups.items():
        for team in team_list:
            team_lookup[team["name"]] = team

    matches = conn.execute("""
        SELECT home, away, score_home, score_away
        FROM matches
        WHERE stage = ?
          AND score_home IS NOT NULL
          AND score_away IS NOT NULL
        ORDER BY match_no ASC
    """, ("Vòng bảng",)).fetchall()

    conn.close()

    for match in matches:
        home_name = match["home"]
        away_name = match["away"]

        if home_name not in team_lookup or away_name not in team_lookup:
            continue

        home = team_lookup[home_name]
        away = team_lookup[away_name]

        home_score = match["score_home"]
        away_score = match["score_away"]

        home["played"] += 1
        away["played"] += 1

        home["goals_for"] += home_score
        home["goals_against"] += away_score

        away["goals_for"] += away_score
        away["goals_against"] += home_score

        if home_score > away_score:
            home["points"] += 3
        elif home_score < away_score:
            away["points"] += 3
        else:
            home["points"] += 1
            away["points"] += 1

    all_group_matches = get_finished_group_matches()

    for group_name in groups:
        group_matches = [
            match
            for match in all_group_matches
            if match["group_name"] == group_name
        ]

        groups[group_name] = sort_group_fifa_style(
            groups[group_name],
            group_matches
        )

    return groups


def get_summary_data():
    fixtures = get_matches()

    conn = get_db()

    users = conn.execute("""
        SELECT id, username
        FROM users
        WHERE is_active = 1
        AND role <> 'admin' 
        ORDER BY username
    """).fetchall()

    prediction_rows = conn.execute("""
        SELECT user_id, match_no, predicted_result
        FROM predictions
    """).fetchall()

    conn.close()

    predictions = {}

    for row in prediction_rows:
        predictions[(row["user_id"], row["match_no"])] = row["predicted_result"]

    summary_list = []

    for user in users:
        item = {
            "username": user["username"],
            "total_predictions": 0,   # số trận user đã chốt
            "counted_matches": 0,      # số trận đã có tỷ số và được tính điểm
            "correct": 0,
            "wrong": 0,
            "missed": 0,              # đã có tỷ số nhưng user không chọn
            "push": 0,                # hòa kèo
            "pending": 0,             # chưa có tỷ số
            "total_beer": 0,
            "accuracy": 0
        }

        for match in fixtures:
            match_no = match["match_no"]
            predicted_result = predictions.get((user["id"], match_no))

            if predicted_result:
                item["total_predictions"] += 1

            handicap_result = get_handicap_result(match)

            # Trận chưa có tỷ số thì chưa tính điểm
            if handicap_result is None:
                item["pending"] += 1
                continue

            # Hòa kèo:
            # - chọn draw thì đúng
            # - chọn home/away thì sai
            # - không chọn thì bỏ lượt, tính sai
            if handicap_result == "draw":
                item["counted_matches"] += 1

                if predicted_result == "draw":
                    item["correct"] += 1
                elif predicted_result in ["home", "away"]:
                    item["wrong"] += 1
                    item["total_beer"] += get_stage_points(match["stage"])
                else:
                    item["missed"] += 1
                    item["wrong"] += 1
                    item["total_beer"] += get_stage_points(match["stage"])

                item["push"] += 1
                continue

            # Trận đã có đội thắng kèo nhưng user không chọn
            if not predicted_result:
                item["counted_matches"] += 1
                item["missed"] += 1
                item["wrong"] += 1
                item["total_beer"] += get_stage_points(match["stage"])
                continue

            # User chọn hòa nhưng thực tế không hòa kèo
            if predicted_result == "draw":
                item["counted_matches"] += 1
                item["wrong"] += 1
                item["total_beer"] += get_stage_points(match["stage"])
                continue

            # User chọn đúng đội thắng kèo
            item["counted_matches"] += 1

            if predicted_result == handicap_result:
                item["correct"] += 1
            else:
                item["wrong"] += 1
                item["total_beer"] += get_stage_points(match["stage"])

        counted = item["correct"] + item["wrong"]
        item["accuracy"] = round(item["correct"] * 100 / counted, 1) if counted > 0 else 0

        summary_list.append(item)

    return summary_list

def get_group_rank_team(group_name, rank):
    """
    Tra ve doi dung thu rank trong bang.
    rank = 1: Nhat bang
    rank = 2: Nhi bang
    """
    groups = calculate_standings()
    teams = groups.get(group_name)

    if not teams:
        return None

    index = rank - 1

    if index < 0 or index >= len(teams):
        return None

    return teams[index]["name"]


def get_match_winner(match_no):
    """
    Tra ve doi thang tran theo ty so that.
    Neu chua co ty so hoac hoa thi tra None.
    Luu y: knockout neu hoa 90 phut ma co penalty thi sau nay co the bo sung winner_team.
    """
    conn = get_db()

    match = conn.execute("""
        SELECT home, away, score_home, score_away
        FROM matches
        WHERE match_no = ?
    """, (match_no,)).fetchone()

    conn.close()

    if not match:
        return None

    if match["score_home"] is None or match["score_away"] is None:
        return None

    if match["score_home"] > match["score_away"]:
        return resolve_team_name(match["home"])

    if match["score_home"] < match["score_away"]:
        return resolve_team_name(match["away"])

    return None

def get_best_third_team_by_group(group_name):
    qualified_thirds, eliminated_thirds = get_best_third_placed_teams()

    for team in qualified_thirds:
        if team.get("group") == group_name:
            return team["name"]

    return None

def resolve_team_name(team_name):
    """
    Tu doi cac placeholder thanh ten doi that khi da co du lieu.

    Vi du:
    - Nhat bang A -> Mexico
    - Nhi bang B -> Switzerland
    - Thang tran 73 -> Mexico
    """

    if not team_name:
        return team_name

    text = team_name.strip()

    # Nhat bang A
    if text.startswith("Nhất bảng "):
        group_name = text.replace("Nhất bảng ", "").strip()
        resolved = get_group_rank_team(group_name, 1)
        return resolved or team_name

    # Nhi bang A
    if text.startswith("Nhì bảng "):
        group_name = text.replace("Nhì bảng ", "").strip()
        resolved = get_group_rank_team(group_name, 2)
        return resolved or team_name

    # Thang tran 73
    if text.startswith("Thắng trận "):
        raw = text.replace("Thắng trận ", "").strip()

        try:
            match_no = int(raw)
        except ValueError:
            return team_name

        resolved = get_match_winner(match_no)
        return resolved or team_name
    
    # Hạng 3 bảng A
    if text.startswith("Hạng 3 bảng "):
        group_name = text.replace("Hạng 3 bảng ", "").strip()
        resolved = get_best_third_team_by_group(group_name)
        return resolved or team_name

    # Hạng ba bảng A
    if text.startswith("Hạng ba bảng "):
        group_name = text.replace("Hạng ba bảng ", "").strip()
        resolved = get_best_third_team_by_group(group_name)
        return resolved or team_name    
        # Đội hạng 3 tốt nhất 1
    if text.startswith("Đội hạng 3 tốt nhất "):
        raw = text.replace("Đội hạng 3 tốt nhất ", "").strip()

        try:
            index = int(raw) - 1
        except ValueError:
            return team_name

        qualified_thirds, eliminated_thirds = get_best_third_placed_teams()

        if 0 <= index < len(qualified_thirds):
            return qualified_thirds[index]["name"]

        return team_name
    
        # Ví dụ: Hạng 3 tốt nhất A/B/C/D/F
    if text.startswith("Hạng 3 tốt nhất "):
        raw_groups = text.replace("Hạng 3 tốt nhất ", "").strip()
        group_options = [g.strip() for g in raw_groups.split("/") if g.strip()]

        resolved = get_best_third_team_from_groups(group_options)
        return resolved or team_name

    return team_name


def enrich_match_display_names(match):
    """
    Them ten hien thi cho match, khong sua du lieu goc trong DB.
    """
    match["home_display"] = resolve_team_name(match.get("home"))
    match["away_display"] = resolve_team_name(match.get("away"))

    return match

@app.context_processor
def utility_processor():
    return {
        "get_handicap_text": get_handicap_text
    }


@app.route("/")
def home():
    if not login_required():
        return redirect("/login")

    conn = get_db()

    stats = {
        "users": conn.execute("SELECT COUNT(*) AS total FROM users WHERE is_active = 1").fetchone()["total"],
        "matches": conn.execute("SELECT COUNT(*) AS total FROM matches").fetchone()["total"],
        "finished_matches": conn.execute("""
            SELECT COUNT(*) AS total
            FROM matches
            WHERE score_home IS NOT NULL AND score_away IS NOT NULL
        """).fetchone()["total"],
        "predictions": conn.execute("SELECT COUNT(*) AS total FROM predictions").fetchone()["total"],
    }

    conn.close()

    summary_list = get_summary_data()
    grand_total = sum(item["total_beer"] for item in summary_list)

    leaderboard = sorted(
        summary_list,
        key=lambda item: item["total_beer"],
        reverse=True
    )[:3]

    stats["grand_total"] = grand_total

    return render_template(
        "index.html",
        stats=stats,
        leaderboard=leaderboard
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            return "Vui lòng nhập tài khoản và mật khẩu"

        conn = get_db()

        try:
            conn.execute("""
                INSERT INTO users (username, password, role, is_active)
                VALUES (?, ?, ?, ?)
            """, (username, generate_password_hash(password), "user", 1))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Tên đăng nhập đã tồn tại"

        conn.close()
        return redirect("/login")

    return render_template("register.html")

@app.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
def reset_user_password(user_id):
    if not admin_required():
        return redirect("/login")

    new_password = request.form.get("new_password", "").strip()

    if not new_password:
        return redirect("/admin/users")

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET password = ?
        WHERE id = ?
    """, (
        generate_password_hash(new_password),
        user_id
    ))

    conn.commit()
    conn.close()

    return redirect("/admin/users")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            if user["is_active"] == 0:
                return "Tài khoản đã bị khóa"

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect("/")

        return "Sai tài khoản hoặc mật khẩu"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/du-doan", methods=["GET", "POST"])
def prediction():
    if not login_required():
        return redirect("/login")

    fixtures = get_matches()
    user_id = session["user_id"]

    if request.method == "POST":
        conn = get_db()

        for match in fixtures:
            if is_match_locked(match):
                continue

            match_no = match["match_no"]
            predicted_result = request.form.get(f"match_{match_no}")

            if predicted_result in ["home", "draw", "away"]:
                conn.execute("""
                    INSERT INTO predictions (
                        user_id,
                        match_no,
                        predicted_result,
                        updated_at
                    )
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, match_no)
                    DO UPDATE SET
                        predicted_result = excluded.predicted_result,
                        updated_at = CURRENT_TIMESTAMP
                """, (user_id, match_no, predicted_result))

        conn.commit()
        conn.close()

        return redirect("/du-doan")

    conn = get_db()
    rows = conn.execute(
        "SELECT match_no, predicted_result FROM predictions WHERE user_id = ?",
        (user_id,)
    ).fetchall()
    conn.close()

    predictions = {
        row["match_no"]: row["predicted_result"]
        for row in rows
    }

    for match in fixtures:
        enrich_match_display_names(match)
        match["locked"] = is_match_locked(match)
        match["handicap_text"] = get_handicap_text(match)
        match["beer_points"] = get_stage_points(match["stage"])

    return render_template(
        "du_doan.html",
        fixtures=fixtures,
        predictions=predictions
    )


@app.route("/lich-su-du-doan")
def prediction_history():
    if not login_required():
        return redirect("/login")

    fixtures = get_matches()
    user_id = session["user_id"]
    is_admin = session.get("role") == "admin"

    search_username = request.args.get("username", "").strip()

    fixture_lookup = {
        match["match_no"]: match
        for match in fixtures
    }

    conn = get_db()

    if is_admin:
        if search_username:
            users = conn.execute("""
                SELECT id, username
                FROM users
                WHERE username LIKE ?
                AND is_active = 1
                AND role <> 'admin'
                ORDER BY username
            """, (f"%{search_username}%",)).fetchall()
        else:
            users = conn.execute("""
                SELECT id, username
                FROM users
                 WHERE is_active = 1
                AND role <> 'admin'
                ORDER BY username
            """).fetchall()
    else:
        users = conn.execute("""
            SELECT id, username
            FROM users
            WHERE id = ?
            AND is_active = 1
        """, (user_id,)).fetchall()

    prediction_rows = conn.execute("""
        SELECT user_id, match_no, predicted_result
        FROM predictions
    """).fetchall()

    conn.close()

    predictions = {}

    for row in prediction_rows:
        predictions[(row["user_id"], row["match_no"])] = row["predicted_result"]

    history = []
    total_beer = 0

    for user in users:
        for match in fixtures:
            match_no = match["match_no"]
            predicted_result = predictions.get((user["id"], match_no))

            enrich_match_display_names(match)
            match["handicap_text"] = get_handicap_text(match)

            handicap_result = get_handicap_result(match)

            # Trận chưa có tỷ số:
            # - nếu user chưa dự đoán thì không cần hiện
            # - nếu user đã dự đoán thì hiện là chờ kết quả
            if handicap_result is None:
                if not predicted_result:
                    continue

                status = "Chưa có kết quả"
                beer = 0

            # Trận đã có kết quả nhưng user không dự đoán
            elif not predicted_result:
                status = "Không dự đoán"
                beer = get_stage_points(match["stage"])
                total_beer += beer

            # User dự đoán đúng, bao gồm cả draw
            elif predicted_result == handicap_result:
                status = "Đúng"
                beer = 0

            # User dự đoán sai
            else:
                status = "Sai"
                beer = get_stage_points(match["stage"])
                total_beer += beer

            history.append({
                "username": user["username"],
                "match": match,
                "prediction": predicted_result,
                "handicap_result": handicap_result,
                "status": status,
                "beer": beer
            })

    return render_template(
        "lich_su_du_doan.html",
        history=history,
        total_beer=total_beer,
        search_username=search_username
    )


@app.route("/bang-xep-hang")
def standings():
    groups = calculate_standings()
    qualified_thirds, eliminated_thirds = get_best_third_placed_teams()

    return render_template(
        "bang_xep_hang.html",
        groups=groups,
        qualified_thirds=qualified_thirds,
        eliminated_thirds=eliminated_thirds
    )


@app.route("/lich-thi-dau")
def fixtures():
    fixtures = get_matches()

    for match in fixtures:
        enrich_match_display_names(match)
        match["handicap_text"] = get_handicap_text(match)
        match["beer_points"] = get_stage_points(match["stage"])

    return render_template("lich_thi_dau.html", fixtures=fixtures)


@app.route("/tong-hop")
def summary():
    if not login_required():
        return redirect("/login")

    summary_list = get_summary_data()
    summary_list.sort(key=lambda item: item["total_beer"], reverse=True)
    total_beer = sum(item["total_beer"] for item in summary_list)

    return render_template(
        "tong_hop.html",
        summary_list=summary_list,
        total_beer=total_beer
    )


@app.route("/leaderboard")
def leaderboard():
    if not login_required():
        return redirect("/login")

    summary_list = get_summary_data()
    summary_list.sort(
        key=lambda item: (item["accuracy"], item["correct"], -item["total_beer"]),
        reverse=True
    )

    return render_template("leaderboard.html", leaderboard=summary_list)

@app.route("/admin/stage-points", methods=["GET", "POST"])
def admin_stage_points():
    if not admin_required():
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":
        rows = conn.execute("SELECT stage FROM stage_points").fetchall()

        for row in rows:
            stage = row["stage"]
            value = request.form.get(stage)

            if value is not None and value.strip() != "":
                conn.execute("""
                    UPDATE stage_points
                    SET beer_points = ?
                    WHERE stage = ?
                """, (int(value), stage))

        conn.commit()

    stage_points = conn.execute("""
        SELECT stage, beer_points
        FROM stage_points
        ORDER BY id ASC
    """).fetchall()

    conn.close()

    return render_template(
        "admin_stage_points.html",
        stage_points=stage_points
    )

@app.route("/admin/users")
def admin_users():
    if not admin_required():
        return redirect("/login")

    conn = get_db()
    users = conn.execute("""
        SELECT
            users.id,
            users.username,
            users.role,
            users.is_active,
            COUNT(predictions.id) AS total_predictions
        FROM users
        LEFT JOIN predictions ON predictions.user_id = users.id
        GROUP BY users.id
        ORDER BY users.id ASC
    """).fetchall()
    conn.close()

    return render_template("admin_users.html", users=users)


@app.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
def toggle_user(user_id):
    if not admin_required():
        return redirect("/login")

    if user_id == session["user_id"]:
        return redirect("/admin/users")

    conn = get_db()
    user = conn.execute(
        "SELECT is_active FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if user:
        new_status = 0 if user["is_active"] == 1 else 1
        conn.execute(
            "UPDATE users SET is_active = ? WHERE id = ?",
            (new_status, user_id)
        )
        conn.commit()

    conn.close()
    return redirect("/admin/users")


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):

    if not admin_required():
        return redirect("/login")

    if user_id == session["user_id"]:
        return redirect("/admin/users")

    conn = get_db()

    conn.execute("""
        UPDATE users
        SET is_active = 0
        WHERE id = ?
    """, (user_id,))

    conn.commit()
    conn.close()

    return redirect("/admin/users")


@app.route("/admin/matches")
def admin_matches():
    if not admin_required():
        return redirect("/login")

    matches = get_matches()

    for match in matches:
        enrich_match_display_names(match)
        match["handicap_text"] = get_handicap_text(match)
        match["beer_points"] = get_stage_points(match["stage"])

    return render_template("admin_matches.html", matches=matches)


@app.route("/admin/matches/<int:match_no>/update", methods=["POST"])
def update_match(match_no):
    if not admin_required():
        return redirect("/login")

    score_home_raw = request.form.get("score_home", "").strip()
    score_away_raw = request.form.get("score_away", "").strip()

    score_home = int(score_home_raw) if score_home_raw != "" else None
    score_away = int(score_away_raw) if score_away_raw != "" else None

    handicap_team = request.form.get("handicap_team") or None
    handicap_value_raw = request.form.get("handicap_value", "").strip()
    handicap_value = float(handicap_value_raw) if handicap_value_raw != "" else 0

    if handicap_team not in ["home", "away"]:
        handicap_team = None
        handicap_value = 0

    conn = get_db()
    conn.execute("""
        UPDATE matches
        SET
            match_date = ?,
            time_vn = ?,
            home = ?,
            away = ?,
            score_home = ?,
            score_away = ?,
            handicap_team = ?,
            handicap_value = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE match_no = ?
    """, (
        request.form.get("match_date") or None,
        request.form.get("time_vn") or None,
        request.form.get("home") or "",
        request.form.get("away") or "",
        score_home,
        score_away,
        handicap_team,
        handicap_value,
        match_no
    ))
    conn.commit()
    conn.close()

    return redirect("/admin/matches")


@app.route("/admin/backup")
def backup_db():
    if not admin_required():
        return redirect("/login")

    if not DB_NAME.exists():
        return "Chưa có database.db"

    return send_file(
        DB_NAME,
        as_attachment=True,
        download_name="nuoibeer_database_backup.db"
    )
@app.route("/admin/restore", methods=["GET", "POST"])
def restore_db():
    if not admin_required():
        return redirect("/login")

    message = ""

    if request.method == "POST":
        backup_file = request.files.get("backup_file")

        if not backup_file or backup_file.filename == "":
            message = "Chưa chọn file backup."
            return render_template("restore_db.html", message=message)

        if not backup_file.filename.endswith(".db"):
            message = "File backup phải có đuôi .db."
            return render_template("restore_db.html", message=message)

        # Backup database hiện tại trước khi restore
        if DB_NAME.exists():
            safety_backup = BASE_DIR / "database_before_restore.db"
            shutil.copy(DB_NAME, safety_backup)

        # Ghi đè database.db bằng file backup upload
        backup_file.save(DB_NAME)

        message = "Restore thành công. Anh hãy restart app để chắc chắn dữ liệu mới được nạp."

    return render_template("restore_db.html", message=message)

init_db()
seed_matches_from_json()
seed_teams_from_json()
seed_stage_points()
create_default_admin()

if __name__ == "__main__":
    app.run(debug=True)
