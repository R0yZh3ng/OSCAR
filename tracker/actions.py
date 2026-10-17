"""The action layer: the ONE place the tracker's state is mutated.

The web UI, voice, RFID and gestures all call `dispatch(conn, name, args, source)`.
Add a feature by registering an action here; every input source gets it for free.
"""
import json
from datetime import datetime, timedelta

from . import progression, stats
from .db import iso, parse, today as db_today

ACTIONS = {}


def action(name):
    def register(fn):
        ACTIONS[name] = fn
        return fn
    return register


class ActionError(Exception):
    pass


def dispatch(conn, name, args=None, source="ui", today=None):
    """Run an action; returns its result plus XP/level-up/achievement deltas."""
    if name not in ACTIONS:
        raise ActionError(f"unknown action: {name}")
    args = args or {}
    today = today or db_today()
    before_xp = stats.total_xp(conn)
    before_level = progression.level_info(before_xp)["level"]

    with conn:
        result = ACTIONS[name](conn, args, source, today)
        conn.execute("INSERT INTO events(ts, action, args, source) VALUES (?,?,?,?)",
                     (datetime.now().isoformat(timespec="seconds"), name, json.dumps(args, default=str), source))

    after_xp = stats.total_xp(conn)
    info = progression.level_info(after_xp)
    with conn:
        unlocked = check_achievements(conn, today, info["level"])
    return {
        "result": result,
        "xp_delta": after_xp - before_xp,
        "level_up": ({"from": before_level, "to": info["level"], "title": info["title"]}
                     if info["level"] > before_level else None),
        "unlocked": [{"key": k, "title": progression.ACHIEVEMENTS[k][0],
                      "description": progression.ACHIEVEMENTS[k][1]} for k in unlocked],
    }


# ---------------------------------------------------------------- helpers

def resolve_habit(conn, ref):
    """`ref` is an id or a (case-insensitive) name, so voice can say 'gym'."""
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        row = conn.execute("SELECT * FROM habits WHERE id=?", (int(ref),)).fetchone()
    else:
        row = conn.execute("SELECT * FROM habits WHERE lower(name)=lower(?) AND archived=0",
                           (str(ref).strip(),)).fetchone()
    if not row:
        raise ActionError(f"no such habit: {ref}")
    return row


def _date(args, today):
    d = parse(args["date"]) if args.get("date") else today
    if d > today:
        raise ActionError("can't log the future")
    return d


def _set_entry(conn, habit, d, value, source):
    key = iso(d)
    if value <= 0:
        conn.execute("DELETE FROM entries WHERE habit_id=? AND date=?", (habit["id"], key))
    else:
        entries, skips = stats.habit_maps(conn, habit["id"])
        streak = stats.streak_before(habit, entries, skips, d)
        xp = progression.entry_xp(habit["difficulty"], value, habit["target"], streak)
        conn.execute("""INSERT INTO entries(habit_id, date, value, xp, source, created_at)
                        VALUES (?,?,?,?,?,?)
                        ON CONFLICT(habit_id, date) DO UPDATE SET value=excluded.value,
                        xp=excluded.xp, source=excluded.source""",
                     (habit["id"], key, value, xp, source, datetime.now().isoformat(timespec="seconds")))
    _sync_perfect_bonus(conn, d)


def _sync_perfect_bonus(conn, d):
    key = iso(d)
    if stats.is_perfect(conn, d):
        scheduled, _ = stats.day_summary(conn, d)
        amount = progression.perfect_day_bonus([h["difficulty"] for h in scheduled])
        conn.execute("""INSERT INTO bonus_xp(date, kind, amount) VALUES (?, 'perfect_day', ?)
                        ON CONFLICT(date, kind) DO UPDATE SET amount=excluded.amount""", (key, amount))
    else:
        conn.execute("DELETE FROM bonus_xp WHERE date=? AND kind='perfect_day'", (key,))


def check_achievements(conn, today, level):
    have = {r["key"] for r in conn.execute("SELECT key FROM achievements")}
    best = max((stats.best_streak(h, *stats.habit_maps(conn, h["id"]), today)
                for h in conn.execute("SELECT * FROM habits")), default=0)
    total = stats.total_completions(conn)
    earned = {
        "first_log": total >= 1,
        "perfect_day": bool(conn.execute(
            "SELECT 1 FROM bonus_xp WHERE kind='perfect_day' LIMIT 1").fetchone()),
        "streak_7": best >= 7, "streak_30": best >= 30, "streak_100": best >= 100,
        "total_100": total >= 100, "total_500": total >= 500,
        "perfect_week": stats.perfect_run(conn, today) >= 7,
        "level_5": level >= 5, "level_10": level >= 10, "level_20": level >= 20,
    }
    new = [k for k, ok in earned.items() if ok and k not in have]
    for k in new:
        conn.execute("INSERT INTO achievements(key, unlocked_at) VALUES (?,?)",
                     (k, datetime.now().isoformat(timespec="seconds")))
    return new


# ---------------------------------------------------------------- actions

@action("category.create")
def category_create(conn, args, source, today):
    cur = conn.execute("INSERT INTO categories(name, color) VALUES (?,?)",
                       (args["name"], args.get("color", "#6c8cff")))
    return {"id": cur.lastrowid}


@action("habit.create")
def habit_create(conn, args, source, today):
    cat = None
    if args.get("category"):
        row = conn.execute("SELECT id FROM categories WHERE lower(name)=lower(?)",
                           (args["category"],)).fetchone()
        if row:
            cat = row["id"]
        else:
            cat = conn.execute("INSERT INTO categories(name) VALUES (?)", (args["category"],)).lastrowid
    weekdays = args.get("weekdays", [0, 1, 2, 3, 4, 5, 6])
    cur = conn.execute(
        """INSERT INTO habits(name, icon, category_id, type, target, unit, difficulty, weekdays,
                               color, time_of_day, start_date)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (args["name"], args.get("icon", ""), cat, args.get("type", "check"),
         args.get("target", 1), args.get("unit", ""), int(args.get("difficulty", 1)),
         ",".join(str(w) for w in weekdays), args.get("color", "#6c8cff"),
         args.get("time_of_day", "anytime"), iso(args.get("start_date") or today)))
    return {"id": cur.lastrowid}


EDITABLE = ("name", "icon", "target", "unit", "difficulty", "color", "time_of_day", "type")


@action("habit.update")
def habit_update(conn, args, source, today):
    h = resolve_habit(conn, args["habit"])
    sets, vals = [], []
    for k in EDITABLE:
        if k in args:
            sets.append(f"{k}=?")
            vals.append(args[k])
    if "weekdays" in args:
        sets.append("weekdays=?")
        vals.append(",".join(str(w) for w in args["weekdays"]))
    if "category" in args:
        row = conn.execute("SELECT id FROM categories WHERE lower(name)=lower(?)",
                           (args["category"] or "",)).fetchone()
        cat = row["id"] if row else (conn.execute(
            "INSERT INTO categories(name) VALUES (?)", (args["category"],)).lastrowid
            if args["category"] else None)
        sets.append("category_id=?")
        vals.append(cat)
    if sets:
        conn.execute(f"UPDATE habits SET {', '.join(sets)} WHERE id=?", (*vals, h["id"]))
    return {"id": h["id"]}


@action("habit.note")
def habit_note(conn, args, source, today):
    h, d = resolve_habit(conn, args["habit"]), _date(args, today)
    cur = conn.execute("UPDATE entries SET note=? WHERE habit_id=? AND date=?",
                       (args.get("note", ""), h["id"], iso(d)))
    if not cur.rowcount:
        raise ActionError("log the habit first, then add a note")
    return {}


@action("mood.set")
def mood_set(conn, args, source, today):
    d = _date(args, today)
    mood = int(args["mood"])
    if not 1 <= mood <= 5:
        raise ActionError("mood must be 1-5")
    conn.execute("INSERT OR REPLACE INTO moods(date, mood) VALUES (?,?)", (iso(d), mood))
    return {}


@action("habit.unskip")
def habit_unskip(conn, args, source, today):
    h, d = resolve_habit(conn, args["habit"]), _date(args, today)
    conn.execute("DELETE FROM skips WHERE habit_id=? AND date=?", (h["id"], iso(d)))
    _sync_perfect_bonus(conn, d)
    return {}


@action("habit.archive")
def habit_archive(conn, args, source, today):
    h = resolve_habit(conn, args["habit"])
    conn.execute("UPDATE habits SET archived=1 WHERE id=?", (h["id"],))
    return {}


@action("habit.complete")
def habit_complete(conn, args, source, today):
    h, d = resolve_habit(conn, args["habit"]), _date(args, today)
    _set_entry(conn, h, d, h["target"], source)
    return {"habit": h["id"], "date": iso(d)}


@action("habit.log")
def habit_log(conn, args, source, today):
    """Count/duration habits: add (default) or set a value."""
    h, d = resolve_habit(conn, args["habit"]), _date(args, today)
    cur = conn.execute("SELECT value FROM entries WHERE habit_id=? AND date=?",
                       (h["id"], iso(d))).fetchone()
    value = float(args["value"])
    if args.get("add", True) and cur:
        value += cur["value"]
    _set_entry(conn, h, d, value, source)
    return {"habit": h["id"], "date": iso(d), "value": value}


@action("habit.undo")
def habit_undo(conn, args, source, today):
    h, d = resolve_habit(conn, args["habit"]), _date(args, today)
    _set_entry(conn, h, d, 0, source)
    return {"habit": h["id"], "date": iso(d)}


@action("habit.skip")
def habit_skip(conn, args, source, today):
    h, d = resolve_habit(conn, args["habit"]), _date(args, today)
    conn.execute("INSERT OR REPLACE INTO skips(habit_id, date, reason) VALUES (?,?,?)",
                 (h["id"], iso(d), args.get("reason", "rest")))
    _sync_perfect_bonus(conn, d)
    return {"habit": h["id"], "date": iso(d)}


# ---------------------------------------------------------------- read model

def build_state(conn, today=None, view=None):
    """`today` is the real current day; `view` is the day being displayed (for backfill)."""
    real_today = today or db_today()
    today = view or real_today
    key = iso(today)
    habits = []
    for h in conn.execute("""SELECT h.*, c.name AS category, c.color AS cat_color FROM habits h
                             LEFT JOIN categories c ON c.id = h.category_id
                             WHERE h.archived=0 ORDER BY h.id"""):
        entries, skips = stats.habit_maps(conn, h["id"])
        e = entries.get(key)
        habits.append({
            "id": h["id"], "name": h["name"], "icon": h["icon"], "type": h["type"],
            "target": h["target"], "unit": h["unit"], "difficulty": h["difficulty"],
            "category": h["category"], "cat_color": h["cat_color"], "color": h["color"],
            "time_of_day": h["time_of_day"], "weekdays": [int(w) for w in h["weekdays"].split(",")],
            "scheduled_today": stats.scheduled_on(h, today),
            "skipped_today": key in skips,
            "value": e["value"] if e else 0,
            "done": stats.is_complete(h, e),
            "xp_today": e["xp"] if e else 0,
            "note": e["note"] if e else "",
            "streak": stats.current_streak(h, entries, skips, today),
            "best_streak": stats.best_streak(h, entries, skips, today),
        })
    info = progression.level_info(stats.total_xp(conn))
    scheduled, done = stats.day_summary(conn, today)
    return {
        "today": iso(real_today),
        "view": key,
        "mood": (lambda r: r["mood"] if r else None)(
            conn.execute("SELECT mood FROM moods WHERE date=?", (key,)).fetchone()),
        "week": [{"date": iso(d), "ratio": (lambda sd: len(sd[1]) / len(sd[0]) if sd[0] else None)(
                      stats.day_summary(conn, d))}
                 for d in (today - timedelta(days=today.weekday()) + timedelta(days=i) for i in range(7))],
        "habits": habits,
        "level": info,
        "titles": progression.TITLES,
        "categories": stats.category_xp(conn),
        "today_progress": {"done": len(done), "total": len(scheduled)},
        "perfect_run": stats.perfect_run(conn, today),
        "achievements": [
            {"key": k, "title": t, "description": d,
             "unlocked_at": next((r["unlocked_at"] for r in conn.execute(
                 "SELECT unlocked_at FROM achievements WHERE key=?", (k,))), None)}
            for k, (t, d) in progression.ACHIEVEMENTS.items()],
    }
