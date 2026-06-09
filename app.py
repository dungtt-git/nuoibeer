import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash


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
            generate_password_hash("admin123"),
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
    """
    Return:
    - "home": đội 1 thắng kèo
    - "away": đội 2 thắng kèo
    - "push": hòa kèo, không phạt
    - None: chưa có kết quả
    """
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

    if adjusted_home < adjusted_away:
        return "away"

    return "push"


def is_match_locked(match):
    date = match.get("date")
    time_vn = match.get("time_vn")

    if not date or not time_vn:
        return False

    try:
        match_time = datetime.strptime(f"{date} {time_vn}", "%Y-%m-%d %H:%M")
    except ValueError:
        return False

    lock_time = match_time - timedelta(hours=1)
    return datetime.now() >= lock_time


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

    for group_name in groups:
        groups[group_name] = sorted(
            groups[group_name],
            key=lambda t: (
                t["points"],
                t["goals_for"] - t["goals_against"],
                t["goals_for"]
            ),
            reverse=True
        )

    return groups


def get_summary_data():
    fixtures = get_matches()

    for match in fixtures:
        match["handicap_text"] = get_handicap_text(match)

    fixture_lookup = {
        match["match_no"]: match
        for match in fixtures
    }

    conn = get_db()

    rows = conn.execute("""
        SELECT
            users.username,
            predictions.match_no,
            predictions.predicted_result
        FROM predictions
        JOIN users ON users.id = predictions.user_id
        ORDER BY users.username, predictions.match_no
    """).fetchall()

    conn.close()

    summary_data = {}

    for row in rows:
        username = row["username"]
        match_no = row["match_no"]
        predicted_result = row["predicted_result"]

        if username not in summary_data:
            summary_data[username] = {
                "username": username,
                "total_predictions": 0,
                "correct": 0,
                "wrong": 0,
                "push": 0,
                "pending": 0,
                "total_beer": 0,
                "accuracy": 0
            }

        summary_data[username]["total_predictions"] += 1

        match = fixture_lookup.get(match_no)

        if not match:
            summary_data[username]["pending"] += 1
            continue

        handicap_result = get_handicap_result(match)

        if handicap_result is None:
            summary_data[username]["pending"] += 1
        elif handicap_result == "push":
            summary_data[username]["push"] += 1
        elif predicted_result == handicap_result:
            summary_data[username]["correct"] += 1
        else:
            summary_data[username]["wrong"] += 1
            summary_data[username]["total_beer"] += get_stage_points(match["stage"])

    summary_list = list(summary_data.values())

    for item in summary_list:
        counted = item["correct"] + item["wrong"]
        item["accuracy"] = round(item["correct"] * 100 / counted, 1) if counted > 0 else 0

    return summary_list


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

            if predicted_result in ["home", "away"]:
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
        match["locked"] = is_match_locked(match)
        match["handicap_text"] = get_handicap_text(match)

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

    history = []
    total_beer = 0

    for match in fixtures:
        match_no = match["match_no"]

        if match_no not in predictions:
            continue

        match["handicap_text"] = get_handicap_text(match)
        handicap_result = get_handicap_result(match)

        if handicap_result is None:
            status = "Chưa có kết quả"
            beer = 0
        elif handicap_result == "push":
            status = "Hòa kèo"
            beer = 0
        elif predictions[match_no] == handicap_result:
            status = "Đúng"
            beer = 0
        else:
            status = "Sai"
            beer = get_stage_points(match["stage"])
            total_beer += beer

        history.append({
            "match": match,
            "prediction": predictions[match_no],
            "handicap_result": handicap_result,
            "status": status,
            "beer": beer
        })

    return render_template(
        "lich_su_du_doan.html",
        history=history,
        total_beer=total_beer
    )


@app.route("/bang-xep-hang")
def standings():
    groups = calculate_standings()
    return render_template("bang_xep_hang.html", groups=groups)


@app.route("/lich-thi-dau")
def fixtures():
    fixtures = get_matches()

    for match in fixtures:
        match["handicap_text"] = get_handicap_text(match)

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
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    return redirect("/admin/users")


@app.route("/admin/matches")
def admin_matches():
    if not admin_required():
        return redirect("/login")

    matches = get_matches()

    for match in matches:
        match["handicap_text"] = get_handicap_text(match)

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
            time_vn = ?,
            score_home = ?,
            score_away = ?,
            handicap_team = ?,
            handicap_value = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE match_no = ?
    """, (
        request.form.get("time_vn") or None,
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


init_db()
seed_matches_from_json()
seed_teams_from_json()
seed_stage_points()
create_default_admin()


if __name__ == "__main__":
    app.run(debug=True)
