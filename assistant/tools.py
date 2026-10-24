"""What the assistant can do. Each tool is a thin wrapper over an existing OSCAR module.

Dependencies are injected (db connection, tab switcher, PC wake) so the tools run in tests with
no hardware. Tool results are plain strings the model reads back to you.
"""

import json
from pathlib import Path

from tracker import actions, stats
from tracker.db import iso

ROOT = Path(__file__).resolve().parent.parent
PRESET = ROOT / "config" / "preset.json"

# name -> (description, json-schema properties, required)
SPECS = {
    "list_habits": ("List today's habits with progress, streaks and level.", {}, []),
    "complete_habit": ("Mark a check-type habit done for today (or a past date).",
                       {"habit": {"type": "string"}, "date": {"type": "string", "description": "YYYY-MM-DD, optional"}},
                       ["habit"]),
    "log_habit": ("Add an amount to a count/duration habit (e.g. 20 minutes of reading).",
                  {"habit": {"type": "string"}, "value": {"type": "number"}}, ["habit", "value"]),
    "undo_habit": ("Clear today's entry for a habit.", {"habit": {"type": "string"}}, ["habit"]),
    "skip_habit": ("Skip a habit today (rest day) without breaking its streak.",
                   {"habit": {"type": "string"}}, ["habit"]),
    "show_page": ("Put a page on the wall projector. `page` is a name from list_pages or a URL.",
                  {"page": {"type": "string"}}, ["page"]),
    "list_pages": ("List the named pages that can be shown on the wall.", {}, []),
    "wake_pc": ("Wake the desktop PC from sleep and unlock it.", {}, []),
}


class Tools:
    def __init__(self, conn, tabs=None, wake_pc=None, pages=None, today=None):
        self.conn, self.tabs, self._wake_pc, self._today = conn, tabs, wake_pc, today
        self.pages = pages if pages is not None else self._load_pages()

    @staticmethod
    def _load_pages(path=PRESET):
        cfg = json.loads(Path(path).read_text())
        return dict(cfg.get("pages", {})) or {f"tag {uid}": url for uid, url in cfg["rfid_tags"].items()}

    def schemas(self):
        return [{"name": n, "description": d,
                 "input_schema": {"type": "object", "properties": p, "required": r,
                                  "additionalProperties": False}}
                for n, (d, p, r) in SPECS.items()]

    def call(self, name, args):
        """Returns (text, is_error). Never raises: the model should see failures and explain them."""
        try:
            return getattr(self, "t_" + name)(**args), False
        except (actions.ActionError, ValueError, KeyError, TypeError, AttributeError, OSError) as e:
            return f"{type(e).__name__}: {e}", True

    def _dispatch(self, name, args):
        return actions.dispatch(self.conn, name, args, source="assistant", today=self._today)

    def t_list_habits(self):
        s = actions.build_state(self.conn, today=self._today)
        lines = [f"Level {s['level']['level']} ({s['level']['title']}), "
                 f"{s['today_progress']['done']}/{s['today_progress']['total']} done today"]
        for h in s["habits"]:
            if not h["scheduled_today"]:
                continue
            status = "done" if h["done"] else "skipped" if h["skipped_today"] else f"{h['value']:g}/{h['target']:g} {h['unit']}".strip()
            lines.append(f"- {h['name']}: {status}, streak {h['streak']}")
        return "\n".join(lines)

    def t_complete_habit(self, habit, date=None):
        r = self._dispatch("habit.complete", {"habit": habit, **({"date": date} if date else {})})
        return self._summary("completed " + habit, r)

    def t_log_habit(self, habit, value):
        return self._summary(f"logged {value:g} for {habit}", self._dispatch("habit.log", {"habit": habit, "value": value}))

    def t_undo_habit(self, habit):
        return self._summary("cleared " + habit, self._dispatch("habit.undo", {"habit": habit}))

    def t_skip_habit(self, habit):
        return self._summary("skipped " + habit, self._dispatch("habit.skip", {"habit": habit}))

    @staticmethod
    def _summary(msg, r):
        extra = [f"+{r['xp_delta']} XP"] if r["xp_delta"] else []
        if r["level_up"]:
            extra.append(f"LEVEL UP to {r['level_up']['to']} ({r['level_up']['title']})")
        extra += [f"unlocked: {u['title']}" for u in r["unlocked"]]
        return msg + (" (" + ", ".join(extra) + ")" if extra else "")

    def t_list_pages(self):
        return "\n".join(f"- {n}: {u}" for n, u in self.pages.items()) or "no named pages"

    def t_show_page(self, page):
        if self.tabs is None:
            raise OSError("no display connected")
        url = self.pages.get(page) or next((u for n, u in self.pages.items() if n.lower() == page.lower()), None)
        if url is None:
            if not page.startswith(("http://", "https://")):
                raise ValueError(f"unknown page {page!r}; known: {', '.join(self.pages)}")
            url = page
        self.tabs.show(url)
        return "showing " + url

    def t_wake_pc(self):
        if self._wake_pc is None:
            raise OSError("PC wake not configured")
        return "PC wake result: " + self._wake_pc()
