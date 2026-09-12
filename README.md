# CampusFit – Campus Fitness League

**Smart India Hackathon 2026**

- Problem Statement ID: **SIH26196**
- Category: **Software**
- Theme: **Fitness & Sports**
- Team ID: **93**
- Team Name: **team zero**

## About
CampusFit is a campus fitness web app that encourages students to stay active through
activity logging, points, streaks, badges, teams, friends, campus-wide challenges,
a leaderboard, and campus events. An admin dashboard manages users, events, activities,
and challenges.

## What's New in This Version
- **Interactive RESTful API (`/api/*`)** — Full token- and session-authenticated REST API
  enabling mobile apps, web clients, and third-party services to authenticate, track activities,
  retrieve daily summaries, query leaderboards, and interact with the AI coach.
- **AI Fitness Coach Engine (`coach_service.py`)** — Context-aware AI coach assistant
  that inspects the student's actual daily activities, active streak, and personal goals
  (Weight Loss, Muscle Gain, Cardio, etc.) to give customized workout plans, canteen nutrition
  advice, and recovery guidance. Supports Google Gemini API with smart deterministic fallback.
- **Daily Activity & Coach Tips Email Engine (`email_service.py`)** — Automatically generates
  and dispatches responsive HTML daily digests directly to the student's email with their
  activity recap, streak counters, and daily coach tips. Supports SMTP and zero-crash simulation logging.
- **Floating Interactive AI Coach Drawer** — A live on-site chat drawer on the website allowing
  students to chat with their AI Coach in real-time with quick-action prompt chips.
- **Interactive API Documentation & Playground (`/api/docs`)** — Built-in test console to execute
  live requests against any endpoint right in the browser.
- **Security & CSRF Exemptions** — Modern CSRF protection for HTML forms with clean API exemption
  for Bearer token and JSON clients.

## Features
- Student registration and login (hashed passwords)
- Fitness goal + avatar selection
- Activity logging with points and streaks
- Automatic badge awards
- Fitness level display
- Campus leaderboard (students and teams)
- Teams: create, join, leave, team leaderboard
- Friends: add by email, accept requests, friend activity feed
- Campus events + registration
- Team challenges with progress tracking
- Admin dashboard: manage users, events, activities, and challenges
- SQLite database
- Dark mode + mobile-responsive layout

## Technology Stack
- Python 3 / Flask 3
- SQLite
- Jinja2 templates, vanilla CSS/JS
- Chart.js (via CDN) for the activity chart

## How to Run

### 1. Install Python
Python 3.10+ is recommended.

### 2. Open a terminal in this project folder

```bash
cd CampusFit-SIH2026
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Start the application

```bash
python app.py
```

### 5. Open in browser

http://127.0.0.1:8000

The SQLite database (`campusfit.db`) is created automatically on first run.

## Admin Demo Login
- Email: `admin@campusfit.com`
- Password: `admin123`

## Student Demo
Click **Register** on the login page to create a student account, then explore
**Teams**, **Friends**, and **Challenges** from the nav bar.

## Project Structure

```text
CampusFit-SIH2026/
├── app.py                     # Flask app, web routes, CSRF protect, dashboard
├── api.py                     # Interactive RESTful API (/api/*) & Bearer auth
├── coach_service.py           # Context-aware AI coach & daily tips engine
├── email_service.py           # Responsive HTML daily activity digest & email sender
├── db.py                      # SQLite schema, seed data, streaks, badges, tokens, logs
├── test_interactive_api.py    # Automated test suite (13 comprehensive tests)
├── requirements.txt
├── README.md
├── static/
│   ├── style.css              # theme variables, responsive layout, AI coach & API styles
│   └── app.js                 # theme toggle, mobile nav, chart, AI coach drawer & email JS
└── templates/
    ├── base.html              # base layout with floating AI coach widget & API link
    ├── dashboard.html         # student dashboard with AI coach card & email trigger
    ├── api_docs.html          # interactive API documentation & live testing console
    ├── login.html / register.html
    ├── activity.html / leaderboard.html / events.html / add_event.html
    ├── teams.html / friends.html / challenges.html / rewards.html
    └── admin.html / admin_users.html / admin_events.html
        / admin_activities.html / admin_challenges.html / admin_rewards.html
```

## Environment Variables (Optional)

| Variable | Description | Default |
| --- | --- | --- |
| `CAMPUSFIT_SECRET` | Secret key for Flask session security | Auto-generated per process |
| `GEMINI_API_KEY` | Google Gemini API key for advanced conversational coaching | Uses smart rule-based engine if absent |
| `SMTP_HOST` | Outgoing SMTP server (e.g. `smtp.gmail.com`) | Simulated database logger if absent |
| `SMTP_PORT` | SMTP port (e.g. `587`) | `587` |
| `SMTP_USER` | SMTP username / email address | Optional |
| `SMTP_PASS` | SMTP password / app password | Optional |

## Running Automated Tests

Run the test suite covering authentication, API tokens, activity tracking, instant coach feedback, email digest dispatch, and CSRF protection:

```bash
python test_interactive_api.py
```
