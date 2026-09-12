"""
CampusFit Smart AI Coach Service
Provides interactive fitness coaching, personalized daily activity insights,
workout recommendations, and conversational responses.
Supports Google Gemini API when configured (via env or settings DB),
with an extensive built-in conversational AI fitness engine.
"""

import os
import json
import random
import urllib.request
import urllib.error

from db import get_db, get_setting

# ---------------------------------------------------------------------------
# Fitness Knowledge Base for Campus Students
# ---------------------------------------------------------------------------

GOAL_WORKOUTS = {
    "weight loss": [
        {"title": "Campus Stair Climber", "desc": "Find a 3-4 flight building on campus. Walk up at a brisk pace, jog down. Repeat 6-8 times.", "minutes": 25, "intensity": "High"},
        {"title": "Dorm HIIT Circuit", "desc": "4 rounds: 40s jumping jacks, 20s rest, 40s mountain climbers, 20s rest, 40s high knees, 60s rest.", "minutes": 20, "intensity": "High"},
        {"title": "Brisk Campus Perimeter Walk", "desc": "Take a 35-minute power walk around campus sports grounds or campus ring road.", "minutes": 35, "intensity": "Moderate"},
        {"title": "Bodyweight Tabata", "desc": "8 rounds of 20s burpees / 10s rest, followed by 8 rounds of squats.", "minutes": 15, "intensity": "Very High"}
    ],
    "muscle gain": [
        {"title": "Dorm Calisthenics Strength", "desc": "4 sets of 15 push-ups, 4 sets of 20 bodyweight squats, 3 sets of 45s wall sit, 3 sets of 15 chair dips.", "minutes": 30, "intensity": "Moderate-High"},
        {"title": "Campus Open Gym Push Day", "desc": "Chest press, overhead dumbbell press, push-ups, and tricep cable pushdowns.", "minutes": 45, "intensity": "High"},
        {"title": "Pull & Core Workout", "desc": "Pull-ups at campus outdoor bar (or resistance bands), inverted rows, plank hold 3x60s, leg raises 3x15.", "minutes": 35, "intensity": "High"},
        {"title": "Lower Body Power", "desc": "Walking lunges across hostel corridor (3x20 steps), Bulgarian split squats with chair, calf raises.", "minutes": 30, "intensity": "High"}
    ],
    "cardio": [
        {"title": "Campus 4K Interval Run", "desc": "5 min warm-up jog, 6x200m sprints with 60s walking recovery, 5 min cool-down.", "minutes": 30, "intensity": "High"},
        {"title": "Campus Cycling Tour", "desc": "Cycle through campus trails and nearby parks at a steady cadence of 80-90 RPM.", "minutes": 40, "intensity": "Moderate"},
        {"title": "Jump Rope & Agility Drills", "desc": "3 min jump rope, 1 min rest, 5 rounds. Mix with side-to-side shuffle hops.", "minutes": 25, "intensity": "High"}
    ],
    "general": [
        {"title": "Total Body Mobility & Flow", "desc": "Cat-cow stretches, downward dog transitions, deep squat holds, and thoracic rotations.", "minutes": 20, "intensity": "Low-Moderate"},
        {"title": "Campus Lunchtime Power Walk", "desc": "Step away from screens for a 20-minute power walk with a batchmate.", "minutes": 20, "intensity": "Moderate"},
        {"title": "Quick Core & Posture Reset", "desc": "Plank, bird-dog, glute bridges, and dead-bugs. Fixes hunching from long study hours.", "minutes": 15, "intensity": "Moderate"}
    ]
}

NUTRITION_TIPS = [
    "💧 **Hydration Goal**: Aim for at least 2.5–3 Liters of water today. Keep a refillable bottle during lectures.",
    "🥗 **Canteen Hack**: Choose boiled eggs, lentils (dal), sprouts, or grilled paneer over deep-fried snacks for sustained energy.",
    "🍎 **Pre-Workout Fuel**: Eat a banana or a handful of roasted peanuts 30 minutes before your workout for instant glycogen.",
    "🥛 **Post-Workout Recovery**: Consume a protein source within 45 minutes after exercise to repair muscle fibers and reduce soreness.",
    "🌙 **Late-Night Study Snack**: Swap instant ramen for mixed nuts, fruit, or roasted chana to prevent energy crashes."
]

RECOVERY_TIPS = [
    "😴 **Sleep Target**: Deep tissue repair peaks during Stage 3 sleep. Aim for 7–8 hours, especially after high-intensity days.",
    "🧘 **Desk Mobility**: Every 60 minutes of studying, stand up and perform 10 shoulder rolls and 5 torso twists.",
    "🚶 **Active Recovery**: If your muscles feel sore from yesterday, take a light 15-minute stroll instead of staying stationary.",
    "🧊 **Cool Down Routine**: Spend 5 minutes stretching major muscle groups (hamstrings, quads, chest) right after logging your workout."
]


# ---------------------------------------------------------------------------
# Structured Daily Tips Generator
# ---------------------------------------------------------------------------

def generate_daily_tips(user_summary):
    """
    Generates tailored tips based on the user's logged activity today,
    current streak status, and selected fitness goal.
    """
    goal_key = "general"
    goal_str = (user_summary.get("goal") or "").lower()
    if "weight" in goal_str or "fat" in goal_str or "loss" in goal_str:
        goal_key = "weight loss"
    elif "muscle" in goal_str or "bulk" in goal_str or "strength" in goal_str:
        goal_key = "muscle gain"
    elif "cardio" in goal_str or "run" in goal_str or "endurance" in goal_str:
        goal_key = "cardio"

    workouts = GOAL_WORKOUTS.get(goal_key, GOAL_WORKOUTS["general"])
    workout_pick = random.choice(workouts)
    nutrition_pick = random.choice(NUTRITION_TIPS)
    recovery_pick = random.choice(RECOVERY_TIPS)

    today_minutes = user_summary.get("today_minutes", 0)
    streak = user_summary.get("streak", 0)

    # Contextual streak nudge
    if today_minutes > 0:
        streak_nudge = f"🔥 Excellent work! You logged {today_minutes} mins today. Your streak is safe at {streak} day(s)!"
    elif streak > 0:
        streak_nudge = f"⚠️ Don't lose your {streak}-day streak! Log at least 15 minutes of movement today to keep the flame burning."
    else:
        streak_nudge = "🚀 Start your Day 1 streak today! Even a 10-minute walk around campus counts."

    # Status summary
    if today_minutes >= 45:
        activity_status = "Champion level today! Make sure you prioritize proper hydration and stretching."
    elif today_minutes > 0:
        activity_status = f"Good momentum with {today_minutes} mins logged. You are close to crushing today's milestone."
    else:
        activity_status = "No activity logged yet today. Take a quick break from your desk and get moving!"

    return {
        "goal": user_summary.get("goal", "Stay Fit"),
        "today_minutes": today_minutes,
        "streak": streak,
        "activity_status": activity_status,
        "streak_nudge": streak_nudge,
        "workout_recommendation": workout_pick,
        "nutrition_tip": nutrition_pick,
        "recovery_tip": recovery_pick,
        "weekly_progress": f"{user_summary.get('weekly_minutes', 0)} / {user_summary.get('weekly_target_minutes', 240)} mins ({user_summary.get('weekly_progress_pct', 0)}%)",
    }


# ---------------------------------------------------------------------------
# Instant Post-Activity Feedback
# ---------------------------------------------------------------------------

def get_activity_coach_feedback(activity_name, minutes, points, new_streak, new_badges):
    """
    Returns an immediate coaching reaction and tip when a student logs an activity.
    """
    burned_approx = int(minutes * 6.5)
    cheers = [
        "Way to crush it!",
        "Outstanding consistency!",
        "Every minute counts toward your campus fitness rank!",
        "Boom! That was an energizing session."
    ]
    cheer = random.choice(cheers)

    tip = f"{cheer} Logging {minutes} mins of {activity_name} burned ~{burned_approx} kcal and earned you +{points} points ⭐."
    if new_streak >= 3:
        tip += f" Your streak is on fire at {new_streak} days! 🔥"
    else:
        tip += f" Streak updated to {new_streak} day(s)!"

    if new_badges:
        tip += f" 🏆 Congratulations on unlocking new badge(s): {', '.join(new_badges)}!"

    # Specific recovery tip per activity type
    act_lower = activity_name.lower()
    if "run" in act_lower or "walk" in act_lower or "jog" in act_lower:
        tip += " Take 3 minutes to stretch your calves and hamstrings."
    elif "gym" in act_lower or "weight" in act_lower or "workout" in act_lower:
        tip += " Grab a protein-rich snack or meal within 45 minutes to refuel."
    elif "cycle" in act_lower or "cycling" in act_lower:
        tip += " Great cardiovascular stimulus! Hydrate well with electrolytes."
    else:
        tip += " Keep this momentum going tomorrow!"

    return tip


# ---------------------------------------------------------------------------
# Conversational AI Coach
# ---------------------------------------------------------------------------

def _call_gemini_api(prompt, api_key):
    """Call Google Gemini REST API using urllib (zero external pip dependencies)."""
    # Try gemini-1.5-flash endpoint
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 450
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        candidates = res.get("candidates", [])
        if candidates and candidates[0].get("content", {}).get("parts"):
            return candidates[0]["content"]["parts"][0]["text"]
        return None


def chat_with_coach(user_message, user_summary, history=None):
    """
    Processes an interactive user query and returns an intelligent response,
    contextualized with the user's real daily activity, streak, and goals.
    """
    user_name = user_summary.get("user_name", "Student")
    goal = user_summary.get("goal", "General Fitness")
    streak = user_summary.get("streak", 0)
    today_min = user_summary.get("today_minutes", 0)
    weekly_min = user_summary.get("weekly_minutes", 0)
    weekly_target = user_summary.get("weekly_target_minutes", 240)
    points = user_summary.get("today_points", 0)

    # 1. Try Gemini AI if GEMINI_API_KEY is available in env or database
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        conn = get_db()
        api_key = get_setting(conn, "gemini_api_key")
        conn.close()

    if api_key and api_key.strip():
        try:
            system_context = (
                f"You are the CampusFit AI Coach, a friendly, energetic, and highly knowledgeable campus fitness mentor. "
                f"Student Name: {user_name}. "
                f"Fitness Goal: {goal}. "
                f"Active Streak: {streak} days. "
                f"Today's active minutes: {today_min} mins. "
                f"Weekly active minutes: {weekly_min}/{weekly_target} mins. "
                f"Today's points: {points}. "
                f"Answer the student's question directly with motivational, scientifically sound, and practical advice tailored for college students (dorm rooms, hostel mess/canteens, study schedules). "
                f"Use bullet points, bold text, and keep answers concise (100-150 words)."
            )
            prompt = f"{system_context}\n\nStudent asks: \"{user_message}\"\n\nCoach Response:"
            reply = _call_gemini_api(prompt, api_key.strip())
            if reply and reply.strip():
                return {
                    "reply": reply.strip(),
                    "source": "gemini_ai",
                    "suggested_actions": ["Log Activity", "Send Email Summary", "Check Leaderboard"],
                    "quick_replies": ["Give me a 15-min dorm workout", "What should I eat at the canteen?", "How to protect my streak?"]
                }
        except Exception:
            pass  # Fall back to our extensive local expert engine

    # 2. Comprehensive Local Expert Coaching Engine
    msg = (user_message or "").lower().strip()

    # (A) Greetings / Casual Chat / Introduction
    if any(msg.startswith(w) or msg == w for w in ["hi", "hello", "hey", "sup", "yo", "good morning", "good evening", "how are you", "who are you", "what can you do"]):
        activity_note = f"You've logged **{today_min} mins** today!" if today_min > 0 else "You haven't logged any activity today yet."
        reply = (
            f"Hey {user_name}! 👋 Great to see you. I'm your **CampusFit AI Coach**.\n\n"
            f"📊 **Your Status Today**:\n"
            f"• Goal: **{goal}**\n"
            f"• Streak: **{streak} days 🔥**\n"
            f"• Today's Movement: {activity_note}\n\n"
            f"I can give you customized workout routines, campus canteen diet hacks, streak protection tips, or email your daily summary. What's on your mind today?"
        )
        actions = ["Today's Workout", "Canteen Diet", "Email My Report"]
        quicks = ["What should I do today?", "How to lose belly fat?", "15-min dorm workout"]

    # (B) Weight Loss / Belly Fat / Burning Calories
    elif any(w in msg for w in ["fat", "belly", "weight loss", "lose weight", "lose fat", "slim", "cutting", "calories", "love handle", "burn"]):
        reply = (
            f"Targeting **fat loss**, {user_name}? Here is the honest, science-backed campus roadmap:\n\n"
            f"1. **Spot reduction is a myth**: You can't just crunch away belly fat—fat loss happens across the whole body via a caloric deficit.\n"
            f"2. **Canteen Nutrition Hacks**:\n"
            f"   • Cut sugary chai, cold drinks, and fried canteen snacks (samosas/pakoras).\n"
            f"   • Double your protein: opt for boiled eggs, dal, curd, or paneer.\n"
            f"3. **High-Yield Campus Fat Burner**:\n"
            f"   • 4 rounds: 45s Jumping Jacks, 45s High Knees, 45s Mountain Climbers, 45s Bodyweight Squats (60s rest between rounds).\n"
            f"   • Take the stairs to your hostel room and lecture halls instead of the elevator!\n\n"
            f"👉 Don't forget to log 20-30 mins in the **Activity** tab to earn +40-60 points!"
        )
        actions = ["Log 25m HIIT Workout", "Email My Tips"]
        quicks = ["Dorm room abs circuit", "Healthy canteen foods", "How much water daily?"]

    # (C) Muscle Building / Bulking / Strength / Lifting
    elif any(w in msg for w in ["muscle", "bulk", "bicep", "tricep", "strength", "lifting", "weights", "hypertrophy", "mass", "gain weight", "chest", "pushup", "push up", "pullup"]):
        reply = (
            f"Ready to build strength and pack on lean muscle, {user_name}? Here is your campus blueprint:\n\n"
            f"💪 **Hostel / Dorm Strength Circuit**:\n"
            f"• **Push-ups**: 4 sets of 12-15 reps (elevate feet on chair for upper chest)\n"
            f"• **Chair Dips**: 3 sets of 15 reps (triceps and shoulders)\n"
            f"• **Doorway / Towel Rows**: 4 sets of 12 reps (back and biceps)\n"
            f"• **Bodyweight Squats + Wall Sit**: 4 sets of 20 squats + 45s wall sit\n\n"
            f"🥩 **Mess & Canteen Fuel**:\n"
            f"• Aim for 1.4–1.8g protein per kg of bodyweight.\n"
            f"• In mess/canteen: ask for extra eggs, soya chunks, paneer, and milk.\n"
            f"• Hydrate with at least 3L of water for muscle fullness and recovery."
        )
        actions = ["Log 30m Strength Workout", "Nutrition Guide"]
        quicks = ["Best canteen protein sources", "How many rest days needed?", "How to get a six pack?"]

    # (D) Abs / Core / Six-Pack
    elif any(w in msg for w in ["abs", "six pack", "six-pack", "core", "plank", "crunches", "waist"]):
        reply = (
            f"Want a strong, defined core, {user_name}? Here is the real formula:\n\n"
            f"🔥 **10-Minute Dorm Ab Routine** (3 rounds, 30s rest between rounds):\n"
            f"• **Plank with Shoulder Taps**: 40 seconds\n"
            f"• **Hollow Body Hold**: 30 seconds\n"
            f"• **Bicycle Crunches**: 40 seconds\n"
            f"• **Leg Raises / Reverse Crunches**: 15 reps\n\n"
            f"💡 **Key Rule**: Endless crunches won't reveal abs if body fat is elevated. Pair this with a clean diet and campus walking!"
        )
        actions = ["Log 15m Core Session", "What Should I Eat?"]
        quicks = ["How to lose belly fat?", "Plank form tips", "Log today's workout"]

    # (E) Daily Plan / What Should I Do Today?
    elif any(w in msg for w in ["today", "what should i do", "routine", "schedule", "daily plan", "suggest a workout", "plan"]):
        if today_min > 0:
            reply = (
                f"Awesome consistency, {user_name}! You've already completed **{today_min} minutes** of movement today (+{points} points)!\n\n"
                f"✅ **For the rest of today**:\n"
                f"• Focus on recovery: Drink at least 500ml water now.\n"
                f"• Do 5 minutes of gentle hamstring and shoulder stretches before bed.\n"
                f"• Sleep 7–8 hours so your muscles rebuild.\n\n"
                f"Your streak is locked in at **{streak} days** 🔥. Ready for me to email your complete daily report?"
            )
            actions = ["Send Email Digest Now", "View Full Dashboard"]
            quicks = ["Email me today's report", "Quick evening stretch routine", "Tomorrow's workout plan"]
        else:
            workouts = GOAL_WORKOUTS.get("weight loss" if "weight" in goal.lower() else "muscle gain" if "muscle" in goal.lower() else "general")
            w = random.choice(workouts)
            reply = (
                f"Here is your customized action plan for today, {user_name} (Goal: **{goal}**):\n\n"
                f"🎯 **Today's Mission**: Protect your **{streak}-day streak**!\n\n"
                f"🏋️ **Recommended Workout**: {w['title']} ({w['minutes']} mins, {w['intensity']})\n"
                f"{w['desc']}\n\n"
                f"👉 Complete this before the day ends, then head over to the **Activity** tab to log it and earn +{min(150, w['minutes']*2)} points!"
            )
            actions = ["Log Activity Now", "Give Me Another Workout"]
            quicks = ["Give me a 15-min dorm workout", "Canteen food tips", "Email my report"]

    # (F) Campus Canteen / Mess Food / Nutrition / Diet
    elif any(w in msg for w in ["canteen", "mess", "food", "eat", "diet", "meal", "nutrition", "snack", "maggi", "fast food", "protein", "supplements"]):
        nutr = random.choice(NUTRITION_TIPS)
        reply = (
            f"Here is how to master your diet around campus and hostel food, {user_name}:\n\n"
            f"{nutr}\n\n"
            f"🥦 **Smart College Eating Guide**:\n"
            f"• **Breakfast**: Boiled eggs, omelette with brown bread, oats, or poha/upma with peanuts.\n"
            f"• **Lunch / Dinner**: Double the dal/lentils, add a cup of curd/yogurt, ask for salad/cucumbers, limit deep-fried curries.\n"
            f"• **Late-Night Study Hack**: Replace Maggi and chips with roasted chana, almonds, or fruit.\n"
            f"• **Pre-Workout Fuel**: 1 banana 30 mins before exercising gives instant muscle glycogen."
        )
        actions = ["Log Workout", "Send Email Digest"]
        quicks = ["Best protein in canteen", "Healthy study snacks", "How much water daily?"]

    # (G) Motivation / Feeling Lazy / Tired / Procrastination
    elif any(w in msg for w in ["lazy", "tired", "motivate", "motivation", "don't feel like", "cant be bothered", "no energy", "exhausted", "give up"]):
        reply = (
            f"I hear you, {user_name}. College life, lectures, and exams can drain your energy—but here is the secret:\n\n"
            f"⚡ **Physical action creates mental energy, not the other way around.**\n\n"
            f"Use the **'2-Minute Rule'**:\n"
            f"1. Put on your shoes right now.\n"
            f"2. Just walk outside your hostel for 5 minutes.\n"
            f"3. If you still want to stop after 5 minutes, you can. But 90% of the time, your blood flow will kick in and you'll finish a great 15-minute session!\n\n"
            f"🔥 You have a **{streak}-day streak**. Don't let a temporary slump reset your hard-earned flame to 0!"
        )
        actions = ["Log 15m Walk", "Quick 5m Stretch"]
        quicks = ["15-min dorm workout", "Check my current streak", "Show leaderboard"]

    # (H) Running, Walking, Cardio & Stamina
    elif any(w in msg for w in ["run", "running", "walk", "walking", "cardio", "jog", "stamina", "endurance", "5k", "treadmill", "cycle", "cycling"]):
        reply = (
            f"Cardiovascular fitness is the ultimate campus life hack—it increases oxygen to your brain and lowers study stress!\n\n"
            f"🏃 **Campus Cardio Protocols**:\n"
            f"• **Beginner**: 20 minutes brisk power walking around campus sports grounds (aim for 120 steps/min).\n"
            f"• **Stamina Builder**: Run 2 minutes, walk 1 minute—repeat 6 times (18 minutes total).\n"
            f"• **Campus 5K Prep**: 3 runs per week. One easy 3km, one interval day (6x200m sprints), one 5km weekend run.\n\n"
            f"Logging a 30-minute run will earn you **+60 points** on the CampusFit leaderboard!"
        )
        actions = ["Log 30m Run", "View Events"]
        quicks = ["Best campus running spots", "How to prevent shin splints?", "Check leaderboard"]

    # (I) Soreness, Rest, Recovery & Pain
    elif any(w in msg for w in ["sore", "pain", "hurt", "injury", "rest", "stiff", "doms", "stretch", "sleep"]):
        rec = random.choice(RECOVERY_TIPS)
        reply = (
            f"Rest and recovery are when muscle fibers rebuild stronger, {user_name}!\n\n"
            f"{rec}\n\n"
            f"🩹 **DOMS (Delayed Onset Muscle Soreness) vs. Injury**:\n"
            f"• **Dull, stiff muscle ache**: Normal DOMS. Best remedy is light active recovery (a 15-minute gentle walk) and hydration.\n"
            f"• **Sharp, stabbing joint/tendon pain**: Rest immediately and apply ice. Do not push through sharp pain!\n\n"
            f"Tip: Spend 5 minutes stretching your hamstrings and quads before sleep."
        )
        actions = ["Log Light Stretch", "Email Daily Digest"]
        quicks = ["Quick neck & shoulder stretch", "Can I workout when sore?", "Best sleep duration"]

    # (J) Streak, Points, Badges & Campus League Rules
    elif any(w in msg for w in ["streak", "point", "points", "badge", "badges", "leaderboard", "team", "rules", "level"]):
        reply = (
            f"🏆 **CampusFit League Scoring & Rules**:\n\n"
            f"• **Activity Points**: Earn **2 points per active minute** (up to 150 points per workout).\n"
            f"• **Day Streaks**: Log at least one activity every calendar day to grow your streak flame 🔥. Milestones award badges at **3, 7, and 30 days**!\n"
            f"• **Campus Events**: Join official campus challenges and weekend 5Ks for +80 to +150 bonus points.\n"
            f"• **Rewards**: Use earned points in the Rewards store for canteen vouchers, sports court priority bookings, and gym passes!\n\n"
            f"You currently have **{points} points today** and a **{streak}-day streak**."
        )
        actions = ["View Leaderboard", "Visit Rewards Store"]
        quicks = ["Check my streak", "Upcoming campus events", "Log activity now"]

    # (K) Email / Notifications
    elif any(w in msg for w in ["mail", "email", "digest", "send", "report"]):
        reply = (
            f"✉️ **Daily Activity & Tips Email Digest**:\n\n"
            f"I can deliver your complete daily report directly to your inbox with:\n"
            f"• Today's total active minutes & points earned\n"
            f"• Active streak counter & milestone badges\n"
            f"• Recommended workout & nutrition advice for tomorrow\n\n"
            f"Click the button below or use the **'Email Me Today's Activity & Tips'** button on your dashboard to receive it!"
        )
        actions = ["Send Email Digest Now"]
        quicks = ["Send email digest now", "Configure my SMTP", "Back to dashboard"]

    # (L) Default / Context-Aware General Guidance
    else:
        workouts = GOAL_WORKOUTS.get("weight loss" if "weight" in goal.lower() else "muscle gain" if "muscle" in goal.lower() else "general")
        w = random.choice(workouts)
        reply = (
            f"Got it, {user_name}! As your campus fitness coach, I'm here to help you crush your **{goal}** goal.\n\n"
            f"📌 **Quick Recommendation for You**:\n"
            f"• Try **{w['title']}** ({w['minutes']} mins) to get your body moving today.\n"
            f"• Make sure you hit your daily hydration target (2.5L+).\n"
            f"• Your streak is currently at **{streak} days 🔥**.\n\n"
            f"Ask me anything specific like:\n"
            f"• *'Give me a 15-minute dorm workout'*\n"
            f"• *'How to lose belly fat?'*\n"
            f"• *'What should I eat at the campus canteen?'*\n"
            f"• *'Email me today's summary & tips'*"
        )
        actions = ["Today's Workout", "Canteen Nutrition", "Send Email Digest"]
        quicks = ["Give me a 15-min dorm workout", "How to lose belly fat?", "Healthy canteen foods"]

    return {
        "reply": reply,
        "source": "smart_coach_engine",
        "suggested_actions": actions,
        "quick_replies": quicks
    }
