"""
CampusFit Email Notification & Messaging Service
Generates responsive HTML daily digests with activity stats and coach tips,
and dispatches them via SMTP or safe database simulation logging.
Supports settings configured via .env or the in-app settings database.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

from db import get_db, log_email, get_daily_activity_summary, get_setting
from coach_service import generate_daily_tips


def render_daily_digest_html(user_summary, tips, app_url="http://127.0.0.1:8000"):
    """
    Renders an email-client-compatible, responsive HTML template
    containing daily activity stats, milestones, and personalized AI tips.
    """
    user_name = user_summary.get("user_name", "Student")
    streak = user_summary.get("streak", 0)
    today_min = user_summary.get("today_minutes", 0)
    today_pts = user_summary.get("today_points", 0)
    weekly_min = user_summary.get("weekly_minutes", 0)
    weekly_target = user_summary.get("weekly_target_minutes", 240)
    weekly_pct = user_summary.get("weekly_progress_pct", 0)
    goal = user_summary.get("goal", "General Fitness")
    activities = user_summary.get("activities", [])

    # Format activities list
    if activities:
        act_rows = ""
        for a in activities:
            act_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 8px; font-weight: 600; color: #1e293b;">{a.get('activity')}</td>
                <td style="padding: 10px 8px; color: #475569;">{a.get('minutes')} mins</td>
                <td style="padding: 10px 8px; color: #16a34a; font-weight: 600;">+{a.get('points')} pts</td>
            </tr>
            """
    else:
        act_rows = """
        <tr>
            <td colspan="3" style="padding: 16px; text-align: center; color: #64748b; font-style: italic;">
                No activities logged today yet. Take a brisk walk or do a quick dorm workout!
            </td>
        </tr>
        """

    workout = tips.get("workout_recommendation", {})
    workout_title = workout.get("title", "Campus Cardio & Core")
    workout_desc = workout.get("desc", "20-minute bodyweight circuit.")
    workout_min = workout.get("minutes", 20)
    workout_intensity = workout.get("intensity", "Moderate")

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CampusFit Daily Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f1f5f9; padding: 30px 15px;">
  <tr>
    <td align="center">
      <table role="presentation" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06);">
        
        <!-- HEADER -->
        <tr>
          <td style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 32px 28px; text-align: center; color: #ffffff;">
            <div style="font-size: 28px; font-weight: 800; letter-spacing: -0.5px;">🏃 CampusFit</div>
            <div style="font-size: 14px; opacity: 0.9; margin-top: 6px; font-weight: 500;">Your Daily Activity &amp; Wellness Report</div>
          </td>
        </tr>

        <!-- GREETING & STREAK -->
        <tr>
          <td style="padding: 28px 28px 12px 28px;">
            <h2 style="margin: 0 0 8px 0; color: #0f172a; font-size: 22px;">Hi {user_name} 👋</h2>
            <p style="margin: 0; color: #475569; font-size: 15px; line-height: 1.5;">
              Here is your daily fitness summary for <strong>{date.today().strftime('%A, %b %d, %Y')}</strong>. 
              Keep pushing toward your target of <strong>{goal}</strong>!
            </p>
          </td>
        </tr>

        <!-- STATS GRID -->
        <tr>
          <td style="padding: 12px 24px;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
              <tr>
                <td width="25%" style="padding: 6px;">
                  <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 8px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #059669;">{today_min}m</div>
                    <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-top: 4px;">Today Mins</div>
                  </div>
                </td>
                <td width="25%" style="padding: 6px;">
                  <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 8px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #eab308;">+{today_pts}</div>
                    <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-top: 4px;">Points</div>
                  </div>
                </td>
                <td width="25%" style="padding: 6px;">
                  <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 8px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #ef4444;">{streak} 🔥</div>
                    <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-top: 4px;">Day Streak</div>
                  </div>
                </td>
                <td width="25%" style="padding: 6px;">
                  <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 8px; text-align: center;">
                    <div style="font-size: 22px; font-weight: 800; color: #3b82f6;">{weekly_pct}%</div>
                    <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; margin-top: 4px;">Week Goal</div>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- STREAK BANNER -->
        <tr>
          <td style="padding: 6px 28px;">
            <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; border-radius: 8px; padding: 12px 16px; font-size: 13.5px; color: #065f46; font-weight: 500;">
              {tips.get('streak_nudge')}
            </div>
          </td>
        </tr>

        <!-- TODAY'S ACTIVITIES TABLE -->
        <tr>
          <td style="padding: 20px 28px 10px 28px;">
            <h3 style="margin: 0 0 12px 0; color: #0f172a; font-size: 17px;">📋 Today's Logged Activities</h3>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse: collapse; font-size: 14px;">
              <thead>
                <tr style="border-bottom: 2px solid #cbd5e1; text-align: left;">
                  <th style="padding: 8px; color: #64748b; font-weight: 600;">Activity</th>
                  <th style="padding: 8px; color: #64748b; font-weight: 600;">Duration</th>
                  <th style="padding: 8px; color: #64748b; font-weight: 600;">Points</th>
                </tr>
              </thead>
              <tbody>
                {act_rows}
              </tbody>
            </table>
          </td>
        </tr>

        <!-- AI COACH WORKOUT TIP -->
        <tr>
          <td style="padding: 16px 28px;">
            <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 12px; padding: 18px;">
              <div style="display: flex; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 18px; margin-right: 6px;">💡</span>
                <strong style="color: #166534; font-size: 15px;">Today's Recommended Workout ({workout_min}m • {workout_intensity})</strong>
              </div>
              <div style="font-weight: 700; color: #0f172a; font-size: 16px; margin-bottom: 4px;">{workout_title}</div>
              <p style="margin: 0; color: #334155; font-size: 14px; line-height: 1.5;">{workout_desc}</p>
            </div>
          </td>
        </tr>

        <!-- NUTRITION & RECOVERY CARDS -->
        <tr>
          <td style="padding: 6px 28px 20px 28px;">
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; margin-bottom: 12px;">
              <div style="font-weight: 700; color: #0f172a; font-size: 14px; margin-bottom: 4px;">🥗 Nutrition &amp; Fuel Tip</div>
              <div style="color: #475569; font-size: 13.5px; line-height: 1.5;">{tips.get('nutrition_tip')}</div>
            </div>
            <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px;">
              <div style="font-weight: 700; color: #0f172a; font-size: 14px; margin-bottom: 4px;">😴 Recovery &amp; Mobility Tip</div>
              <div style="color: #475569; font-size: 13.5px; line-height: 1.5;">{tips.get('recovery_tip')}</div>
            </div>
          </td>
        </tr>

        <!-- CTA BUTTON -->
        <tr>
          <td style="padding: 10px 28px 32px 28px; text-align: center;">
            <a href="{app_url}/activity" target="_blank" style="display: inline-block; background-color: #10b981; color: #ffffff; text-decoration: none; font-weight: 700; font-size: 15px; padding: 14px 32px; border-radius: 10px; box-shadow: 0 3px 10px rgba(16,185,129,0.35);">
              🚀 Open CampusFit &amp; Log Activity
            </a>
          </td>
        </tr>

        <!-- FOOTER -->
        <tr>
          <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px 28px; text-align: center; color: #94a3b8; font-size: 12px;">
            CampusFit • SIH 2026 Problem Statement SIH26196 • Team 93 (team zero)<br>
            Sent automatically to help you stay fit, active, and motivated on campus.
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>
    """
    return html


# ---------------------------------------------------------------------------
# SMTP Credentials Loader
# ---------------------------------------------------------------------------

def get_smtp_config(conn=None):
    """Retrieve SMTP settings from environment or database."""
    close_at_end = False
    if conn is None:
        conn = get_db()
        close_at_end = True

    host = os.environ.get("SMTP_HOST") or get_setting(conn, "smtp_host", "")
    port_str = os.environ.get("SMTP_PORT") or get_setting(conn, "smtp_port", "587")
    user = os.environ.get("SMTP_USER") or get_setting(conn, "smtp_user", "")
    password = os.environ.get("SMTP_PASS") or get_setting(conn, "smtp_pass", "")
    from_addr = os.environ.get("SMTP_FROM") or get_setting(conn, "smtp_from", user or "notifications@campusfit.com")

    if close_at_end:
        conn.close()

    try:
        port = int(port_str)
    except ValueError:
        port = 587

    return {
        "host": host.strip() if host else "",
        "port": port,
        "user": user.strip() if user else "",
        "pass": password.strip() if password else "",
        "from": from_addr.strip() if from_addr else "",
        "is_configured": bool(host and user and password)
    }


# ---------------------------------------------------------------------------
# Email Dispatcher
# ---------------------------------------------------------------------------

def send_daily_digest_email(user_id, recipient_email=None):
    """
    Prepares and dispatches the daily activity digest for the given user_id.
    Uses SMTP if credentials are set, or records to email_logs in demo/simulation mode.
    """
    conn = get_db()
    summary = get_daily_activity_summary(conn, user_id)
    if not summary:
        conn.close()
        return {"success": False, "error": "User summary not found"}

    target_email = recipient_email or summary["user_email"]
    tips = generate_daily_tips(summary)
    html_content = render_daily_digest_html(summary, tips)

    subject = f"🏃 CampusFit Daily Activity & Tips – {date.today().strftime('%b %d')}"
    smtp_cfg = get_smtp_config(conn)

    if smtp_cfg["is_configured"]:
        # Real SMTP dispatch
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"CampusFit <{smtp_cfg['from']}>"
            msg["To"] = target_email
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=12) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_cfg["user"], smtp_cfg["pass"])
                server.sendmail(smtp_cfg["from"], [target_email], msg.as_string())

            log_email(conn, user_id, target_email, subject, html_content, status="delivered_smtp")
            conn.close()
            return {
                "success": True,
                "status": "delivered_via_smtp",
                "is_smtp": True,
                "message": f"Successfully delivered directly to your inbox at {target_email}!",
                "recipient": target_email,
                "subject": subject,
                "summary": summary,
                "preview_html": html_content
            }
        except Exception as e:
            err_msg = str(e)
            log_email(conn, user_id, target_email, subject, html_content, status=f"failed: {err_msg[:60]}")
            conn.close()
            return {
                "success": False,
                "is_smtp": True,
                "error": f"SMTP delivery error: {err_msg}. Please verify your SMTP Host, Username, and App Password.",
                "status": "failed",
                "preview_html": html_content
            }
    else:
        # Simulated dispatch (safe demo mode — logs preview to database)
        log_email(conn, user_id, target_email, subject, html_content, status="simulated_preview")
        conn.close()
        return {
            "success": True,
            "status": "simulated_preview",
            "is_smtp": False,
            "message": f"Email report generated! Since live SMTP credentials are not configured yet, it was saved to preview. Click 'Configure SMTP' to deliver to your real inbox, or 'View Preview' to inspect it now.",
            "recipient": target_email,
            "subject": subject,
            "today_minutes": summary["today_minutes"],
            "streak": summary["streak"],
            "preview_html": html_content
        }


def send_test_smtp_email(target_email):
    """Send a quick test email to verify SMTP configuration."""
    conn = get_db()
    smtp_cfg = get_smtp_config(conn)
    conn.close()

    if not smtp_cfg["is_configured"]:
        return {
            "success": False,
            "error": "SMTP credentials are missing. Please enter your SMTP Host, Username, and Password."
        }

    subject = "🏃 CampusFit SMTP Test Connection"
    html = f"""
    <div style="font-family: sans-serif; padding: 20px; color: #1e293b;">
        <h2 style="color: #10b981;">✅ SMTP Test Successful!</h2>
        <p>Your CampusFit email service is properly connected to <strong>{smtp_cfg['host']}</strong>.</p>
        <p>Daily fitness digests and activity tips will now be delivered directly to your inbox (<strong>{target_email}</strong>).</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <small style="color: #64748b;">CampusFit • Smart India Hackathon 2026</small>
    </div>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"CampusFit <{smtp_cfg['from']}>"
        msg["To"] = target_email
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=12) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_cfg["user"], smtp_cfg["pass"])
            server.sendmail(smtp_cfg["from"], [target_email], msg.as_string())

        return {
            "success": True,
            "message": f"Test email successfully sent to {target_email}! Check your inbox."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"SMTP Connection Failed: {str(e)}"
        }
