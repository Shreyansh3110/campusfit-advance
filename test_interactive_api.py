"""
CampusFit Automated Test Suite for Interactive API, AI Coach & Email Engine
"""

import sys
import json
import time
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app import app
from db import init_db, get_db

def run_tests():
    print("==================================================")
    print(" CampusFit Automated Test Suite: Interactive API ")
    print("==================================================")

    init_db()
    client = app.test_client()

    test_email = f"test_student_{int(time.time())}@campusfit.edu"
    test_password = "securePassword123"

    # 1. Test Registration via API
    print("\n[1] Testing POST /api/auth/register ...")
    reg_resp = client.post("/api/auth/register", json={
        "name": "Alex Rivera",
        "email": test_email,
        "password": test_password,
        "goal": "Weight Loss",
        "avatar": "🏃"
    })
    assert reg_resp.status_code == 201, f"Expected 201, got {reg_resp.status_code}: {reg_resp.get_data(as_text=True)}"
    reg_data = reg_resp.get_json()
    assert reg_data.get("success") is True
    token = reg_data.get("token")
    assert token and len(token) == 64, f"Invalid token format: {token}"
    print(f" -> Passed! User registered with Bearer token: {token[:12]}...")

    # 2. Test Login via API
    print("\n[2] Testing POST /api/auth/login ...")
    login_resp = client.post("/api/auth/login", json={
        "email": test_email,
        "password": test_password
    })
    assert login_resp.status_code == 200, f"Expected 200, got {login_resp.status_code}"
    login_data = login_resp.get_json()
    assert login_data.get("success") is True
    assert login_data["user"]["name"] == "Alex Rivera"
    print(" -> Passed! Login successful with valid credentials.")

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Test Profile with Bearer Auth
    print("\n[3] Testing GET /api/auth/me (Bearer Token Auth) ...")
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200, f"Expected 200, got {me_resp.status_code}"
    me_data = me_resp.get_json()
    assert me_data["user"]["email"] == test_email
    assert me_data["user"]["goal"] == "Weight Loss"
    print(f" -> Passed! Authenticated as {me_data['user']['name']} ({me_data['user']['goal']}).")

    # 4. Test Logging Activity via API
    print("\n[4] Testing POST /api/activities (Log Activity with Instant Coach Feedback) ...")
    act_resp = client.post("/api/activities", headers=headers, json={
        "activity": "Cycling",
        "minutes": 35
    })
    assert act_resp.status_code == 201, f"Expected 201, got {act_resp.status_code}"
    act_data = act_resp.get_json()
    assert act_data.get("success") is True
    assert act_data["points_earned"] == 70  # 35 * 2
    assert act_data["new_streak"] >= 1
    assert "coach_feedback" in act_data
    print(f" -> Passed! Logged 35m Cycling, earned +{act_data['points_earned']} points. Streak: {act_data['new_streak']} 🔥")
    print(f"    Coach feedback: \"{act_data['coach_feedback'][:80]}...\"")

    # 5. Test Daily Activity Summary
    print("\n[5] Testing GET /api/activities/daily-summary ...")
    sum_resp = client.get("/api/activities/daily-summary", headers=headers)
    assert sum_resp.status_code == 200
    sum_data = sum_resp.get_json()["summary"]
    assert sum_data["today_minutes"] >= 35
    assert sum_data["today_points"] >= 70
    assert len(sum_data["activities"]) >= 1
    print(f" -> Passed! Summary reports {sum_data['today_minutes']} mins today, weekly target {sum_data['weekly_target_minutes']}m ({sum_data['weekly_progress_pct']}%).")

    # 6. Test AI Coach Tips
    print("\n[6] Testing GET /api/coach/tips ...")
    tips_resp = client.get("/api/coach/tips", headers=headers)
    assert tips_resp.status_code == 200
    tips_data = tips_resp.get_json()["tips"]
    assert "workout_recommendation" in tips_data
    assert "nutrition_tip" in tips_data
    assert "streak_nudge" in tips_data
    print(f" -> Passed! Recommended workout: {tips_data['workout_recommendation']['title']} ({tips_data['workout_recommendation']['minutes']}m)")
    print(f"    Streak nudge: {tips_data['streak_nudge']}")

    # 7. Test Conversational AI Coach Chat with Natural Language Queries
    print("\n[7] Testing POST /api/coach/chat (Interactive Assistant) ...")
    queries = [
        "how to lose belly fat?",
        "what should I do today?",
        "what healthy food can I eat at the campus canteen?",
        "how many pushups for chest?"
    ]
    for q in queries:
        chat_resp = client.post("/api/coach/chat", headers=headers, json={"message": q})
        assert chat_resp.status_code == 200
        chat_data = chat_resp.get_json()
        assert chat_data.get("success") is True
        assert len(chat_data["reply"]) > 40
        print(f" -> Passed! Coach query: \"{q}\" -> {len(chat_data['reply'])} chars response.")

    # 8. Test Email Notification Engine
    print("\n[8] Testing POST /api/notifications/send-daily-digest ...")
    email_resp = client.post("/api/notifications/send-daily-digest", headers=headers, json={})
    assert email_resp.status_code == 200
    email_data = email_resp.get_json()
    assert email_data.get("success") is True
    assert email_data["recipient"] == test_email
    assert "preview_html" in email_data or email_data.get("status") == "delivered_via_smtp"
    print(f" -> Passed! Daily digest successfully generated ({email_data.get('status')}).")
    print(f"    Subject: {email_data.get('subject')}")

    # 9. Test Email Log History
    print("\n[9] Testing GET /api/notifications/history ...")
    hist_resp = client.get("/api/notifications/history", headers=headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.get_json()
    assert hist_data["count"] >= 1
    assert hist_data["notifications"][0]["recipient"] == test_email
    print(f" -> Passed! Found {hist_data['count']} notification log(s) for user.")

    # 10. Test Email Preview API
    print("\n[10] Testing GET /api/notifications/preview-latest ...")
    prev_resp = client.get("/api/notifications/preview-latest", headers=headers)
    assert prev_resp.status_code == 200
    prev_data = prev_resp.get_json()
    assert prev_data.get("success") is True
    assert "CampusFit" in prev_data["html"]
    print(" -> Passed! Latest email preview successfully retrieved with full HTML content.")

    # 11. Test Settings API (GET and POST)
    print("\n[11] Testing GET and POST /api/settings ...")
    set_resp = client.post("/api/settings", headers=headers, json={
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "demo@campusfit.com"
    })
    assert set_resp.status_code == 200
    get_set_resp = client.get("/api/settings", headers=headers)
    assert get_set_resp.status_code == 200
    cfg = get_set_resp.get_json()["smtp"]
    assert cfg["host"] == "smtp.gmail.com"
    assert cfg["user"] == "demo@campusfit.com"
    print(" -> Passed! App settings successfully saved and retrieved.")

    # 12. Test Mobile Dashboard Consolidated API
    print("\n[12] Testing GET /api/dashboard ...")
    dash_resp = client.get("/api/dashboard", headers=headers)
    assert dash_resp.status_code == 200
    dash_data = dash_resp.get_json()
    assert "weekly_chart" in dash_data
    assert "tips" in dash_data
    assert "badge_stats" in dash_data
    print(f" -> Passed! Mobile app dashboard consolidated payload verified.")

    # 13. Test Web Form CSRF Protection
    print("\n[13] Testing Web Form CSRF Protection ...")
    form_resp = client.post("/activity", data={"activity": "Running", "minutes": 20})
    assert form_resp.status_code == 400, "Web POST form without CSRF should be rejected with 400"
    print(" -> Passed! Standard web forms remain strictly CSRF-protected while /api/ endpoints are accessible to clients.")

    # 14. Test Web Student Dashboard Rendering
    print("\n[14] Testing Web Student Dashboard Rendering ...")
    with client.session_transaction() as sess:
        sess["uid"] = reg_data["user"]["id"]
        sess["role"] = "student"
        sess["name"] = reg_data["user"]["name"]
    dash_html_resp = client.get("/dashboard")
    assert dash_html_resp.status_code == 200, f"Dashboard failed with {dash_html_resp.status_code}"
    html = dash_html_resp.get_data(as_text=True)
    assert "AI Coach" in html
    assert "Email Me Today's Activity" in html
    assert "Preview Email" in html
    assert "Setup SMTP" in html
    print(" -> Passed! Student web dashboard with modals rendered successfully.")

    # 15. Test Web API Docs Page Rendering
    print("\n[15] Testing Web API Documentation Page ...")
    docs_resp = client.get("/api/docs")
    assert docs_resp.status_code == 200
    docs_html = docs_resp.get_data(as_text=True)
    assert "Live API Test Console" in docs_html
    print(" -> Passed! Interactive API documentation page rendered successfully.")

    print("\n==================================================")
    print(" ALL 15 TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
