import unittest
from datetime import date
from types import SimpleNamespace as NS

from assistant.agent import Assistant
from assistant.tools import Tools
from assistant.wake import split_wake
from tracker import actions
from tracker.db import connect

TODAY = date(2026, 10, 23)


def text(t):
    return NS(type="text", text=t)


def call(id, name, **args):
    return NS(type="tool_use", id=id, name=name, input=args)


def resp(*blocks, stop="end_turn"):
    return NS(content=list(blocks), stop_reason=stop)


class FakeClient:
    """Plays back scripted responses and records the requests."""
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []
        self.messages = self

    def create(self, **kw):
        self.requests.append(dict(kw, messages=list(kw["messages"])))
        return self.responses.pop(0)


class FakeTabs:
    def __init__(self):
        self.shown = []

    def show(self, url):
        self.shown.append(url)


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        actions.dispatch(self.conn, "habit.create", {"name": "Gym"}, today=TODAY)
        actions.dispatch(self.conn, "habit.create", {"name": "Read", "type": "count", "target": 30, "unit": "min"}, today=TODAY)
        self.tabs = FakeTabs()
        self.tools = Tools(self.conn, tabs=self.tabs, pages={"dashboard": "http://x/"}, today=TODAY,
                           wake_pc=lambda: "unlocked")

    def test_complete_and_list(self):
        out, err = self.tools.call("complete_habit", {"habit": "gym"})
        self.assertFalse(err)
        self.assertIn("completed gym", out)
        self.assertIn("Gym: done", self.tools.call("list_habits", {})[0])

    def test_log_count_habit(self):
        out, _ = self.tools.call("log_habit", {"habit": "Read", "value": 10})
        self.assertIn("logged 10", out)
        self.assertIn("Read: 10/30 min", self.tools.call("list_habits", {})[0])

    def test_unknown_habit_is_an_error_not_a_crash(self):
        out, err = self.tools.call("complete_habit", {"habit": "yoga"})
        self.assertTrue(err)
        self.assertIn("no such habit", out)

    def test_show_page_by_name_and_url(self):
        self.assertFalse(self.tools.call("show_page", {"page": "Dashboard"})[1])
        self.assertFalse(self.tools.call("show_page", {"page": "https://example.com"})[1])
        self.assertEqual(self.tabs.shown, ["http://x/", "https://example.com"])
        self.assertTrue(self.tools.call("show_page", {"page": "nonsense"})[1])

    def test_wake_pc_and_bad_args(self):
        self.assertEqual(self.tools.call("wake_pc", {}), ("PC wake result: unlocked", False))
        self.assertTrue(self.tools.call("log_habit", {"habit": "Read"})[1])  # missing value

    def test_schemas_match_handlers(self):
        for s in self.tools.schemas():
            self.assertTrue(hasattr(self.tools, "t_" + s["name"]), s["name"])


class AssistantTest(unittest.TestCase):
    def setUp(self):
        self.conn = connect(":memory:")
        actions.dispatch(self.conn, "habit.create", {"name": "Gym"}, today=TODAY)
        self.tools = Tools(self.conn, pages={}, today=TODAY)

    def test_tool_loop_runs_tool_then_answers(self):
        client = FakeClient(resp(call("t1", "complete_habit", habit="gym"), stop="tool_use"),
                            resp(text("Marked gym done.")))
        bot = Assistant(self.tools, client=client)
        self.assertEqual(bot.ask("I did the gym"), "Marked gym done.")
        result = client.requests[1]["messages"][-1]["content"][0]
        self.assertEqual(result["tool_use_id"], "t1")
        self.assertFalse(result["is_error"])
        self.assertIn("Gym: done", self.tools.call("list_habits", {})[0])

    def test_failed_tool_result_is_flagged(self):
        client = FakeClient(resp(call("t1", "complete_habit", habit="yoga"), stop="tool_use"),
                            resp(text("I don't have a yoga habit.")))
        Assistant(self.tools, client=client).ask("did yoga")
        self.assertTrue(client.requests[1]["messages"][-1]["content"][0]["is_error"])

    def test_history_resets_after_idle(self):
        now = [0]
        client = FakeClient(resp(text("a")), resp(text("b")), resp(text("c")))
        bot = Assistant(self.tools, client=client, idle_reset=60, clock=lambda: now[0])
        bot.ask("one")
        now[0] = 30
        bot.ask("two")
        self.assertEqual(len(client.requests[1]["messages"]), 3)
        now[0] = 500
        bot.ask("three")
        self.assertEqual(len(client.requests[2]["messages"]), 1)

    def test_refusal_and_runaway_loop_are_contained(self):
        bot = Assistant(self.tools, client=FakeClient(resp(stop="refusal")))
        self.assertIn("can't", bot.ask("x"))
        loop = [resp(call(f"t{i}", "list_habits"), stop="tool_use") for i in range(20)]
        self.assertIn("too many", Assistant(self.tools, client=FakeClient(*loop)).ask("x"))


class WakeTest(unittest.TestCase):
    def test_commands(self):
        cases = {
            "Oscar, show the dashboard": "show the dashboard",
            "hey oscar mark gym done.": "mark gym done",
            "Oskar log 20 minutes of reading": "log 20 minutes of reading",
            "show my schedule oscar": "show my schedule",
            "Oscar": "",
            "Okay Oscar, wake up the PC": "wake up the PC",
        }
        for heard, cmd in cases.items():
            self.assertEqual(split_wake(heard), cmd, heard)

    def test_ignores_other_speech(self):
        for heard in ["what time is dinner", "I saw Oscar yesterday at the park", "", "oscars are on tonight"]:
            self.assertIsNone(split_wake(heard), heard)



class ListenerTest(unittest.TestCase):
    @staticmethod
    def tone(seconds, amp=8000):
        import array, math
        n = int(seconds * 16000)
        return array.array("h", [int(amp * math.sin(i * 0.3)) for i in range(n)]).tobytes()

    @staticmethod
    def silence(seconds):
        return bytes(int(seconds * 16000) * 2)

    def run_listener(self, transcripts, audio):
        from assistant.listener import Listener
        said = list(transcripts)
        asked = []
        L = Listener(lambda pcm: said.pop(0), lambda t: asked.append(t) or "ok " + t)
        out = []
        for chunk in audio:
            out += L.feed(chunk)
        return out, asked

    def test_segmenter_splits_on_silence_and_ignores_blips(self):
        from assistant.listener import Segmenter
        s = Segmenter()
        utts = s.feed(self.silence(1) + self.tone(1) + self.silence(1) + self.tone(0.05) + self.silence(1) + self.tone(0.6) + self.silence(1))
        self.assertEqual(len(utts), 2)

    def test_wake_then_command(self):
        speech = self.silence(1) + self.tone(1) + self.silence(1)
        out, asked = self.run_listener(["Oscar mark gym done"], [speech])
        self.assertEqual(asked, ["mark gym done"])
        self.assertEqual(out[0][1], "ok mark gym done")

    def test_bare_name_arms_followup_and_chatter_is_ignored(self):
        speech = self.silence(1) + self.tone(1) + self.silence(1)
        out, asked = self.run_listener(["what's for dinner", "Oscar", "show the dashboard"], [speech] * 3)
        self.assertEqual(asked, ["show the dashboard"])
        self.assertEqual([r for _, r in out], ["Yes?", "ok show the dashboard"])




if __name__ == "__main__":
    unittest.main()
