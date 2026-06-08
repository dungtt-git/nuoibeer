from flask import Flask, render_template
import json

app = Flask(__name__)

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

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/bang-xep-hang")
def standings():
    groups = load_groups()

    for group_name in groups:
        groups[group_name] = sort_teams(groups[group_name])

    return render_template("bang_xep_hang.html", groups=groups)

@app.route("/lich-thi-dau")
def fixtures():
    return render_template("lich_thi_dau.html")

@app.route("/du-doan")
def prediction():
    return render_template("du_doan.html")

if __name__ == "__main__":
    app.run(debug=True)