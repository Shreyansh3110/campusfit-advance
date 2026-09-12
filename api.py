"""
CampusFit Interactive REST API Blueprint
Provides comprehensive, token- and session-authenticated JSON endpoints
for mobile apps, web clients, AI coach interactions, and daily email digests.
"""

from functools import wraps
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from db import (
    get_db, BADGES, update_streak, check_and_award_badges,
    award_badge, get_balance, generate_api_token, verify_api_token,
    get_daily_activity_summary, log_email, get_email_logs,
    save_coach_message, get_coach_history, get_user_badges,
    get_setting, set_setting, get_all_settings
)
from coach_service import (
    generate_daily_tips, get_activity_coach_feedback, chat_with_coach
)
from email_service import (
    send_daily_digest_email, get_smtp_config, send_test_smtp_email
)

api_bp = Blueprint("api", __name__, url_prefix="/api")


# ---------------------------------------------------------------------------
# Auth Decorator: Supports Bearer Token and Web Session
# ---------------------------------------------------------------------------

def api_auth_required(role=None):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = None
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1].strip()
                conn = get_db()
                user = verify_api_token(conn, token)
                conn.close()

            # Fallback to active Flask web session
            if not user and session.get("uid"):
                conn = get_db()
                user = conn.execute("SELECT * FROM users WHERE id=?", (session["uid"],)).fetchone()
                conn.close()

            if not user:
                return jsonify({"error": "Unauthorized. Please provide a valid Bearer token or log in."}), 401

            if role and user["role"] != role:
                return jsonify({"error": "Forbidden. Insufficient permissions."}), 403

            request.api_user = user
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def _user_dict(u):
    return {
        "id": u["id"],
        "name": u["name"],
        "email": u["email"],
        "goal": u["goal"],
        "role": u["role"],
        "avatar": u["avatar"],
        "streak": u["streak"] or 0,
        "team_id": u["team_id"],
        "created_at": u["created_at"],
    }


# ---------------------------------------------------------------------------
# 1. Authentication Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/auth/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()[:60]
    email = (data.get("email") or "").strip().lower()[:120]
    password = data.get("password") or ""
    goal = data.get("goal") or "General Fitness"
    avatar = data.get("avatar") or "🙂"

    if not name or not email or len(password) < 6:
        return jsonify({"error": "Name, valid email, and password (min 6 chars) are required."}), 400

    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users(name,email,password,goal,avatar,created_at) VALUES(?,?,?,?,?,?)",
            (name, email, generate_password_hash(password), goal, avatar,
             datetime.now().isoformat(timespec="minutes")),
        )
        user_id = cur.lastrowid
        token, expires_at = generate_api_token(conn, user_id)
        u = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        conn.commit()
        return jsonify({
            "success": True,
            "message": "Account created successfully.",
            "token": token,
            "expires_at": expires_at,
            "user": _user_dict(u)
        }), 201
    except Exception as e:
        return jsonify({"error": "Email is already registered."}), 409
    finally:
        conn.close()


@api_bp.route("/auth/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not u or not check_password_hash(u["password"], password):
        conn.close()
        return jsonify({"error": "Invalid email or password."}), 401

    token, expires_at = generate_api_token(conn, u["id"])
    conn.close()

    # Also bind to session if requested from browser
    session["uid"] = u["id"]
    session["role"] = u["role"]
    session["name"] = u["name"]

    return jsonify({
        "success": True,
        "message": "Logged in successfully.",
        "token": token,
        "expires_at": expires_at,
        "user": _user_dict(u)
    })


@api_bp.route("/auth/me", methods=["GET"])
@api_auth_required()
def api_me():
    u = request.api_user
    conn = get_db()
    summary = get_daily_activity_summary(conn, u["id"])
    balance = get_balance(conn, u["id"])
    badges = get_user_badges(conn, u["id"])
    conn.close()

    user_info = _user_dict(u)
    user_info["balance"] = balance
    user_info["badges_count"] = len(badges)
    user_info["badges"] = badges

    return jsonify({
        "success": True,
        "user": user_info,
        "daily_summary": summary
    })


@api_bp.route("/auth/token", methods=["POST"])
@api_auth_required()
def api_generate_token():
    u = request.api_user
    conn = get_db()
    token, expires_at = generate_api_token(conn, u["id"])
    conn.close()
    return jsonify({
        "success": True,
        "token": token,
        "expires_at": expires_at
    })


# ---------------------------------------------------------------------------
# 2. Daily Activity & Tracking Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/activities", methods=["GET"])
@api_auth_required()
def api_get_activities():
    u = request.api_user
    period = request.args.get("period", "all")
    limit = max(1, min(100, int(request.args.get("limit", 20))))

    conn = get_db()
    today = date.today().isoformat()
    if period == "today":
        rows = conn.execute(
            "SELECT * FROM activities WHERE user_id=? AND date(created_at)=? ORDER BY id DESC LIMIT ?",
            (u["id"], today, limit)
        ).fetchall()
    elif period == "week":
        week_start = (date.today() - timedelta(days=6)).isoformat()
        rows = conn.execute(
            "SELECT * FROM activities WHERE user_id=? AND date(created_at)>=? ORDER BY id DESC LIMIT ?",
            (u["id"], week_start, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM activities WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (u["id"], limit)
        ).fetchall()

    summary = get_daily_activity_summary(conn, u["id"])
    conn.close()

    activities = [dict(r) for r in rows]
    return jsonify({
        "success": True,
        "period": period,
        "count": len(activities),
        "activities": activities,
        "daily_summary": summary
    })


@api_bp.route("/activities", methods=["POST"])
@api_auth_required("student")
def api_log_activity():
    u = request.api_user
    data = request.get_json(silent=True) or request.form
    act = (data.get("activity") or "Walking").strip()[:60]
    try:
        minutes = max(1, min(300, int(data.get("minutes", 0))))
    except (ValueError, TypeError):
        return jsonify({"error": "Minutes must be an integer between 1 and 300."}), 400

    points = min(150, minutes * 2)

    conn = get_db()
    now_iso = datetime.now().isoformat(timespec="minutes")
    cur = conn.execute(
        "INSERT INTO activities(user_id,activity,minutes,points,created_at) VALUES(?,?,?,?,?)",
        (u["id"], act, minutes, points, now_iso),
    )
    activity_id = cur.lastrowid
    new_streak = update_streak(conn, u["id"])
    conn.commit()

    newly_earned = check_and_award_badges(conn, u["id"])
    new_badge_names = [BADGES[code]["name"] for code in newly_earned if code in BADGES]

    # Generate instant AI coach feedback
    coach_feedback = get_activity_coach_feedback(act, minutes, points, new_streak, new_badge_names)

    # Get updated summary
    summary = get_daily_activity_summary(conn, u["id"])
    conn.close()

    return jsonify({
        "success": True,
        "message": f"Logged {minutes} mins of {act}! +{points} points.",
        "activity": {
            "id": activity_id,
            "activity": act,
            "minutes": minutes,
            "points": points,
            "created_at": now_iso
        },
        "points_earned": points,
        "new_streak": new_streak,
        "newly_awarded_badges": new_badge_names,
        "coach_feedback": coach_feedback,
        "daily_summary": summary
    }), 201


@api_bp.route("/activities/daily-summary", methods=["GET"])
@api_auth_required()
def api_daily_summary():
    u = request.api_user
    target_date = request.args.get("date")
    conn = get_db()
    summary = get_daily_activity_summary(conn, u["id"], target_date)
    conn.close()

    if not summary:
        return jsonify({"error": "Unable to compute daily summary"}), 404

    return jsonify({
        "success": True,
        "summary": summary
    })


# ---------------------------------------------------------------------------
# 3. Smart AI Coach & Chat Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/coach/tips", methods=["GET"])
@api_auth_required()
def api_coach_tips():
    u = request.api_user
    conn = get_db()
    summary = get_daily_activity_summary(conn, u["id"])
    conn.close()

    tips = generate_daily_tips(summary)
    return jsonify({
        "success": True,
        "tips": tips,
        "summary": summary
    })


@api_bp.route("/coach/chat", methods=["POST"])
@api_auth_required()
def api_coach_chat():
    u = request.api_user
    data = request.get_json(silent=True) or request.form
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "Message is required."}), 400

    conn = get_db()
    summary = get_daily_activity_summary(conn, u["id"])
    history = get_coach_history(conn, u["id"], limit=6)

    # Record student message in conversation log
    save_coach_message(conn, u["id"], "user", message)

    # Process response
    response_data = chat_with_coach(message, summary, history)

    # Record coach message in conversation log
    save_coach_message(conn, u["id"], "coach", response_data["reply"])
    conn.close()

    return jsonify({
        "success": True,
        "reply": response_data["reply"],
        "source": response_data["source"],
        "suggested_actions": response_data["suggested_actions"],
        "quick_replies": response_data["quick_replies"],
        "daily_context": {
            "streak": summary["streak"],
            "today_minutes": summary["today_minutes"],
            "goal": summary["goal"]
        }
    })


@api_bp.route("/coach/history", methods=["GET"])
@api_auth_required()
def api_coach_history():
    u = request.api_user
    limit = max(1, min(50, int(request.args.get("limit", 15))))
    conn = get_db()
    history = get_coach_history(conn, u["id"], limit)
    conn.close()
    return jsonify({
        "success": True,
        "count": len(history),
        "history": history
    })


# ---------------------------------------------------------------------------
# 4. Email Notification & Daily Digest Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/notifications/send-daily-digest", methods=["POST"])
@api_auth_required()
def api_send_daily_digest():
    u = request.api_user
    data = request.get_json(silent=True) or {}
    custom_email = data.get("email") if isinstance(data, dict) else None

    result = send_daily_digest_email(u["id"], recipient_email=custom_email)
    status_code = 200 if result.get("success") else 500
    return jsonify(result), status_code


@api_bp.route("/notifications/history", methods=["GET"])
@api_auth_required()
def api_notification_history():
    u = request.api_user
    limit = max(1, min(50, int(request.args.get("limit", 20))))
    conn = get_db()
    logs = get_email_logs(conn, u["id"], limit)
    conn.close()
    return jsonify({
        "success": True,
        "count": len(logs),
        "notifications": logs
    })


@api_bp.route("/notifications/preview-latest", methods=["GET"])
@api_auth_required()
def api_preview_latest_email():
    u = request.api_user
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM email_logs WHERE user_id=? ORDER BY id DESC LIMIT 1",
        (u["id"],)
    ).fetchone()
    conn.close()

    if not row:
        # Generate on the fly if none exists yet
        result = send_daily_digest_email(u["id"])
        return jsonify({
            "success": True,
            "html": result.get("preview_html", ""),
            "subject": result.get("subject", ""),
            "recipient": u["email"]
        })

    if request.args.get("format") == "html":
        return row["body_html"]

    return jsonify({
        "success": True,
        "html": row["body_html"],
        "subject": row["subject"],
        "recipient": row["recipient"],
        "sent_at": row["sent_at"],
        "status": row["status"]
    })


# ---------------------------------------------------------------------------
# 5. Email & AI Settings Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/settings", methods=["GET"])
@api_auth_required()
def api_get_settings():
    conn = get_db()
    smtp_cfg = get_smtp_config(conn)
    gemini_key = get_setting(conn, "gemini_api_key", "")
    conn.close()

    # Mask password
    masked_pass = "••••••••" if smtp_cfg["pass"] else ""
    masked_gemini = (gemini_key[:4] + "..." + gemini_key[-4:]) if len(gemini_key) > 8 else ("Set" if gemini_key else "")

    return jsonify({
        "success": True,
        "smtp": {
            "host": smtp_cfg["host"],
            "port": smtp_cfg["port"],
            "user": smtp_cfg["user"],
            "from": smtp_cfg["from"],
            "has_password": bool(smtp_cfg["pass"]),
            "password_masked": masked_pass,
            "is_configured": smtp_cfg["is_configured"]
        },
        "gemini": {
            "has_key": bool(gemini_key),
            "key_masked": masked_gemini
        }
    })


@api_bp.route("/settings", methods=["POST"])
@api_auth_required()
def api_save_settings():
    data = request.get_json(silent=True) or request.form
    conn = get_db()

    if "smtp_host" in data:
        set_setting(conn, "smtp_host", (data.get("smtp_host") or "").strip())
    if "smtp_port" in data:
        set_setting(conn, "smtp_port", str(data.get("smtp_port") or "587").strip())
    if "smtp_user" in data:
        set_setting(conn, "smtp_user", (data.get("smtp_user") or "").strip())
    if "smtp_pass" in data and data.get("smtp_pass"):
        set_setting(conn, "smtp_pass", data.get("smtp_pass").strip())
    if "smtp_from" in data:
        set_setting(conn, "smtp_from", (data.get("smtp_from") or "").strip())
    if "gemini_api_key" in data and data.get("gemini_api_key"):
        set_setting(conn, "gemini_api_key", data.get("gemini_api_key").strip())

    smtp_cfg = get_smtp_config(conn)
    conn.close()

    return jsonify({
        "success": True,
        "message": "Settings updated successfully.",
        "smtp_configured": smtp_cfg["is_configured"]
    })


@api_bp.route("/settings/test-email", methods=["POST"])
@api_auth_required()
def api_test_email():
    u = request.api_user
    data = request.get_json(silent=True) or {}
    target_email = data.get("email") or u["email"]

    res = send_test_smtp_email(target_email)
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code


# ---------------------------------------------------------------------------
# 5. Full Mobile / Client Platform Data Endpoints
# ---------------------------------------------------------------------------

@api_bp.route("/dashboard", methods=["GET"])
@api_auth_required()
def api_dashboard_data():
    u = request.api_user
    conn = get_db()
    summary = get_daily_activity_summary(conn, u["id"])
    balance = get_balance(conn, u["id"])
    badges = get_user_badges(conn, u["id"])
    earned_codes = {b["code"] for b in badges}

    # Last 7 days chart data
    today = date.today()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    chart_data = []
    for d in days:
        m = conn.execute(
            "SELECT COALESCE(SUM(minutes),0) m FROM activities WHERE user_id=? AND date(created_at)=?",
            (u["id"], d.isoformat()),
        ).fetchone()["m"]
        chart_data.append({"day": d.strftime("%a"), "date": d.isoformat(), "minutes": m})

    # Recent activities
    recent = conn.execute(
        "SELECT * FROM activities WHERE user_id=? ORDER BY id DESC LIMIT 5", (u["id"],)
    ).fetchall()

    team = None
    if u["team_id"]:
        team = dict(conn.execute("SELECT * FROM teams WHERE id=?", (u["team_id"],)).fetchone() or {})

    conn.close()

    tips = generate_daily_tips(summary)

    return jsonify({
        "success": True,
        "user": _user_dict(u),
        "balance": balance,
        "summary": summary,
        "tips": tips,
        "weekly_chart": chart_data,
        "recent_activities": [dict(r) for r in recent],
        "team": team,
        "badges": badges,
        "badge_stats": {
            "earned_count": len(badges),
            "total_available": len(BADGES)
        }
    })


@api_bp.route("/leaderboard", methods=["GET"])
@api_auth_required()
def api_leaderboard():
    view = request.args.get("view", "students")
    conn = get_db()
    if view == "teams":
        rows = conn.execute("""
            SELECT t.id, t.name, COUNT(DISTINCT u.id) members,
                   COALESCE(SUM(a.points),0) points
            FROM teams t
            LEFT JOIN users u ON u.team_id = t.id
            LEFT JOIN activities a ON a.user_id = u.id
            GROUP BY t.id ORDER BY points DESC, t.name
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT u.id, u.name, u.avatar, t.name as team_name,
                   COALESCE(SUM(a.points),0) points
            FROM users u
            LEFT JOIN activities a ON u.id = a.user_id
            LEFT JOIN teams t ON u.team_id = t.id
            WHERE u.role='student'
            GROUP BY u.id ORDER BY points DESC, u.name
        """).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "view": view,
        "rankings": [dict(r) for r in rows]
    })


@api_bp.route("/events", methods=["GET"])
@api_auth_required()
def api_events():
    u = request.api_user
    conn = get_db()
    events = conn.execute("SELECT * FROM events ORDER BY date").fetchall()
    registrations = {
        r["event_id"] for r in conn.execute(
            "SELECT event_id FROM event_registrations WHERE user_id=?", (u["id"],)
        ).fetchall()
    }
    conn.close()

    out = []
    for e in events:
        d = dict(e)
        d["is_registered"] = e["id"] in registrations
        out.append(d)

    return jsonify({
        "success": True,
        "events": out
    })


@api_bp.route("/events/<int:event_id>/register", methods=["POST"])
@api_auth_required("student")
def api_register_event(event_id):
    u = request.api_user
    conn = get_db()
    ev = conn.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not ev:
        conn.close()
        return jsonify({"error": "Event not found."}), 404

    try:
        conn.execute(
            "INSERT INTO event_registrations(user_id,event_id) VALUES(?,?)",
            (u["id"], event_id)
        )
        award_badge(conn, u["id"], "event_goer")
        conn.commit()
        conn.close()
        return jsonify({
            "success": True,
            "message": f"Successfully registered for {ev['name']}!"
        })
    except Exception:
        conn.close()
        return jsonify({"message": "You are already registered for this event."}), 200


@api_bp.route("/rewards", methods=["GET"])
@api_auth_required()
def api_rewards():
    u = request.api_user
    conn = get_db()
    catalog = conn.execute("SELECT * FROM rewards ORDER BY cost").fetchall()
    balance = get_balance(conn, u["id"])
    redemptions = conn.execute("""
        SELECT red.id, red.cost, red.status, red.redeemed_at, r.name, r.icon
        FROM redemptions red
        JOIN rewards r ON r.id = red.reward_id
        WHERE red.user_id = ?
        ORDER BY red.id DESC
    """, (u["id"],)).fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "balance": balance,
        "catalog": [dict(r) for r in catalog],
        "my_redemptions": [dict(r) for r in redemptions]
    })
