"""Streaks and aggregates, computed from DB rows. No web or hardware imports."""
from collections import defaultdict
from datetime import timedelta

from . import progression
from .db import iso, parse


def scheduled_on(habit, d):
    return d >= parse(habit["start_date"]) and str(d.weekday()) in habit["weekdays"].split(",")


def is_complete(habit, entry):
    return entry is not None and entry["value"] >= habit["target"]


def habit_maps(conn, habit_id):
    entries = {r["date"]: r for r in conn.execute(
        "SELECT * FROM entries WHERE habit_id=?", (habit_id,))}
    skips = {r["date"] for r in conn.execute(
        "SELECT date FROM skips WHERE habit_id=?", (habit_id,))}
    return entries, skips


def streak_before(habit, entries, skips, d):
    """Consecutive completed scheduled days ending the day before `d`.
    Skipped and unscheduled days are neutral (don't extend, don't break)."""
    streak, cur = 0, d - timedelta(days=1)
    start = parse(habit["start_date"])
    while cur >= start:
        key = iso(cur)
        if scheduled_on(habit, cur) and key not in skips:
            if is_complete(habit, entries.get(key)):
                streak += 1
            else:
                break
        cur -= timedelta(days=1)
    return streak


def current_streak(habit, entries, skips, today):
    """Streak including today if done; an unfinished today doesn't break it."""
    s = streak_before(habit, entries, skips, today)
    if is_complete(habit, entries.get(iso(today))):
        s += 1
    return s


def best_streak(habit, entries, skips, today):
    best = run = 0
    cur = parse(habit["start_date"])
    while cur <= today:
        key = iso(cur)
        if scheduled_on(habit, cur) and key not in skips:
            if is_complete(habit, entries.get(key)):
                run += 1
                best = max(best, run)
            elif cur < today:
                run = 0
        cur += timedelta(days=1)
    return best


def total_xp(conn):
    e = conn.execute("SELECT COALESCE(SUM(xp),0) FROM entries").fetchone()[0]
    b = conn.execute("SELECT COALESCE(SUM(amount),0) FROM bonus_xp").fetchone()[0]
    return e + b


def category_xp(conn):
    rows = conn.execute("""
        SELECT c.id, c.name, c.color, COALESCE(SUM(e.xp),0) AS xp
        FROM categories c
        LEFT JOIN habits h ON h.category_id = c.id
        LEFT JOIN entries e ON e.habit_id = h.id
        GROUP BY c.id ORDER BY c.name""").fetchall()
    return [{"id": r["id"], "name": r["name"], "color": r["color"],
             **progression.level_info(r["xp"])} for r in rows]


def total_completions(conn):
    n = 0
    for h in conn.execute("SELECT * FROM habits"):
        for e in conn.execute("SELECT value FROM entries WHERE habit_id=?", (h["id"],)):
            n += e["value"] >= h["target"]
    return n


def day_summary(conn, d):
    """(scheduled_habits, completed_ids) for a date, excluding skipped/archived."""
    key = iso(d)
    scheduled = [h for h in conn.execute("SELECT * FROM habits WHERE archived=0")
                 if scheduled_on(h, d) and not conn.execute(
                     "SELECT 1 FROM skips WHERE habit_id=? AND date=?", (h["id"], key)).fetchone()]
    done = set()
    for h in scheduled:
        e = conn.execute("SELECT * FROM entries WHERE habit_id=? AND date=?", (h["id"], key)).fetchone()
        if is_complete(h, e):
            done.add(h["id"])
    return scheduled, done


def is_perfect(conn, d):
    scheduled, done = day_summary(conn, d)
    return bool(scheduled) and len(done) == len(scheduled)


def perfect_run(conn, today):
    """Consecutive perfect days ending today (or yesterday if today unfinished)."""
    run, cur = 0, today
    if not is_perfect(conn, cur):
        cur -= timedelta(days=1)
    while is_perfect(conn, cur):
        run += 1
        cur -= timedelta(days=1)
    return run


def heatmap(conn, today, days=140):
    """date -> completion ratio over the scheduled habits that day (None = nothing scheduled)."""
    out = {}
    start = today - timedelta(days=days - 1)
    habits = conn.execute("SELECT * FROM habits").fetchall()
    done_by_date = defaultdict(set)
    for r in conn.execute("SELECT habit_id, date, value FROM entries WHERE date>=?", (iso(start),)):
        done_by_date[r["date"]].add((r["habit_id"], r["value"]))
    targets = {h["id"]: h["target"] for h in habits}
    cur = start
    while cur <= today:
        key = iso(cur)
        sched = [h for h in habits if not h["archived"] and scheduled_on(h, cur)]
        if sched:
            done = sum(1 for hid, v in done_by_date[key] if v >= targets[hid]
                       and any(h["id"] == hid for h in sched))
            out[key] = round(done / len(sched), 2)
        cur += timedelta(days=1)
    return out


# ------------------------------------------------------------------ visual stats

STRENGTH_DECAY = 0.5 ** (1 / 9)  # Loop-style smoothing: a scheduled day moves the score ~7% of the way


def day_status(habit, entries, skips, d, today):
    """done | partial | missed | skipped | pending | None (not scheduled)."""
    key = iso(d)
    e = entries.get(key)
    if is_complete(habit, e):
        return "done"
    if not scheduled_on(habit, d):
        return None
    if key in skips:
        return "skipped"
    if e:
        return "partial" if d < today else "pending"
    return "missed" if d < today else "pending"


def strength_series(habit, entries, skips, today, days=90):
    """Habit strength 0..1. Every scheduled repetition lifts it and every miss lowers it
    gradually, so one bad day after a long run barely dents it (unlike a raw streak)."""
    score, series = 0.0, {}
    cur = parse(habit["start_date"])
    while cur <= today:
        status = day_status(habit, entries, skips, cur, today)
        if status in ("done", "partial", "missed"):
            e = entries.get(iso(cur))
            frac = min(e["value"] / habit["target"], 1.0) if e else 0.0
            score = score * STRENGTH_DECAY + frac * (1 - STRENGTH_DECAY)
        series[iso(cur)] = round(score, 3)
        cur += timedelta(days=1)
    first = iso(today - timedelta(days=days - 1))
    return {k: v for k, v in series.items() if k >= first}, score


def habit_detail(conn, habit, today):
    entries, skips = habit_maps(conn, habit["id"])
    start = parse(habit["start_date"])
    series, strength = strength_series(habit, entries, skips, today)

    calendar, weekday_hits, weekday_total = {}, [0] * 7, [0] * 7
    cur = max(start, today - timedelta(days=370))
    while cur <= today:
        st = day_status(habit, entries, skips, cur, today)
        if st:
            calendar[iso(cur)] = st
        if st in ("done", "partial", "missed"):
            weekday_total[cur.weekday()] += 1
            weekday_hits[cur.weekday()] += st == "done"
        cur += timedelta(days=1)

    last30 = [v for k, v in calendar.items() if k > iso(today - timedelta(days=30))
              and v in ("done", "partial", "missed")]
    weeks = []
    for w in range(11, -1, -1):
        end = today - timedelta(days=7 * w)
        begin = end - timedelta(days=6)
        weeks.append({"start": iso(begin), "count": sum(
            1 for k, v in calendar.items() if iso(begin) <= k <= iso(end) and v == "done")})
    notes = [{"date": k, "note": e["note"]} for k, e in sorted(entries.items(), reverse=True)
             if e["note"]][:5]
    return {
        "id": habit["id"],
        "strength": round(strength, 3),
        "strength_series": series,
        "calendar": calendar,
        "weekday_rate": [round(h / t, 2) if t else None for h, t in zip(weekday_hits, weekday_total)],
        "weeks": weeks,
        "streak": current_streak(habit, entries, skips, today),
        "best_streak": best_streak(habit, entries, skips, today),
        "completions": sum(1 for e in entries.values() if is_complete(habit, e)),
        "total_value": round(sum(e["value"] for e in entries.values()), 1),
        "xp": sum(e["xp"] for e in entries.values()),
        "rate_30d": round(sum(v == "done" for v in last30) / len(last30), 2) if last30 else None,
        "notes": notes,
        "today_note": entries[iso(today)]["note"] if iso(today) in entries else "",
    }


def overview(conn, today, days=90):
    habits = conn.execute("""SELECT h.*, c.name AS category, c.color AS cat_color FROM habits h
                             LEFT JOIN categories c ON c.id = h.category_id
                             WHERE h.archived=0""").fetchall()
    maps = {h["id"]: habit_maps(conn, h["id"]) for h in habits}

    daily, tod, cat = [], defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    weekday = [[0, 0] for _ in range(7)]
    heat = {}
    for i in range(364, -1, -1):
        d = today - timedelta(days=i)
        sched = done = 0
        for h in habits:
            entries, skips = maps[h["id"]]
            st = day_status(h, entries, skips, d, today)
            if st in ("done", "partial", "missed") or (st == "pending" and i == 0):
                sched += 1
                done += st == "done"
                if i < 30:
                    tod[h["time_of_day"]][1] += 1
                    tod[h["time_of_day"]][0] += st == "done"
                    cat[h["category"] or "Other"][1] += 1
                    cat[h["category"] or "Other"][0] += st == "done"
                if i < 90 and st != "pending":
                    weekday[d.weekday()][1] += 1
                    weekday[d.weekday()][0] += st == "done"
        if sched:
            heat[iso(d)] = round(done / sched, 2)
            if i < days:
                daily.append({"date": iso(d), "rate": round(done / sched, 2), "done": done, "total": sched})

    # 7-day moving average of the daily rate
    rates = [x["rate"] for x in daily]
    for i, x in enumerate(daily):
        window = rates[max(0, i - 6): i + 1]
        x["avg"] = round(sum(window) / len(window), 2)

    xp_by_day = defaultdict(int)
    first = iso(today - timedelta(days=29))
    for r in conn.execute("SELECT date, SUM(xp) AS xp FROM entries WHERE date>=? GROUP BY date", (first,)):
        xp_by_day[r["date"]] += r["xp"]
    for r in conn.execute("SELECT date, SUM(amount) AS xp FROM bonus_xp WHERE date>=? GROUP BY date", (first,)):
        xp_by_day[r["date"]] += r["xp"]
    xp_series = [{"date": iso(today - timedelta(days=i)),
                  "xp": xp_by_day[iso(today - timedelta(days=i))]} for i in range(29, -1, -1)]

    moods = {r["date"]: r["mood"] for r in conn.execute(
        "SELECT * FROM moods WHERE date>=?", (iso(today - timedelta(days=days)),))}
    by_mood = defaultdict(list)
    for k, m in moods.items():
        if k in heat:
            by_mood[m].append(heat[k])
    mood_rate = {m: round(sum(v) / len(v), 2) for m, v in sorted(by_mood.items())}

    ranking = sorted(({"id": h["id"], "name": h["name"], "icon": h["icon"], "color": h["color"],
                       "strength": round(strength_series(h, *maps[h["id"]], today)[1], 3)}
                      for h in habits), key=lambda x: -x["strength"])
    perfect_days = conn.execute("SELECT COUNT(*) FROM bonus_xp WHERE kind='perfect_day'").fetchone()[0]
    rate = lambda p: round(p[0] / p[1], 2) if p[1] else None
    return {
        "daily": daily,
        "heatmap": heat,
        "weekday_rate": [rate(w) for w in weekday],
        "time_of_day": {k: rate(v) for k, v in tod.items()},
        "wheel": [{"name": k, "rate": rate(v)} for k, v in sorted(cat.items())],
        "xp_series": xp_series,
        "moods": moods,
        "mood_rate": mood_rate,
        "ranking": ranking,
        "totals": {
            "completions": total_completions(conn),
            "perfect_days": perfect_days,
            "best_streak": max((best_streak(h, *maps[h["id"]], today) for h in habits), default=0),
            "habits": len(habits),
        },
    }
