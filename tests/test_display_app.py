import json
import tempfile
import unittest
from pathlib import Path

from display.app import WarpState, create_app, load_walls

WALLS = {
    "wall": {"angle_deg": 40, "warp": {"corners": [[0.04, 0.02], [0.97, 0.06], [0.96, 0.95], [0.02, 0.91]]}},
    "closet": {"angle_deg": 140, "warp": {"rotateY": 20}},
}


class AppTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        path = Path(self.dir.name) / "presets.json"
        path.write_text(json.dumps({"walls": WALLS}))
        self.client = create_app(path).test_client()

    def tearDown(self):
        self.dir.cleanup()

    def test_starts_unwarped(self):
        got = self.client.get("/warp").get_json()
        self.assertIsNone(got["wall"])
        self.assertEqual(got["corners"], [[0, 0], [1, 0], [1, 1], [0, 1]])

    def test_select_wall_uses_preset_corners(self):
        got = self.client.post("/warp", json={"wall": "wall"}).get_json()
        self.assertEqual(got["corners"], WALLS["wall"]["warp"]["corners"])
        self.assertEqual(self.client.get("/warp").get_json(), got)

    def test_legacy_wall_is_converted(self):
        got = self.client.post("/warp", json={"wall": "closet"}).get_json()
        self.assertEqual(len(got["corners"]), 4)
        self.assertNotEqual(got["corners"], [[0, 0], [1, 0], [1, 1], [0, 1]])

    def test_preview_raw_corners(self):
        corners = [[0, 0], [0.9, 0], [0.9, 1], [0, 1]]
        got = self.client.post("/warp", json={"corners": corners}).get_json()
        self.assertEqual(got["corners"], corners)

    def test_unknown_wall_404_and_state_unchanged(self):
        self.assertEqual(self.client.post("/warp", json={"wall": "attic"}).status_code, 404)
        self.assertIsNone(self.client.get("/warp").get_json()["wall"])

    def test_invalid_json_or_empty_body_400(self):
        r = self.client.post("/warp", data='{"corners": []}.', content_type="application/json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.client.post("/warp", json={}).status_code, 400)

    def test_bad_corners_400(self):
        self.assertEqual(self.client.post("/warp", json={"corners": [[0, 0]]}).status_code, 400)

    def test_stage_and_script_are_served(self):
        self.assertEqual(self.client.get("/stage?u=http://localhost:5001/").status_code, 200)
        self.assertEqual(self.client.get("/static/warp.js").status_code, 200)

    def test_missing_or_empty_presets_means_no_walls(self):
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "presets.json"
            self.assertEqual(load_walls(empty), {})
            empty.write_text("")
            self.assertEqual(load_walls(empty), {})


class WarpStateTest(unittest.TestCase):
    def test_wait_returns_after_set(self):
        state = WarpState(WALLS)
        state.set(wall="wall")
        version, snap = state.wait(-1, timeout=0.1)
        self.assertEqual(snap["wall"], "wall")
        # nothing new: times out and returns the same version
        self.assertEqual(state.wait(version, timeout=0.05)[0], version)


if __name__ == "__main__":
    unittest.main()
