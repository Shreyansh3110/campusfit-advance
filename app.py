import os
import secrets
from functools import wraps
from datetime import datetime, date, timedelta

# Auto-load .env configuration if present
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    try:
        with open(_env_file, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k and _k not in os.environ:
                        os.environ[_k] = _v
    except Exception:
        pass

from flask import Flask, request, redirect, session, render_template, flash, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from db import (
    get_db, init_db, BADGES, update_streak, check_and_award_badges,
    get_user_badges, award_badge, get_balance, get_daily_activity_summary
)
from coach_service import generate_daily_tips
from email_service import send_daily_digest_email
from api import api_bp

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'static'))
app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
# Use a static fallback instead of a random one so Vercel doesn't break sessions on every request
app.secret_key = os.environ.get("CAMPUSFIT_SECRET") or "campusfit_super_secret_fallback_key_2024"
app.register_blueprint(api_bp)


# ---------------------------------------------------------------------------
# CSRF protection (exempts /api/* JSON/Bearer requests)
# ---------------------------------------------------------------------------

@app.before_request
def csrf_protect():
    if request.method == "POST":
        if request.path.startswith("/api/"):
            return  # Exempt REST API endpoints
        token = session.get("_csrf_token")
        sent = request.form.get("csrf_token")
        if not token or not sent or token != sent:
            abort(400, description="Invalid or missing CSRF token. Please refresh and try again.")


@app.context_processor
def inject_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return {"csrf_token": session["_csrf_token"]}


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("uid"):
                return redirect("/login")
            if role and session.get("role") != role:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco


def current_points(conn, user_id):
    return conn.execute(
        "SELECT COALESCE(SUM(points),0) p FROM activities WHERE user_id=?", (user_id,)
    ).fetchone()["p"]


def fitness_level(points):
    if points < 100:
        return "Starter"
    if points < 250:
        return "Active"
    if points < 500:
        return "Champion"
    return "Fitness Hero"


# ---------------------------------------------------------------------------
# Home / auth routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    next_url = "/login"
    if session.get("role") == "admin":
        next_url = "/admin"
    elif session.get("uid"):
        next_url = "/dashboard"
    return render_template("splash.html", next_url=next_url)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:60]
        email = request.form.get("email", "").strip().lower()[:120]
        password = request.form.get("password", "")
        goal = request.form.get("goal", "Not set")
        avatar = request.form.get("avatar", "🙂")

        if not name or not email or len(password) < 6:
            flash("Please fill all fields — password must be at least 6 characters.")
            return redirect("/register")

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users(name,email,password,goal,avatar,created_at) VALUES(?,?,?,?,?,?)",
                (name, email, generate_password_hash(password), goal, avatar,
                 datetime.now().isoformat(timespec="minutes")),
            )
            conn.commit()
        except Exception:
            flash("That email is already registered.")
            return redirect("/register")
        finally:
            conn.close()
        flash("Account created! Please log in.")
        return redirect("/login")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if u and check_password_hash(u["password"], password):
            session["uid"] = u["id"]
            session["role"] = u["role"]
            session["name"] = u["name"]
            return redirect("/admin" if u["role"] == "admin" else "/dashboard")
        flash("Invalid email or password.")
        return redirect("/login")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------------------------------------------------------------------
# Student: dashboard / activity logging
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required("student")
def dashboard():
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
    points = current_points(conn, u["id"])
    minutes = conn.execute(
        "SELECT COALESCE(SUM(minutes),0) m FROM activities WHERE user_id=?", (u["id"],)
    ).fetchone()["m"]
    acts = conn.execute(
        "SELECT * FROM activities WHERE user_id=? ORDER BY id DESC LIMIT 5", (u["id"],)
    ).fetchall()

    team = None
    if u["team_id"]:
        team = conn.execute("SELECT * FROM teams WHERE id=?", (u["team_id"],)).fetchone()

    # last 7 days chart data
    today = date.today()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    chart_labels = [d.strftime("%a") for d in days]
    chart_minutes = []
    for d in days:
        m = conn.execute(
            "SELECT COALESCE(SUM(minutes),0) m FROM activities WHERE user_id=? AND date(created_at)=?",
            (u["id"], d.isoformat()),
        ).fetchone()["m"]
        chart_minutes.append(m)

    earned = get_user_badges(conn, u["id"])
    earned_codes = {b["code"] for b in earned}
    balance = get_balance(conn, u["id"])
    summary = get_daily_activity_summary(conn, u["id"])
    daily_tips = generate_daily_tips(summary)
    conn.close()

    pct = min(100, round(minutes / 240 * 100)) if minutes else 0
    level = fitness_level(points)

    return render_template(
        "dashboard.html", u=u, points=points, minutes=minutes, acts=acts,
        pct=pct, level=level, team=team, streak=u["streak"] or 0,
        chart_labels=chart_labels, chart_minutes=chart_minutes,
        badges=earned, earned_codes=earned_codes, all_badges=BADGES,
        total_badges=len(BADGES), balance=balance,
        daily_tips=daily_tips, summary=summary,
    )


@app.route("/dashboard/send-email", methods=["POST"])
@login_required("student")
def dashboard_send_email():
    res = send_daily_digest_email(session["uid"])
    if res.get("success"):
        flash("Daily activity summary & wellness tips sent to your email! ✉️")
    else:
        flash(f"Could not send email: {res.get('error', 'Please try again')}")
    return redirect("/dashboard")


@app.route("/api/docs")
def api_docs_page():
    return render_template("api_docs.html")


@app.route("/activity", methods=["GET", "POST"])
@login_required("student")
def activity():
    if request.method == "POST":
        act = request.form.get("activity", "Walking")
        try:
            minutes = max(1, min(300, int(request.form.get("minutes", 0))))
        except ValueError:
            flash("Please enter a valid number of minutes.")
            return redirect("/activity")
        points = min(150, minutes * 2)

        conn = get_db()
        conn.execute(
            "INSERT INTO activities(user_id,activity,minutes,points,created_at) VALUES(?,?,?,?,?)",
            (session["uid"], act, minutes, points, datetime.now().isoformat(timespec="minutes")),
        )
        new_streak = update_streak(conn, session["uid"])
        conn.commit()
        newly = check_and_award_badges(conn, session["uid"])
        conn.close()

        msg = f"Activity logged! +{points} points. Streak: {new_streak} day(s) 🔥"
        if newly:
            names = ", ".join(BADGES[c]["name"] for c in newly)
            msg += f" New badge unlocked: {names} 🎉"
        flash(msg)
        return redirect("/dashboard")

    return render_template("activity.html")


@app.route("/live-workout")
@login_required("student")
def live_workout():
    return render_template("live_workout.html")


# ---------------------------------------------------------------------------

# Leaderboard (students + teams)
# ---------------------------------------------------------------------------

@app.route("/leaderboard")
@login_required()
def leaderboard():
    view = request.args.get("view", "students")
    conn = get_db()
    if view == "teams":
        rows = conn.execute("""
            SELECT t.name, COUNT(DISTINCT u.id) members,
                   COALESCE(SUM(a.points),0) points
            FROM teams t
            LEFT JOIN users u ON u.team_id = t.id
            LEFT JOIN activities a ON a.user_id = u.id
            GROUP BY t.id ORDER BY points DESC, t.name
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT u.name, u.avatar, t.name as team_name,
                   COALESCE(SUM(a.points),0) points
            FROM users u
            LEFT JOIN activities a ON u.id = a.user_id
            LEFT JOIN teams t ON u.team_id = t.id
            WHERE u.role='student'
            GROUP BY u.id, t.name ORDER BY points DESC, u.name
        """).fetchall()
    conn.close()
    return render_template("leaderboard.html", rows=rows, view=view)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

@app.route("/events")
@login_required()
def events():
    conn = get_db()
    rows = conn.execute("SELECT * FROM events ORDER BY date").fetchall()
    regs = set()
    if session["role"] == "student":
        regs = {
            r["event_id"] for r in conn.execute(
                "SELECT event_id FROM event_registrations WHERE user_id=?", (session["uid"],)
            ).fetchall()
        }
    conn.close()
    return render_template("events.html", events=rows, regs=regs)


@app.route("/join_event/<int:event_id>")
@login_required("student")
def join_event(event_id):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO event_registrations(user_id,event_id) VALUES(?,?)",
            (session["uid"], event_id),
        )
        conn.commit()
        award_badge(conn, session["uid"], "event_goer")
        conn.commit()
    except Exception:
        pass
    conn.close()
    return redirect("/events")


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@app.route("/teams")
@login_required("student")
def teams():
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
    my_team = None
    my_team_members = []
    my_team_points = 0
    if u["team_id"]:
        my_team = conn.execute("SELECT * FROM teams WHERE id=?", (u["team_id"],)).fetchone()
        my_team_members = conn.execute("""
            SELECT us.name, us.avatar, COALESCE(SUM(a.points),0) points
            FROM users us LEFT JOIN activities a ON a.user_id = us.id
            WHERE us.team_id=? GROUP BY us.id ORDER BY points DESC
        """, (u["team_id"],)).fetchall()
        my_team_points = sum(m["points"] for m in my_team_members)

    all_teams = conn.execute("""
        SELECT t.id, t.name, COUNT(DISTINCT us.id) member_count,
               COALESCE(SUM(a.points),0) points
        FROM teams t
        LEFT JOIN users us ON us.team_id = t.id
        LEFT JOIN activities a ON a.user_id = us.id
        GROUP BY t.id ORDER BY points DESC
    """).fetchall()
    conn.close()

    return render_template(
        "teams.html", my_team=my_team, my_team_members=my_team_members,
        my_team_points=my_team_points, all_teams=all_teams,
    )


@app.route("/teams/create", methods=["POST"])
@login_required("student")
def create_team():
    name = request.form.get("name", "").strip()[:40]
    description = request.form.get("description", "").strip()[:120]
    if not name:
        flash("Team name is required.")
        return redirect("/teams")
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO teams(name,description,created_by,created_at) VALUES(?,?,?,?)",
            (name, description, session["uid"], datetime.now().isoformat(timespec="minutes")),
        )
        conn.execute("UPDATE users SET team_id=? WHERE id=?", (cur.lastrowid, session["uid"]))
        conn.commit()
        award_badge(conn, session["uid"], "social")
        conn.commit()
    except Exception:
        flash("A team with that name already exists.")
    conn.close()
    return redirect("/teams")


@app.route("/teams/<int:team_id>/join", methods=["POST"])
@login_required("student")
def join_team(team_id):
    conn = get_db()
    conn.execute("UPDATE users SET team_id=? WHERE id=?", (team_id, session["uid"]))
    conn.commit()
    award_badge(conn, session["uid"], "social")
    conn.commit()
    conn.close()
    return redirect("/teams")


@app.route("/teams/leave", methods=["POST"])
@login_required("student")
def leave_team():
    conn = get_db()
    conn.execute("UPDATE users SET team_id=NULL WHERE id=?", (session["uid"],))
    conn.commit()
    conn.close()
    return redirect("/teams")


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------

@app.route("/friends")
@login_required("student")
def friends():
    conn = get_db()
    uid = session["uid"]

    pending = conn.execute("""
        SELECT f.id as fid, u.name, u.avatar FROM friendships f
        JOIN users u ON u.id = f.user_id
        WHERE f.friend_id=? AND f.status='pending'
    """, (uid,)).fetchall()

    friend_list = conn.execute("""
        SELECT us.id, us.name, us.avatar, us.streak,
               COALESCE(SUM(a.points),0) points
        FROM friendships f
        JOIN users us ON us.id = (CASE WHEN f.user_id=? THEN f.friend_id ELSE f.user_id END)
        LEFT JOIN activities a ON a.user_id = us.id
        WHERE (f.user_id=? OR f.friend_id=?) AND f.status='accepted'
        GROUP BY us.id ORDER BY points DESC
    """, (uid, uid, uid)).fetchall()

    friend_ids = [f["id"] for f in friend_list]
    feed = []
    if friend_ids:
        qmarks = ",".join("?" * len(friend_ids))
        feed = conn.execute(f"""
            SELECT a.activity, a.minutes, a.created_at, u.name, u.avatar
            FROM activities a JOIN users u ON u.id = a.user_id
            WHERE a.user_id IN ({qmarks})
            ORDER BY a.id DESC LIMIT 15
        """, friend_ids).fetchall()

    conn.close()
    return render_template("friends.html", pending=pending, friends=friend_list, feed=feed)


@app.route("/friends/add", methods=["POST"])
@login_required("student")
def add_friend():
    email = request.form.get("email", "").strip().lower()
    conn = get_db()
    target = conn.execute("SELECT * FROM users WHERE email=? AND role='student'", (email,)).fetchone()
    if not target:
        flash("No student found with that email.")
    elif target["id"] == session["uid"]:
        flash("You can't add yourself as a friend.")
    else:
        try:
            conn.execute(
                "INSERT INTO friendships(user_id,friend_id,status,created_at) VALUES(?,?,?,?)",
                (session["uid"], target["id"], "pending", datetime.now().isoformat(timespec="minutes")),
            )
            conn.commit()
            flash(f"Friend request sent to {target['name']}.")
        except Exception:
            flash("Request already sent or you're already friends.")
    conn.close()
    return redirect("/friends")


@app.route("/friends/<int:fid>/accept", methods=["POST"])
@login_required("student")
def accept_friend(fid):
    conn = get_db()
    conn.execute(
        "UPDATE friendships SET status='accepted' WHERE id=? AND friend_id=?",
        (fid, session["uid"]),
    )
    conn.commit()
    award_badge(conn, session["uid"], "friendly")
    conn.commit()
    conn.close()
    return redirect("/friends")


# ---------------------------------------------------------------------------
# Challenges (student view)
# ---------------------------------------------------------------------------

def _team_progress(conn, team_id, start_date, end_date):
    row = conn.execute("""
        SELECT COALESCE(SUM(a.points),0) p FROM activities a
        JOIN users u ON u.id = a.user_id
        WHERE u.team_id=? AND date(a.created_at) BETWEEN ? AND ?
    """, (team_id, start_date, end_date)).fetchone()
    return row["p"]


@app.route("/challenges")
@login_required("student")
def challenges():
    conn = get_db()
    u = conn.execute("SELECT team_id FROM users WHERE id=?", (session["uid"],)).fetchone()
    my_team_id = u["team_id"]

    rows = conn.execute("SELECT * FROM challenges ORDER BY start_date DESC").fetchall()
    out = []
    for c in rows:
        teams_in = conn.execute("""
            SELECT t.id, t.name FROM challenge_teams ct
            JOIN teams t ON t.id = ct.team_id WHERE ct.challenge_id=?
        """, (c["id"],)).fetchall()
        # auto-enroll every team that has at least one member (simplification: all teams compete)
        if not teams_in:
            teams_in = conn.execute("SELECT id, name FROM teams").fetchall()

        lb = []
        my_progress = None
        for t in teams_in:
            prog = _team_progress(conn, t["id"], c["start_date"], c["end_date"])
            lb.append({"name": t["name"], "progress": prog})
            if t["id"] == my_team_id:
                my_progress = prog
        lb.sort(key=lambda x: -x["progress"])

        pct = min(100, round((my_progress or 0) / c["target_points"] * 100)) if c["target_points"] else 0
        out.append({**dict(c), "leaderboard": lb, "team_progress": my_progress, "pct": pct})

    if my_team_id:
        award_badge(conn, session["uid"], "challenger") if out else None
        conn.commit()
    conn.close()
    return render_template("challenges.html", challenges=out, my_team=my_team_id)


# ---------------------------------------------------------------------------
# Rewards (student view)
# ---------------------------------------------------------------------------

@app.route("/rewards")
@login_required("student")
def rewards():
    conn = get_db()
    balance = get_balance(conn, session["uid"])
    catalog = conn.execute("SELECT * FROM rewards ORDER BY cost").fetchall()
    history = conn.execute("""
        SELECT r.name, r.icon, red.cost, red.status, red.redeemed_at
        FROM redemptions red JOIN rewards r ON r.id = red.reward_id
        WHERE red.user_id=? ORDER BY red.id DESC
    """, (session["uid"],)).fetchall()
    conn.close()
    return render_template("rewards.html", balance=balance, catalog=catalog, history=history)


@app.route("/rewards/<int:reward_id>/redeem", methods=["POST"])
@login_required("student")
def redeem_reward(reward_id):
    conn = get_db()
    reward = conn.execute("SELECT * FROM rewards WHERE id=?", (reward_id,)).fetchone()
    if not reward:
        abort(404)
    balance = get_balance(conn, session["uid"])

    if balance < reward["cost"]:
        flash(f"Not enough points — you need {reward['cost'] - balance} more ⭐ for {reward['name']}.")
    elif reward["stock"] == 0:
        flash(f"Sorry, {reward['name']} is out of stock.")
    else:
        conn.execute(
            "INSERT INTO redemptions(user_id,reward_id,cost,status,redeemed_at) VALUES(?,?,?,?,?)",
            (session["uid"], reward_id, reward["cost"], "pending",
             datetime.now().isoformat(timespec="minutes")),
        )
        if reward["stock"] > 0:
            conn.execute("UPDATE rewards SET stock=stock-1 WHERE id=?", (reward_id,))
        conn.commit()
        flash(f"Redeemed {reward['name']} for {reward['cost']} ⭐! Show this in your history at the counter.")
    conn.close()
    return redirect("/rewards")


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required("admin")
def admin():
    conn = get_db()
    students = conn.execute("SELECT COUNT(*) n FROM users WHERE role='student'").fetchone()["n"]
    activities_n = conn.execute("SELECT COUNT(*) n FROM activities").fetchone()["n"]
    points = conn.execute("SELECT COALESCE(SUM(points),0) n FROM activities").fetchone()["n"]
    events_n = conn.execute("SELECT COUNT(*) n FROM events").fetchone()["n"]
    teams_n = conn.execute("SELECT COUNT(*) n FROM teams").fetchone()["n"]
    rows = conn.execute("""
        SELECT u.name, u.email, u.goal, u.avatar,
               COALESCE(SUM(a.points),0) points, COALESCE(SUM(a.minutes),0) minutes
        FROM users u LEFT JOIN activities a ON u.id = a.user_id
        WHERE u.role='student' GROUP BY u.id ORDER BY points DESC LIMIT 10
    """).fetchall()
    conn.close()
    return render_template(
        "admin.html", students=students, activities=activities_n, points=points,
        events=events_n, teams=teams_n, rows=rows,
    )


@app.route("/admin/users")
@login_required("admin")
def admin_users():
    conn = get_db()
    rows = conn.execute("""
        SELECT u.id, u.name, u.email, u.avatar, u.streak, t.name as team_name,
               COALESCE(SUM(a.points),0) points
        FROM users u LEFT JOIN activities a ON a.user_id = u.id
        LEFT JOIN teams t ON t.id = u.team_id
        WHERE u.role='student' GROUP BY u.id ORDER BY u.name
    """).fetchall()
    conn.close()
    return render_template("admin_users.html", users=rows)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM activities WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM event_registrations WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM friendships WHERE user_id=? OR friend_id=?", (user_id, user_id))
    conn.execute("DELETE FROM user_badges WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM redemptions WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM users WHERE id=? AND role='student'", (user_id,))
    conn.commit()
    conn.close()
    flash("Student removed.")
    return redirect("/admin/users")


@app.route("/admin/events")
@login_required("admin")
def admin_events():
    conn = get_db()
    rows = conn.execute("""
        SELECT e.*, COUNT(r.id) regs FROM events e
        LEFT JOIN event_registrations r ON r.event_id = e.id
        GROUP BY e.id ORDER BY e.date
    """).fetchall()
    conn.close()
    return render_template("admin_events.html", events=rows)


@app.route("/admin/add_event", methods=["GET", "POST"])
@login_required("admin")
def add_event():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        edate = request.form.get("date", "").strip()
        points = max(0, int(request.form.get("points", 0)))
        conn = get_db()
        conn.execute(
            "INSERT INTO events(name,description,date,points) VALUES(?,?,?,?)",
            (name, description, edate, points),
        )
        conn.commit()
        conn.close()
        flash("Event created.")
        return redirect("/admin/events")
    return render_template("add_event.html", event=None)


@app.route("/admin/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def edit_event(event_id):
    conn = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        edate = request.form.get("date", "").strip()
        points = max(0, int(request.form.get("points", 0)))
        conn.execute(
            "UPDATE events SET name=?, description=?, date=?, points=? WHERE id=?",
            (name, description, edate, points, event_id),
        )
        conn.commit()
        conn.close()
        flash("Event updated.")
        return redirect("/admin/events")
    event = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    conn.close()
    if not event:
        abort(404)
    return render_template("add_event.html", event=event)


@app.route("/admin/events/<int:event_id>/delete", methods=["POST"])
@login_required("admin")
def delete_event(event_id):
    conn = get_db()
    conn.execute("DELETE FROM event_registrations WHERE event_id=?", (event_id,))
    conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()
    flash("Event deleted.")
    return redirect("/admin/events")


@app.route("/admin/activities")
@login_required("admin")
def admin_activities():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, u.name FROM activities a JOIN users u ON u.id = a.user_id
        ORDER BY a.id DESC LIMIT 200
    """).fetchall()
    conn.close()
    return render_template("admin_activities.html", acts=rows)


@app.route("/admin/activities/<int:act_id>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_activity(act_id):
    conn = get_db()
    conn.execute("DELETE FROM activities WHERE id=?", (act_id,))
    conn.commit()
    conn.close()
    flash("Activity removed.")
    return redirect("/admin/activities")


@app.route("/admin/challenges")
@login_required("admin")
def admin_challenges():
    conn = get_db()
    rows = conn.execute("SELECT * FROM challenges ORDER BY start_date DESC").fetchall()
    conn.close()
    return render_template("admin_challenges.html", challenges=rows)


@app.route("/admin/challenges/create", methods=["POST"])
@login_required("admin")
def admin_create_challenge():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    start_date = request.form.get("start_date", "").strip()
    end_date = request.form.get("end_date", "").strip()
    target_points = max(1, int(request.form.get("target_points", 500)))
    conn = get_db()
    conn.execute(
        """INSERT INTO challenges(name,description,start_date,end_date,target_points,created_by)
           VALUES(?,?,?,?,?,?)""",
        (name, description, start_date, end_date, target_points, session["uid"]),
    )
    conn.commit()
    conn.close()
    flash("Challenge created.")
    return redirect("/admin/challenges")


@app.route("/admin/challenges/<int:challenge_id>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_challenge(challenge_id):
    conn = get_db()
    conn.execute("DELETE FROM challenge_teams WHERE challenge_id=?", (challenge_id,))
    conn.execute("DELETE FROM challenges WHERE id=?", (challenge_id,))
    conn.commit()
    conn.close()
    flash("Challenge deleted.")
    return redirect("/admin/challenges")


@app.route("/admin/rewards")
@login_required("admin")
def admin_rewards():
    conn = get_db()
    catalog = conn.execute("SELECT * FROM rewards ORDER BY cost").fetchall()
    requests_ = conn.execute("""
        SELECT red.id, red.cost, red.status, red.redeemed_at, u.name as user_name, r.name as reward_name, r.icon
        FROM redemptions red
        JOIN users u ON u.id = red.user_id
        JOIN rewards r ON r.id = red.reward_id
        ORDER BY red.id DESC LIMIT 100
    """).fetchall()
    conn.close()
    return render_template("admin_rewards.html", catalog=catalog, requests=requests_)


@app.route("/admin/rewards/create", methods=["POST"])
@login_required("admin")
def admin_create_reward():
    name = request.form.get("name", "").strip()[:80]
    description = request.form.get("description", "").strip()[:200]
    icon = request.form.get("icon", "🎁").strip()[:4] or "🎁"
    try:
        cost = max(1, int(request.form.get("cost", 100)))
        stock = int(request.form.get("stock", -1))
    except ValueError:
        flash("Cost and stock must be numbers.")
        return redirect("/admin/rewards")
    if not name:
        flash("Reward name is required.")
        return redirect("/admin/rewards")
    conn = get_db()
    conn.execute(
        "INSERT INTO rewards(name,description,cost,icon,stock) VALUES(?,?,?,?,?)",
        (name, description, cost, icon, stock),
    )
    conn.commit()
    conn.close()
    flash("Reward added to catalog.")
    return redirect("/admin/rewards")


@app.route("/admin/rewards/<int:reward_id>/delete", methods=["POST"])
@login_required("admin")
def admin_delete_reward(reward_id):
    conn = get_db()
    conn.execute("DELETE FROM rewards WHERE id=?", (reward_id,))
    conn.commit()
    conn.close()
    flash("Reward removed from catalog.")
    return redirect("/admin/rewards")


@app.route("/admin/redemptions/<int:redemption_id>/<action>", methods=["POST"])
@login_required("admin")
def admin_update_redemption(redemption_id, action):
    if action not in ("fulfilled", "cancelled"):
        abort(400)
    conn = get_db()
    red = conn.execute("SELECT * FROM redemptions WHERE id=?", (redemption_id,)).fetchone()
    if not red:
        abort(404)
    conn.execute("UPDATE redemptions SET status=? WHERE id=?", (action, redemption_id))
    if action == "cancelled" and red["status"] != "cancelled":
        reward = conn.execute("SELECT stock FROM rewards WHERE id=?", (red["reward_id"],)).fetchone()
        if reward and reward["stock"] >= 0:
            conn.execute("UPDATE rewards SET stock=stock+1 WHERE id=?", (red["reward_id"],))
    conn.commit()
    conn.close()
    flash(f"Redemption marked as {action}.")
    return redirect("/admin/rewards")


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(403)
def forbidden(e):
    return "Access denied", 403


@app.errorhandler(404)
def not_found(e):
    return "Not found", 404


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=False)
