import json
import unittest

from display.tabs import TabSwitcher


class FakeChromium:
    def __init__(self, tabs):
        self.tabs = tabs
        self.calls = []

    def __call__(self, method, url):
        self.calls.append((method, url.split("9222")[1]))
        if url.endswith("/json/list"):
            return json.dumps(self.tabs)
        return ""


class TabSwitcherTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeChromium([
            {"id": "A", "type": "page", "url": "https://calendar.notion.com/?user=1#x"},
            {"id": "B", "type": "page", "url": "https://app.notion.com/p/todo"},
            {"id": "W", "type": "service_worker", "url": "https://app.notion.com/p/todo"},
        ])
        self.sw = TabSwitcher(http=self.fake)

    def test_activates_loaded_tab(self):
        self.assertTrue(self.sw.show("https://app.notion.com/p/todo/"))
        self.assertEqual(self.fake.calls[-1], ("GET", "/json/activate/B"))

    def test_matches_ignoring_query_and_fragment(self):
        self.assertTrue(self.sw.show("https://calendar.notion.com/?notionUserId=9"))
        self.assertEqual(self.fake.calls[-1], ("GET", "/json/activate/A"))

    def test_opens_new_tab_first_time_only(self):
        self.assertFalse(self.sw.show("https://example.com/"))
        self.assertEqual(self.fake.calls[-1], ("PUT", "/json/new?https://example.com/"))

    def test_hash_routes_are_separate_tabs(self):
        self.fake.tabs = [
            {"id": "T1", "type": "page", "url": "http://localhost:5001/#/year"},
            {"id": "T0", "type": "page", "url": "http://localhost:5001/"},
        ]
        self.assertTrue(self.sw.show("http://localhost:5001/"))
        self.assertEqual(self.fake.calls[-1], ("GET", "/json/activate/T0"))
        self.assertTrue(self.sw.show("http://localhost:5001/#/year"))
        self.assertEqual(self.fake.calls[-1], ("GET", "/json/activate/T1"))
        self.assertFalse(self.sw.show("http://localhost:5001/#/streaks"))
        self.assertEqual(self.fake.calls[-1], ("PUT", "/json/new?http://localhost:5001/%23/streaks"))

    def test_ignores_non_page_targets(self):
        self.assertEqual([t["id"] for t in self.sw.tabs()], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
