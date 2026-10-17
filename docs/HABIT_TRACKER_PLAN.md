# OSCAR Habit Tracker — Plan

## Decision: build it as a webapp that runs on the Pi (not a separate app)

Host it on the Pi as a third OSCAR service (`tracker/`), served over the LAN. This gives every
delivery option from one codebase:

- **Phone / laptop**: open `http://oscar.local:5001`, install as a PWA ("add to home screen"). This
  is where you tick habits off day to day.
- **Projected on the wall**: the existing kiosk display shows the tracker's widget board as another
  view ("habits"), alongside the schedule.
- **Public hosting later**: it is a normal Flask + SQLite app, so it can move to a VPS unchanged.
  Not needed for v1, and not recommended: the Pi is the source of truth and the data is personal.

Not recommended: a native/desktop app (no benefit over a PWA here) or a fully separate project (it
would duplicate the router, the display socket and the config conventions OSCAR already has).

## The one design rule that makes voice/gesture trivial later

**Every change to the tracker is a named action sent through one function**, never a UI-only side
effect. Buttons, voice, RFID and gestures are all just different callers of it.

```
POST /api/actions   { "action": "habit.complete", "args": { "habit": "gym" }, "source": "ui" }
```

- `source` is `ui | voice | rfid | gesture | api`, stored in the event log for stats and debugging.
- The web UI uses only this endpoint for mutations (reads are plain `GET`s). If the UI can do it,
  voice can do it, with no extra backend work.
- The control daemon's command router (see PLAN.md) gets one new handler that forwards to this
  endpoint. Keyword → action mapping lives in config, not code:
  `config/tracker_commands.json`, e.g. `{"done": "habit.complete", "undo": "habit.undo", "stats": "view.show:stats"}`.
- Actions that need an argument ("log gym") are the point where the deferred STT/LLM fallback
  (US-16/17) plugs in: free-form speech → LLM → one of these same actions. The v1 fixed-keyword loop
  can already do argument-free ones ("next habit", "done", "undo", "stats", "habits", "hide").
- **Gesture**: the glove or camera emits the same action names (swipe → `view.next`, tap →
  `habit.complete` on the focused widget). The UI keeps a **focused widget/habit** cursor so that
  "done" and a single gesture have something to act on.
- Server pushes state changes over the existing flask-socketio channel so the wall display, phone
  and any open tab all update live.

## Data model (SQLite, single file `data/tracker.db`)

Append-only event log as the source of truth; everything else is derived. This makes undo, edits,
backfilling and every stat/graph a query rather than extra bookkeeping.

| Table | Key fields |
|---|---|
| `habits` | id, name, icon, color, category_id, type (`check` / `count` / `duration` / `rating`), target, unit, schedule (RRULE-ish: daily, weekdays, N× per week, every N days), start/end date, archived, sort |
| `categories` | id, name, color, wheel_axis (feeds the Wheel of Life) |
| `entries` | id, habit_id, date, value, note, source, created_at (deletable = undo) |
| `skips` | habit_id, date, reason (`rest` / `sick` / `travel`): excluded from streak breaks |
| `xp_events` | id, date, amount, reason, habit_id |
| `achievements` | key, unlocked_at |
| `journal` | date, mood, energy, text |
| `widgets` | id, dashboard_id, type, config JSON, x, y, w, h |
| `dashboards` | id, name, sort |
| `events` | id, ts, action, args JSON, source (full audit log of actions) |

Also stored: a `tz`/day-rollover setting (day ends at e.g. 4 am so late-night habits count for the
right day).

## Feature list

### Habit tracking core
- Habit types: yes/no, count ("8 glasses"), duration ("30 min"), rating (1–5), and **numeric
  metrics** (weight, sleep hours) that are tracked rather than completed.
- Flexible schedules: daily, specific weekdays, N times per week/month, every N days.
- Streaks: current, best, **forgiving streaks** (skips and rest days don't break it; optional
  "1 miss allowed per week").
- Quick-log, undo, backfill past days, notes on any entry, archive instead of delete.
- Habit stacking / ordering into routines (morning / evening) with a "routine runner" focus view
  that walks through one habit at a time (also the ideal voice/gesture view).
- Timers and a Pomodoro widget that auto-logs duration habits.
- Reminders: shown on the projected wall, plus web push on the phone PWA, plus an LED/chime cue from
  OSCAR when something is overdue and you are awake in the room.

### The "wheel" and progression
Interpreted two ways; both are built, since they work together (tell me if you meant only one):
- **Radial rings** (Apple Activity-style): one ring per habit or category showing today's progress.
- **Wheel of Life radar**: categories (Health, Study, Work, Social, Mind, …) as radar axes, scored
  from the last 7/30 days. A lopsided wheel shows what is being neglected.
- **Progression**: XP per completion (weighted by difficulty and streak multiplier), levels, per-
  category levels, daily/weekly quests ("complete 5 gym sessions"), badges/achievements (first 7-day
  streak, 100 total completions, perfect week, comeback after a miss), and optional "boss weeks".
  Level-ups are a flourish on the projected display plus a distinct LED animation.

### Stats and graphs (the "more than Notion" part)
- Calendar **heatmap** (GitHub-style, per habit and overall), year view.
- Completion rate over time (line), weekly/monthly bars, streak timeline, **day-of-week** and
  **time-of-day** patterns, per-category stacked area.
- Correlations: habit vs. habit, habit vs. mood/energy/sleep ("on days you gym, sleep is +0.8 h").
- Trend lines and moving averages for numeric metrics, with goal bands.
- Weekly and monthly auto-generated review (wins, misses, best streak, suggested adjustment).
- Habit "health" score and at-risk list (habits about to lose a streak).
- Export everything to CSV/JSON; import from CSV.

### Notion-like widget board
- Multiple **dashboards** (Today, Stats, Wall display, Phone), each a drag-and-resize grid of
  widgets, saved per dashboard and editable in an edit mode.
- Widget types: today checklist, rings, streak list, heatmap, line/bar chart, Wheel of Life radar,
  XP/level bar, quote, journal entry, mood tracker, timer, countdown to a date, notes/markdown,
  schedule (reads OSCAR's `schedule.json`), clock/weather.
- Per-widget config (which habits, time range, chart type) and a **widget registry** so adding a
  new widget is one file.
- Views per habit database-style: table, board by category, calendar, gallery. Filters, sorts,
  tags, simple formulas for computed columns.
- Templates (starter dashboards) and light/dark/"wall" themes. The wall theme is high-contrast and
  large because it is read from across a room through a projector.

### OSCAR integration
- Schedule events can be linked to a habit (a "Gym 6pm" event completes the habit when ticked).
- **Mode awareness**: RFID `work` mode shows work habits, `daily` shows everything (same
  `category`-filter idea as the schedule). Voice "wall"/"closet" only changes aim, same as v1.
- Voice commands "habits", "stats", "done", "undo", "next", "hide" ride the existing keyword model;
  new keywords mean retraining (collect data for them in the same session as the existing six).
- A physical **RFID habit tag** later: tap to complete a specific habit, e.g. a tag on the gym bag.

## Architecture

```
tracker/
  app.py                 Flask app factory + socketio
  actions.py             the action registry: name -> function(args) -> state delta  (THE seam)
  models.py, db.py       SQLite access (sqlite3 or SQLAlchemy)
  stats.py               streaks, rates, XP, correlations (pure functions, unit-tested)
  api.py                 GET reads + POST /api/actions
  static/                PWA front end (manifest, service worker, widgets/)
  templates/
config/tracker_commands.json   keyword/gesture -> action map
data/tracker.db                not committed
```

- **Backend**: Flask + flask-socketio + SQLite, matching the display app so there is one stack to
  learn and one process model. Pi 4B (2GB) handles this with room to spare; the keyword model is
  the heavy part and runs in a separate process.
- **Frontend**: no build step. Preact + htm (or plain web components), a grid layout library for
  drag/resize, and **uPlot or Chart.js** for time series with custom SVG for rings, radar and
  heatmap. Keeps it light enough for the Pi's Chromium kiosk.
- **Offline-first PWA**: service worker caches the shell; checkmarks made offline queue and sync to
  `/api/actions` when back on the LAN.
- **Auth**: LAN-only to start; a single shared token/PIN before exposing beyond the home network.
- **Testing**: `stats.py` and `actions.py` have no hardware or web dependencies, so they are
  testable on the dev laptop, like the router in PLAN.md.

## Build phases

1. **Core (≈1 weekend)**: schema, `actions.py`, habit CRUD, check/count types, today checklist,
   streaks, heatmap, PWA shell. Usable daily from the phone.
2. **Stats and progression**: rings, Wheel of Life, XP/levels/achievements, charts, weekly review.
3. **Widget board**: dashboards, drag/resize grid, widget registry, wall theme and the kiosk view.
4. **OSCAR hookup**: `tracker` view in the display app, command-router handler, mode filter, LED
   cues, `systemd` unit `oscar-tracker.service`.
5. **Voice**: extend the keyword set (`done`, `undo`, `next`, `habits`, `stats`), then the LLM
   fallback for argument-bearing commands.
6. **Gesture**: map the glove/camera events to the same action names. No tracker changes needed,
   since the action layer and focus cursor already exist.

## Open questions

- Does "wheel progression" mean the rings / Wheel of Life radar, the level-up progression, or both?
  The plan assumes both.
- Phone-first or wall-first as the primary way to log? This affects how much effort goes into the
  PWA versus the kiosk/focus view in phase 1.
- Any need for multi-user (roommate) support? Cheap to add `user_id` to every table now, painful later.

## Implemented so far (phase 1 + leveling core)

Run: `python -m tracker.app` (port 5001, `OSCAR_TRACKER_DB` / `OSCAR_TRACKER_PORT` override). Tests: `python -m unittest discover -s tests`.

**Leveling rules** (all in `tracker/progression.py`, tune the constants there):
- XP per habit per day: 10 / 20 / 35 by difficulty (easy / medium / hard), scaled by progress toward
  the target (count and duration habits earn partial credit, capped at 100%).
- Streak multiplier: up to +50% at a 30-day streak. Skips and unscheduled days don't break it.
- Perfect-day bonus: +25% of that day's base XP when every scheduled habit is done.
- Level N needs `100 * (N-1)^1.6` total XP: level 2 at 100, 5 at ~920, 10 at ~3,400. A few habits a
  day gives a level every day or two at first, slowing to roughly weekly by the teens.
- Titles from Newcomer to Legend, per-category skill levels, and 11 achievements.
- Undo removes the XP (and the perfect-day bonus if it no longer applies), so it can't be farmed.
- Responses to every action include `xp_delta`, `level_up` and `unlocked`, which the UI turns into
  toasts and the full-screen level-up overlay. The wall display and LEDs can react to the same fields.

**Layout (current):** one dashboard of widgets, no tabs. Habits, level, streaks and mood sit at the top; trend, best days, time of day, life balance, year heatmap, strength ranking, XP and achievements below. Tapping the empty part of any widget opens its full page (`#/trend`, `#/year`, `#/ranking`, `#/patterns`, `#/balance`, `#/xp`, `#/rewards`, `#/streaks`, `#/mood`, `#/habits`); the browser back button returns. Habit rings stay tappable on the dashboard itself.

**Visual UI (built):** Streaks-style tappable progress rings grouped by time of day, week strip with
backfill, mood check-in, per-habit detail sheet (Loop-style habit strength score + trend, Way of
Life-style tap-to-edit calendar, weekday and weekly charts, timer, notes, skip), Stats tab (trend with
7-day average, year heatmap, strength ranking, weekday and time-of-day bars, life-balance radar, XP
history, mood vs. completion), Rewards tab (level, title ladder, skill levels, achievements),
templates and emoji/color pickers for adding habits, confetti and level-up overlay, `?wall=1` large
display mode. `python scripts/seed_demo.py` fills a DB with 100 days of sample data.

Not built yet: weekly quests, boss weeks, negative ("quit") habits, reorder, PWA manifest/offline
queue, widget board editing, CSV export.
