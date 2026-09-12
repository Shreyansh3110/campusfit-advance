import psycopg2
import psycopg2.extras
import secrets
import os
from datetime import datetime, date, timedelta

DB = "campusfit.db"

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

class PostgresRowWrapper(dict):
    def __init__(self, d):
        super().__init__(d)
        self._vals = list(d.values())
    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return super().__getitem__(key)

class PostgresCursorWrapper:
    def __init__(self, cur):
        self.cur = cur
    def fetchone(self):
        row = self.cur.fetchone()
        return PostgresRowWrapper(row) if row else None
    def fetchall(self):
        return [PostgresRowWrapper(row) for row in self.cur.fetchall()]
    @property
    def lastrowid(self):
        return getattr(self.cur, '_last_id', None)
    def __iter__(self):
        for row in self.cur:
            yield PostgresRowWrapper(row)

class PostgresConnWrapper:
    def __init__(self, dsn):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True
    def execute(self, query, params=()):
        q = query.replace('?', '%s')
        is_insert = q.strip().upper().startswith('INSERT')
        if is_insert and 'RETURNING' not in q.upper():
            q += ' RETURNING id'
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(q, params)
        pw = PostgresCursorWrapper(cur)
        if is_insert:
            try:
                pw.cur._last_id = cur.fetchone()['id']
            except:
                pw.cur._last_id = None
        return pw
    def executemany(self, query, params_list):
        q = query.replace('?', '%s')
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.executemany(q, params_list)
        return PostgresCursorWrapper(cur)
    def commit(self):
        pass
    def close(self):
        self.conn.close()

def get_db():
    dsn = os.environ.get('DATABASE_URL')
    return PostgresConnWrapper(dsn)


# ---------------------------------------------------------------------------
# Badge catalogue (code -> metadata). Badges are awarded automatically.
# ---------------------------------------------------------------------------

BADGES = {
    "first_step":   {"name": "First Step",     "icon": "🥇", "desc": "Logged your first activity"},
    "century":      {"name": "Century Club",    "icon": "💯", "desc": "Earned 100+ total points"},
    "high_flyer":   {"name": "High Flyer",      "icon": "🚀", "desc": "Earned 500+ total points"},
    "hero":         {"name": "Fitness Hero",    "icon": "🦸", "desc": "Earned 1000+ total points"},
    "marathoner":   {"name": "Marathoner",      "icon": "🏃", "desc": "Logged 500+ total minutes"},
    "streak_3":     {"name": "Warming Up",      "icon": "🔥", "desc": "3-day activity streak"},
    "streak_7":     {"name": "On Fire",         "icon": "🔥", "desc": "7-day activity streak"},
    "streak_30":    {"name": "Unstoppable",     "icon": "🔥", "desc": "30-day activity streak"},
    "social":       {"name": "Squad Up",        "icon": "🤝", "desc": "Joined or created a team"},
    "friendly":     {"name": "Friendly Face",   "icon": "🧑‍🤝‍🧑", "desc": "Added your first friend"},
    "event_goer":   {"name": "Event Goer",      "icon": "📅", "desc": "Registered for a campus event"},
    "challenger":   {"name": "Challenger",      "icon": "⚔️", "desc": "Joined a team challenge"},
}


# ---------------------------------------------------------------------------
# Schema + seed
# ---------------------------------------------------------------------------

def init_db():
    c = get_db()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        goal TEXT DEFAULT 'Not set',
        role TEXT DEFAULT 'student',
        avatar TEXT DEFAULT '🙂',
        streak INTEGER DEFAULT 0,
        last_log_date TEXT,
        team_id INTEGER,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS activities(
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        activity TEXT,
        minutes INTEGER,
        points INTEGER,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS events(
        id SERIAL PRIMARY KEY,
        name TEXT, description TEXT, date TEXT, points INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS event_registrations(
        id SERIAL PRIMARY KEY,
        user_id INTEGER, event_id INTEGER, UNIQUE(user_id, event_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS teams(
        id SERIAL PRIMARY KEY,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        created_by INTEGER,
        created_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS friendships(
        id SERIAL PRIMARY KEY,
        user_id INTEGER, friend_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        UNIQUE(user_id, friend_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS challenges(
        id SERIAL PRIMARY KEY,
        name TEXT, description TEXT,
        start_date TEXT, end_date TEXT,
        target_points INTEGER,
        created_by INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS challenge_teams(
        id SERIAL PRIMARY KEY,
        challenge_id INTEGER, team_id INTEGER,
        UNIQUE(challenge_id, team_id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS user_badges(
        id SERIAL PRIMARY KEY,
        user_id INTEGER, badge_code TEXT,
        earned_at TEXT,
        UNIQUE(user_id, badge_code)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS rewards(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        cost INTEGER NOT NULL,
        icon TEXT DEFAULT '🎁',
        stock INTEGER DEFAULT -1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS redemptions(
        id SERIAL PRIMARY KEY,
        user_id INTEGER, reward_id INTEGER, cost INTEGER,
        status TEXT DEFAULT 'pending',
        redeemed_at TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS api_tokens(
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        token TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS email_logs(
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body_html TEXT,
        status TEXT DEFAULT 'sent',
        sent_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS coach_messages(
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        sender TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS app_settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    # Seed admin
    admin = c.execute("SELECT id FROM users WHERE email=?", ("admin@campusfit.com",)).fetchone()
    if not admin:
        from werkzeug.security import generate_password_hash
        c.execute("""INSERT INTO users(name,email,password,goal,role,avatar,created_at)
                     VALUES(?,?,?,?,?,?,?)""",
                  ("CampusFit Admin", "admin@campusfit.com",
                   generate_password_hash("admin123"), "Admin", "admin", "🛠️",
                   datetime.now().isoformat(timespec="minutes")))

    # Seed events
    if c.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
        c.executemany("""INSERT INTO events(name,description,date,points)
                         VALUES(?,?,?,?)""", [
            ("Campus 5K", "Complete a 5 km run or walk.", "2026-09-20", 150),
            ("7-Day Walking Challenge", "Walk at least 20 minutes every day.", "2026-09-25", 100),
            ("Active Weekend", "Complete 60 minutes of activity.", "2026-09-28", 80),
        ])

    # Seed rewards
    if c.execute("SELECT COUNT(*) FROM rewards").fetchone()[0] == 0:
        c.executemany("""INSERT INTO rewards(name,description,cost,icon,stock)
                         VALUES(?,?,?,?,?)""", [
            ("Protein Shake Voucher", "Redeem at the campus canteen counter.", 120, "🥤", -1),
            ("CampusFit T-Shirt", "Official CampusFit training tee, any size.", 400, "👕", 30),
            ("Gym Day Pass", "One free day at the campus gym.", 250, "🏋️", 50),
            ("Priority Locker", "One semester of a reserved locker.", 350, "🔐", 20),
            ("₹100 Campus Store Voucher", "Redeemable at the campus store.", 600, "🎟️", 15),
            ("Reserved Court Slot", "One-hour priority booking on the sports court.", 180, "🏸", -1),
        ])

    c.commit()
    c.close()


# ---------------------------------------------------------------------------
# Rewards / points balance
# ---------------------------------------------------------------------------

def get_balance(conn, user_id):
    """Spendable points = lifetime earned points minus points spent on non-cancelled redemptions."""
    earned = conn.execute(
        "SELECT COALESCE(SUM(points),0) p FROM activities WHERE user_id=?", (user_id,)
    ).fetchone()["p"]
    spent = conn.execute(
        "SELECT COALESCE(SUM(cost),0) s FROM redemptions WHERE user_id=? AND status!='cancelled'",
        (user_id,),
    ).fetchone()["s"]
    return earned - spent


# ---------------------------------------------------------------------------
# Streak logic
# ---------------------------------------------------------------------------

def update_streak(conn, user_id):
    """Call right after a new activity is logged for user_id. Returns new streak count."""
    u = conn.execute("SELECT streak, last_log_date FROM users WHERE id=?", (user_id,)).fetchone()
    today = date.today()
    last = date.fromisoformat(u["last_log_date"]) if u["last_log_date"] else None
    if last == today:
        new_streak = u["streak"] or 1
    elif last == today - timedelta(days=1):
        new_streak = (u["streak"] or 0) + 1
    else:
        new_streak = 1
    conn.execute("UPDATE users SET streak=?, last_log_date=? WHERE id=?",
                 (new_streak, today.isoformat(), user_id))
    return new_streak


# ---------------------------------------------------------------------------
# Badge award logic
# ---------------------------------------------------------------------------

def award_badge(conn, user_id, code):
    try:
        conn.execute("INSERT INTO user_badges(user_id, badge_code, earned_at) VALUES(?,?,?)",
                     (user_id, code, datetime.now().isoformat(timespec="minutes")))
        return True
    except psycopg2.IntegrityError:
        return False  # already earned


def check_and_award_badges(conn, user_id):
    """Run after activity log / streak update / social actions. Returns list of newly earned badge codes."""
    newly = []
    stats = conn.execute("""SELECT COALESCE(SUM(points),0) points, COALESCE(SUM(minutes),0) minutes,
                            COUNT(*) n FROM activities WHERE user_id=?""", (user_id,)).fetchone()
    streak = conn.execute("SELECT streak FROM users WHERE id=?", (user_id,)).fetchone()["streak"] or 0

    def maybe(code, condition):
        if condition and award_badge(conn, user_id, code):
            newly.append(code)

    maybe("first_step", stats["n"] >= 1)
    maybe("century", stats["points"] >= 100)
    maybe("high_flyer", stats["points"] >= 500)
    maybe("hero", stats["points"] >= 1000)
    maybe("marathoner", stats["minutes"] >= 500)
    maybe("streak_3", streak >= 3)
    maybe("streak_7", streak >= 7)
    maybe("streak_30", streak >= 30)

    conn.commit()
    return newly


def get_user_badges(conn, user_id):
    rows = conn.execute("SELECT badge_code, earned_at FROM user_badges WHERE user_id=? ORDER BY earned_at",
                         (user_id,)).fetchall()
    out = []
    for r in rows:
        meta = BADGES.get(r["badge_code"])
        if meta:
            out.append({**meta, "code": r["badge_code"], "earned_at": r["earned_at"]})
    return out


# ---------------------------------------------------------------------------
# API Token Helpers
# ---------------------------------------------------------------------------

def generate_api_token(conn, user_id, expires_days=30):
    """Generate and store a new secure Bearer token for client/mobile app authentication."""
    token = secrets.token_hex(32)
    now = datetime.now()
    expires_at = (now + timedelta(days=expires_days)).isoformat(timespec="minutes")
    conn.execute(
        "INSERT INTO api_tokens(user_id, token, created_at, expires_at) VALUES(?,?,?,?)",
        (user_id, token, now.isoformat(timespec="minutes"), expires_at),
    )
    conn.commit()
    return token, expires_at


def verify_api_token(conn, token):
    """Validate Bearer token and return associated user row, or None if invalid/expired."""
    if not token:
        return None
    row = conn.execute("""
        SELECT u.*, t.expires_at FROM api_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token = ?
    """, (token,)).fetchone()
    if not row:
        return None
    if row["expires_at"] and row["expires_at"] < datetime.now().isoformat():
        return None
    return row


# ---------------------------------------------------------------------------
# Daily Activity Summary & Analytics
# ---------------------------------------------------------------------------

def get_daily_activity_summary(conn, user_id, target_date=None):
    """Fetch daily activity breakdown, weekly totals, and goal completion for a user."""
    today = target_date or date.today().isoformat()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        return None

    # Today's activities
    today_rows = conn.execute(
        "SELECT * FROM activities WHERE user_id=? AND date(created_at)=? ORDER BY id DESC",
        (user_id, today)
    ).fetchall()

    today_minutes = sum(r["minutes"] for r in today_rows)
    today_points = sum(r["points"] for r in today_rows)
    activities_list = [{"id": r["id"], "activity": r["activity"], "minutes": r["minutes"], "points": r["points"], "created_at": r["created_at"]} for r in today_rows]

    # Last 7 days
    target_d = date.fromisoformat(today)
    week_start = (target_d - timedelta(days=6)).isoformat()
    week_rows = conn.execute(
        "SELECT COALESCE(SUM(minutes),0) m, COALESCE(SUM(points),0) p FROM activities WHERE user_id=? AND date(created_at) >= ? AND date(created_at) <= ?",
        (user_id, week_start, today)
    ).fetchone()

    total_lifetime = conn.execute(
        "SELECT COALESCE(SUM(points),0) p, COALESCE(SUM(minutes),0) m FROM activities WHERE user_id=?",
        (user_id,)
    ).fetchone()

    weekly_target = 240
    weekly_pct = min(100, round((week_rows["m"] / weekly_target) * 100)) if week_rows["m"] else 0

    return {
        "date": today,
        "user_id": user["id"],
        "user_name": user["name"],
        "user_email": user["email"],
        "goal": user["goal"] or "General Fitness",
        "streak": user["streak"] or 0,
        "today_minutes": today_minutes,
        "today_points": today_points,
        "today_activity_count": len(today_rows),
        "activities": activities_list,
        "weekly_minutes": week_rows["m"],
        "weekly_points": week_rows["p"],
        "weekly_target_minutes": weekly_target,
        "weekly_progress_pct": weekly_pct,
        "lifetime_points": total_lifetime["p"],
        "lifetime_minutes": total_lifetime["m"],
    }


# ---------------------------------------------------------------------------
# Email Logging & Audit
# ---------------------------------------------------------------------------

def log_email(conn, user_id, recipient, subject, body_html, status="sent"):
    """Record an email dispatch into email_logs."""
    conn.execute(
        "INSERT INTO email_logs(user_id, recipient, subject, body_html, status, sent_at) VALUES(?,?,?,?,?,?)",
        (user_id, recipient, subject, body_html, status, datetime.now().isoformat(timespec="minutes"))
    )
    conn.commit()


def get_email_logs(conn, user_id, limit=20):
    """Retrieve recent sent emails for a user."""
    rows = conn.execute(
        "SELECT id, recipient, subject, status, sent_at FROM email_logs WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Coach Interaction History
# ---------------------------------------------------------------------------

def save_coach_message(conn, user_id, sender, message):
    """Save user or coach message into coach_messages table."""
    conn.execute(
        "INSERT INTO coach_messages(user_id, sender, message, created_at) VALUES(?,?,?,?)",
        (user_id, sender, message, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()


def get_coach_history(conn, user_id, limit=15):
    """Retrieve recent coach conversation history."""
    rows = conn.execute(
        "SELECT sender, message, created_at FROM coach_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    history = [dict(r) for r in rows]
    history.reverse()
    return history


# ---------------------------------------------------------------------------
# App Settings (SMTP & Gemini Configuration)
# ---------------------------------------------------------------------------

def get_setting(conn, key, default=None):
    row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row and row["value"] is not None else default


def set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO app_settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
    conn.commit()


def get_all_settings(conn):
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}
