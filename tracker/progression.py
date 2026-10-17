"""Leveling, XP and achievements. Pure functions over numbers; no DB access.

Design goals (what keeps it engaging):
  * Fast early levels so progress is felt in the first days, slowing gradually.
  * Streaks multiply XP, but are capped so a miss never feels catastrophic.
  * Partial credit for count/duration habits, capped at the target so over-logging
    can't farm XP.
  * Perfect days pay a bonus, so finishing the *whole* list matters.
  * XP is stored on entries, so undoing an entry takes its XP back.
"""

BASE_XP = {1: 10, 2: 20, 3: 35}  # by habit difficulty
STREAK_CAP_DAYS = 30
STREAK_MAX_BONUS = 0.5           # +50% at a 30-day streak
PERFECT_DAY_FRACTION = 0.25      # of the day's base XP

# (min_level, title)
TITLES = [
    (1, "Newcomer"), (3, "Apprentice"), (6, "Regular"), (10, "Committed"),
    (15, "Disciplined"), (20, "Relentless"), (30, "Master"), (40, "Legend"),
]


def xp_for_level(level):
    """Total XP needed to reach `level` (level 1 = 0)."""
    if level <= 1:
        return 0
    return round(100 * (level - 1) ** 1.6)


def level_info(total_xp):
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    floor, ceil = xp_for_level(level), xp_for_level(level + 1)
    return {
        "level": level,
        "title": title_for(level),
        "xp": total_xp,
        "level_start": floor,
        "next_level_at": ceil,
        "into_level": total_xp - floor,
        "level_span": ceil - floor,
        "progress": (total_xp - floor) / (ceil - floor),
    }


def title_for(level):
    title = TITLES[0][1]
    for min_level, t in TITLES:
        if level >= min_level:
            title = t
    return title


def streak_multiplier(streak_days):
    return 1 + STREAK_MAX_BONUS * min(streak_days, STREAK_CAP_DAYS) / STREAK_CAP_DAYS


def entry_xp(difficulty, value, target, streak_days):
    """XP for one habit on one day. `streak_days` = streak going into that day."""
    fraction = min(value / target, 1.0) if target > 0 else 1.0
    return round(BASE_XP.get(difficulty, BASE_XP[1]) * fraction * streak_multiplier(streak_days))


def perfect_day_bonus(scheduled_difficulties):
    base = sum(BASE_XP.get(d, BASE_XP[1]) for d in scheduled_difficulties)
    return round(base * PERFECT_DAY_FRACTION)


# key -> (title, description). Checked in tracker/actions.py against live stats.
ACHIEVEMENTS = {
    "first_log":   ("First Step", "Log your first habit"),
    "perfect_day": ("Clean Sweep", "Complete every habit scheduled for a day"),
    "streak_7":    ("One Week Strong", "7-day streak on any habit"),
    "streak_30":   ("Monthly Machine", "30-day streak on any habit"),
    "streak_100":  ("Centurion", "100-day streak on any habit"),
    "total_100":   ("Hundred Club", "100 total completions"),
    "total_500":   ("Five Hundred", "500 total completions"),
    "perfect_week": ("Flawless Week", "7 perfect days in a row"),
    "level_5":     ("Level 5", "Reach level 5"),
    "level_10":    ("Level 10", "Reach level 10"),
    "level_20":    ("Level 20", "Reach level 20"),
}
