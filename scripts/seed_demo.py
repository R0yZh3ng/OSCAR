"""Fill a tracker DB with ~100 days of plausible history so the charts have something to show.

    OSCAR_TRACKER_DB=data/demo.db python scripts/seed_demo.py
"""
import os
import random
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tracker import actions  # noqa: E402
from tracker.db import connect, today as db_today  # noqa: E402

HABITS = [
    # name, icon, color, category, type, target, unit, difficulty, time_of_day, weekdays, reliability
    ("Wake up early", "⏰", "#f5a524", "Health", "check", 1, "", 2, "morning", range(7), 0.7),
    ("Drink water", "💧", "#38bdf8", "Health", "count", 8, " cups", 1, "anytime", range(7), 0.8),
    ("Workout", "🏋️", "#f43f5e", "Health", "duration", 30, "m", 3, "afternoon", [0, 1, 3, 4], 0.75),
    ("Read", "📖", "#a78bfa", "Mind", "duration", 20, "m", 2, "evening", range(7), 0.65),
    ("Meditate", "🧘", "#34d399", "Mind", "check", 1, "", 1, "morning", range(7), 0.55),
    ("Study", "📚", "#6c8cff", "Work", "duration", 60, "m", 3, "afternoon", range(5), 0.7),
    ("Journal", "📝", "#fb923c", "Mind", "check", 1, "", 1, "evening", range(7), 0.6),
]


def main():
    conn = connect()
    if conn.execute("SELECT COUNT(*) FROM habits").fetchone()[0]:
        sys.exit("DB already has habits; point OSCAR_TRACKER_DB at an empty file.")
    rnd = random.Random(7)
    real_today = db_today()
    start = real_today - timedelta(days=100)
    for name, icon, color, cat, typ, target, unit, diff, tod, wd, _ in HABITS:
        actions.dispatch(conn, "habit.create", {
            "name": name, "icon": icon, "color": color, "category": cat, "type": typ, "target": target,
            "unit": unit, "difficulty": diff, "time_of_day": tod, "weekdays": list(wd),
            "start_date": start}, today=start)
    for i in range(101):
        d = start + timedelta(days=i)
        if i < 100:  # leave today empty so it is yours to complete
            motivation = 0.85 + 0.15 * (i / 100) - (0.25 if d.weekday() >= 5 else 0)
            for name, *_, wd, rel in HABITS:
                tgt = next(h[5] for h in HABITS if h[0] == name)
                if d.weekday() in wd and rnd.random() < rel * motivation + 0.1:
                    actions.dispatch(conn, "habit.log", {"habit": name, "value": tgt,
                                     "add": False, "date": d}, today=d)
            actions.dispatch(conn, "mood.set", {"mood": rnd.choice([2, 3, 3, 4, 4, 5]), "date": d}, today=d)
    print("seeded", conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0], "entries")


if __name__ == "__main__":
    main()
