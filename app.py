import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import json
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "doi_key_bi_mat_o_day"

DB_NAME = "database.db"


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
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            match_no INTEGER NOT NULL,
            predicted_result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, match_no)
        )
    """)

    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()

def admin_required():
    return (
        "user_id" in session and
        session.get("role") == "admin"
    )

def load_fixtures():
    with open("data/fixtures.json", "r", encoding="utf-8") as f:
        return json.load(f)


def get_actual_result(match):
    home_score = match.get("score_home")
    away_score = match.get("score_away")

    if home_score is None or away_score is None:
        return None

    if home_score > away_score:
        return "home"

    if home_score < away_score:
        return "away"

    return "draw"


def login_required():
    return "user_id" in session

def load_groups():
    with open("data/groups.json", "r", encoding="utf-8") as f:
        return json.load(f)

def sort_teams(teams):
    return sorted(
        teams,
        key=lambda t: (
            t["points"],
            t["goals_for"] - t["goals_against"],
            t["goals_for"]
        ),
        reverse=True
    )

def is_match_locked(match):
    date = match.get("date")
    time_vn = match.get("time_vn")

    if not date or not time_vn:
        return False

    match_time = datetime.strptime(
        f"{date} {time_vn}",
        "%Y-%m-%d %H:%M"
    )

    lock_time = match_time - timedelta(hours=1)
    now = datetime.now()

    return now >= lock_time

def create_default_admin():
    conn = get_db()

    admin = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        ("admin",)
    ).fetchone()

    if admin is None:
        conn.execute(
            """
            INSERT INTO users (username, password, role, is_active)
            VALUES (?, ?, ?, ?)
            """,
            (
                "admin",
                generate_password_hash("admin123"),
                "admin",
                1
            )
        )
    else:
        conn.execute(
            """
            UPDATE users
            SET role = 'admin', is_active = 1
            WHERE username = 'admin'
            """
        )

    conn.commit()
    conn.close()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password)

        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, hashed_password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return "Tên đăng nhập đã tồn tại"

        conn.close()

        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
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

    fixtures = load_fixtures()
    user_id = session["user_id"]

    conn = get_db()

    if request.method == "POST":
        for match in fixtures:
            if is_match_locked(match):
                continue

            match_no = match["match_no"]
            predicted_result = request.form.get(f"match_{match_no}")

            if predicted_result:
                conn.execute("""
                    INSERT INTO predictions (
                        user_id,
                        match_no,
                        predicted_result
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, match_no)
                    DO UPDATE SET predicted_result = excluded.predicted_result
                """, (user_id, match_no, predicted_result))

    conn.commit()

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

    return render_template(
        "du_doan.html",
        fixtures=fixtures,
        predictions=predictions
    )


@app.route("/lich-su-du-doan")
def prediction_history():
    if not login_required():
        return redirect("/login")

    fixtures = load_fixtures()
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
    total_fine = 0

    for match in fixtures:
        match_no = match["match_no"]

        if match_no not in predictions:
            continue

        actual_result = get_actual_result(match)

        if actual_result is None:
            status = "Chưa có kết quả"
            fine = 0
        elif predictions[match_no] == actual_result:
            status = "Đúng"
            fine = 0
        else:
            status = "Sai"
            fine = 10000
            total_fine += fine

        history.append({
            "match": match,
            "prediction": predictions[match_no],
            "actual_result": actual_result,
            "status": status,
            "fine": fine
        })

    return render_template(
        "lich_su_du_doan.html",
        history=history,
        total_fine=total_fine
    )

@app.route("/bang-xep-hang")
def standings():
    groups = load_groups()

    for group_name in groups:
        groups[group_name] = sort_teams(groups[group_name])

    return render_template("bang_xep_hang.html", groups=groups)

@app.route("/lich-thi-dau")
def fixtures():

    fixtures = load_fixtures()

    return render_template(
        "lich_thi_dau.html",
        fixtures=fixtures
    )

@app.route("/tong-hop")
def summary():
    if not login_required():
        return redirect("/login")

    fixtures = load_fixtures()

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
                "pending": 0,
                "total_fine": 0
            }

        summary_data[username]["total_predictions"] += 1

        match = fixture_lookup.get(match_no)

        if not match:
            summary_data[username]["pending"] += 1
            continue

        actual_result = get_actual_result(match)

        if actual_result is None:
            summary_data[username]["pending"] += 1
        elif predicted_result == actual_result:
            summary_data[username]["correct"] += 1
        else:
            summary_data[username]["wrong"] += 1
            summary_data[username]["total_fine"] += 10000

    summary_list = list(summary_data.values())

    summary_list.sort(
        key=lambda item: item["total_fine"],
        reverse=True
    )

    grand_total = sum(
        item["total_fine"]
        for item in summary_list
    )

    return render_template(
        "tong_hop.html",
        summary_list=summary_list,
        grand_total=grand_total
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

    return render_template(
        "admin_users.html",
        users=users
    )

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

    conn.execute(
        "DELETE FROM predictions WHERE user_id = ?",
        (user_id,)
    )

    conn.execute(
        "DELETE FROM users WHERE id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin/users")

@app.route("/")
def home():
    if not login_required():
        return redirect("/login")

    return render_template("index.html")

init_db()
create_default_admin()

if __name__ == "__main__":
    app.run(debug=True)