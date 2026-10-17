import unittest
from datetime import date, timedelta

from tracker import actions, progression, stats
from tracker.db import connect

D0 = date(2026, 1, 1)


def day(n):
    return D0 + timedelta(days=n)


class ProgressionTests(unittest.TestCase):
    def test_level_curve_is_monotonic_and_starts_at_zero(self):
        self.assertEqual(progression.xp_for_level(1), 0)
        costs = [progression.xp_for_level(n) for n in range(1, 30)]
        self.assertEqual(costs, sorted(set(costs)))

    def test_level_info_boundaries(self):
        need = progression.xp_for_level(2)
        self.assertEqual(progression.level_info(need - 1)["level"], 1)
        self.assertEqual(progression.level_info(need)["level"], 2)

    def test_streak_bonus_capped(self):
        self.assertEqual(progression.streak_multiplier(0), 1)
        self.assertEqual(progression.streak_multiplier(30), progression.streak_multiplier(300))

    def test_overlogging_gives_no_extra_xp(self):
        self.assertEqual(progression.entry_xp(2, 8, 8, 0), progression.entry_xp(2, 80, 8, 0))


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")

    def run_action(self, name, args, n=0):
        return actions.dispatch(self.conn, name, args, today=day(n))

    def make(self, name="gym", **kw):
        return self.run_action("habit.create", {"name": name, "start_date": D0, **kw})["result"]["id"]

    def test_complete_awards_xp_and_undo_takes_it_back(self):
        self.make(difficulty=2)
        r = self.run_action("habit.complete", {"habit": "gym"})
        self.assertGreater(r["xp_delta"], 0)
        self.assertIn("first_log", [u["key"] for u in r["unlocked"]])
        u = self.run_action("habit.undo", {"habit": "GYM"})
        self.assertEqual(stats.total_xp(self.conn), 0)
        self.assertLess(u["xp_delta"], 0)

    def test_perfect_day_bonus_only_when_all_done_and_revoked_on_undo(self):
        self.make("a")
        self.make("b")
        self.run_action("habit.complete", {"habit": "a"})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM bonus_xp").fetchone()[0], 0)
        self.run_action("habit.complete", {"habit": "b"})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM bonus_xp").fetchone()[0], 1)
        self.run_action("habit.undo", {"habit": "b"})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM bonus_xp").fetchone()[0], 0)

    def test_streak_grows_xp_and_skip_is_neutral(self):
        self.make()
        xps = []
        for n in (0, 1, 2):
            r = self.run_action("habit.complete", {"habit": "gym"}, n)
            xps.append(r["xp_delta"])
        self.assertTrue(xps[2] >= xps[0])
        self.run_action("habit.skip", {"habit": "gym", "date": day(3).isoformat()}, 4)
        self.run_action("habit.complete", {"habit": "gym"}, 4)
        h = self.conn.execute("SELECT * FROM habits").fetchone()
        entries, skips = stats.habit_maps(self.conn, h["id"])
        self.assertEqual(stats.current_streak(h, entries, skips, day(4)), 4)

    def test_missed_day_resets_streak(self):
        self.make()
        self.run_action("habit.complete", {"habit": "gym"}, 0)
        self.run_action("habit.complete", {"habit": "gym"}, 2)
        h = self.conn.execute("SELECT * FROM habits").fetchone()
        entries, skips = stats.habit_maps(self.conn, h["id"])
        self.assertEqual(stats.current_streak(h, entries, skips, day(2)), 1)
        self.assertEqual(stats.best_streak(h, entries, skips, day(2)), 1)

    def test_count_habit_partial_credit_then_complete(self):
        self.make("water", type="count", target=8)
        self.run_action("habit.log", {"habit": "water", "value": 4})
        half = stats.total_xp(self.conn)
        r = self.run_action("habit.log", {"habit": "water", "value": 4})
        self.assertGreater(stats.total_xp(self.conn), half)
        self.assertTrue(actions.build_state(self.conn, day(0))["habits"][0]["done"])
        self.assertGreater(r["xp_delta"], 0)

    def test_level_up_reported(self):
        self.make(difficulty=3)
        for n in range(8):
            self.make(f"h{n}", difficulty=3)
        leveled = None
        for name in ["gym"] + [f"h{n}" for n in range(8)]:
            res = self.run_action("habit.complete", {"habit": name})
            leveled = leveled or res["level_up"]
        self.assertIsNotNone(leveled)
        self.assertEqual(leveled["to"], 2)

    def test_cannot_log_future(self):
        self.make()
        with self.assertRaises(actions.ActionError):
            self.run_action("habit.complete", {"habit": "gym", "date": day(5).isoformat()})

    def test_unknown_action_and_habit(self):
        with self.assertRaises(actions.ActionError):
            self.run_action("nope", {})
        with self.assertRaises(actions.ActionError):
            self.run_action("habit.complete", {"habit": "ghost"})


if __name__ == "__main__":
    unittest.main()


class VisualStatsTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        actions.dispatch(self.conn, "habit.create", {"name": "gym", "start_date": D0}, today=D0)
        self.h = self.conn.execute("SELECT * FROM habits").fetchone()

    def complete(self, n):
        actions.dispatch(self.conn, "habit.complete", {"habit": "gym"}, today=day(n))

    def strength(self, n):
        return stats.habit_detail(self.conn, self.h, day(n))["strength"]

    def test_strength_rises_with_reps_and_one_miss_barely_dents_it(self):
        for n in range(30):
            self.complete(n)
        peak = self.strength(29)
        self.assertGreater(peak, 0.8)
        after_miss = self.strength(31)  # day 30 was missed
        self.assertGreater(after_miss, peak - 0.1)
        self.assertLess(after_miss, peak)

    def test_calendar_statuses(self):
        self.complete(0)
        actions.dispatch(self.conn, "habit.skip", {"habit": "gym", "date": day(2).isoformat()}, today=day(3))
        cal = stats.habit_detail(self.conn, self.h, day(3))["calendar"]
        self.assertEqual([cal[day(i).isoformat()] for i in range(4)],
                         ["done", "missed", "skipped", "pending"])

    def test_update_note_mood_and_overview(self):
        self.complete(0)
        actions.dispatch(self.conn, "habit.update", {"habit": "gym", "name": "Lift", "color": "#fff"}, today=day(0))
        actions.dispatch(self.conn, "habit.note", {"habit": "Lift", "note": "PR!"}, today=day(0))
        actions.dispatch(self.conn, "mood.set", {"mood": 5}, today=day(0))
        o = stats.overview(self.conn, day(0))
        self.assertEqual(o["mood_rate"], {5: 1.0})
        self.assertEqual(o["ranking"][0]["name"], "Lift")
        self.assertEqual(stats.habit_detail(self.conn, self.h, day(0))["notes"][0]["note"], "PR!")
        with self.assertRaises(actions.ActionError):
            actions.dispatch(self.conn, "mood.set", {"mood": 9}, today=day(0))

    def test_build_state_view_date(self):
        self.complete(0)
        st = actions.build_state(self.conn, day(2), view=day(0))
        self.assertTrue(st["habits"][0]["done"])
        self.assertEqual(st["today"], day(2).isoformat())
        self.assertEqual(len(st["week"]), 7)
