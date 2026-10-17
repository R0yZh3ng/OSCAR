import os
import sqlite3
from datetime import date, datetime, timedelta

DAY_ROLLOVER_HOUR = 4  # before 4am still counts as "yesterday"

DB_PATH = os.environ.get(
    "OSCAR_TRACKER_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "tracker.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#6c8cff'
);
CREATE TABLE IF NOT EXISTS habits (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    icon TEXT NOT NULL DEFAULT '',
    category_id INTEGER REFERENCES categories(id),
    type TEXT NOT NULL DEFAULT 'check',      -- check | count | duration
    target REAL NOT NULL DEFAULT 1,
    unit TEXT NOT NULL DEFAULT '',
    difficulty INTEGER NOT NULL DEFAULT 1,   -- 1 easy, 2 medium, 3 hard
    weekdays TEXT NOT NULL DEFAULT '0,1,2,3,4,5,6',  -- Mon=0
    color TEXT NOT NULL DEFAULT '#6c8cff',
    time_of_day TEXT NOT NULL DEFAULT 'anytime',     -- morning | afternoon | evening | anytime
    start_date TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS entries (
    habit_id INTEGER NOT NULL REFERENCES habits(id),
    date TEXT NOT NULL,
    value REAL NOT NULL,
    xp INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'ui',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    PRIMARY KEY (habit_id, date)
);
CREATE TABLE IF NOT EXISTS skips (
    habit_id INTEGER NOT NULL REFERENCES habits(id),
    date TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT 'rest',
    PRIMARY KEY (habit_id, date)
);
CREATE TABLE IF NOT EXISTS bonus_xp (
    date TEXT NOT NULL,
    kind TEXT NOT NULL,                      -- perfect_day | quest | ...
    amount INTEGER NOT NULL,
    PRIMARY KEY (date, kind)
);
CREATE TABLE IF NOT EXISTS achievements (
    key TEXT PRIMARY KEY,
    unlocked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS moods (
    date TEXT PRIMARY KEY,
    mood INTEGER NOT NULL                    -- 1 (awful) .. 5 (great)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    action TEXT NOT NULL,
    args TEXT NOT NULL,
    source TEXT NOT NULL
);
"""


def connect(path=None):
    path = path or DB_PATH
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """Add columns introduced after the first release to existing databases."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(habits)")}
    for name, ddl in (("color", "TEXT NOT NULL DEFAULT '#6c8cff'"),
                      ("time_of_day", "TEXT NOT NULL DEFAULT 'anytime'")):
        if name not in cols:
            conn.execute(f"ALTER TABLE habits ADD COLUMN {name} {ddl}")
    conn.commit()


def today(now=None):
    now = now or datetime.now()
    return (now - timedelta(hours=DAY_ROLLOVER_HOUR)).date()


def iso(d):
    return d.isoformat() if isinstance(d, date) else d


def parse(s):
    return date.fromisoformat(s) if isinstance(s, str) else s
