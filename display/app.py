"""Display service: serves the /stage warp wrapper and pushes the active wall's corners to it.

Every Chromium tab loads /stage?u=<page>; the wrapper warps the page with a matrix3d built from the
corners it receives on /warp/stream, so all tabs re-warp together when the aim changes.
Run: python -m display.app
"""

import json
import os
import sys
import threading
from pathlib import Path

if not __package__:  # allow `python display/app.py` as well as `python -m display.app`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "display"

from flask import Flask, Response, jsonify, request, send_from_directory

from . import warp

ROOT = Path(__file__).resolve().parent.parent
PRESETS = ROOT / "config" / "presets.json"
PORT = int(os.environ.get("OSCAR_DISPLAY_PORT", 5000))


def check_corners(corners):
    ok = (isinstance(corners, list) and len(corners) == 4
          and all(isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) for v in p)
                  for p in corners))
    if not ok:
        raise ValueError("corners must be 4 [x, y] points")


class WarpState:
    """The active wall and its corners; readers block on `wait` until the version changes."""

    def __init__(self, walls):
        self.walls = walls
        self._cond = threading.Condition()
        self._version = 0
        self.wall = None
        self.corners = warp.UNIT_CORNERS

    def snapshot(self):
        return {"wall": self.wall, "corners": self.corners}

    def set(self, wall=None, corners=None):
        """Aim at a preset wall, or preview raw corners (calibration). Returns the snapshot."""
        if corners is None:
            if wall not in self.walls:
                raise KeyError(wall)
            corners = warp.wall_corners(self.walls[wall].get("warp", {}))
        else:
            check_corners(corners)
        with self._cond:
            self.wall, self.corners = wall, corners
            self._version += 1
            self._cond.notify_all()
        return self.snapshot()

    def wait(self, seen, timeout):
        """Block until the version differs from `seen`; return (version, snapshot)."""
        with self._cond:
            self._cond.wait_for(lambda: self._version != seen, timeout)
            return self._version, self.snapshot()


def _read_presets(path):
    path = Path(path)
    text = path.read_text().strip() if path.exists() else ""
    return json.loads(text) if text else {}


def load_walls(path=PRESETS):
    return _read_presets(path).get("walls", {})


def save_wall(path, wall, corners, angle_deg=None):
    """Write one wall's warp block into presets.json, leaving every other key as it was.

    Replaces any legacy rotate/perspective keys with the corners. Returns the wall's new block.
    """
    path = Path(path)
    data = _read_presets(path)
    block = data.setdefault("walls", {}).setdefault(wall, {})
    block["warp"] = {"corners": [[round(x, 4), round(y, 4)] for x, y in corners]}
    if angle_deg is not None:
        block["angle_deg"] = angle_deg
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)
    return block


def create_app(presets_path=PRESETS):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    state = WarpState(load_walls(presets_path))
    app.config["WARP"] = state

    @app.get("/stage")
    def stage():
        return send_from_directory(app.static_folder, "stage.html")

    @app.get("/warp")
    def get_warp():
        return jsonify(state.snapshot())

    @app.post("/warp")
    def set_warp():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not ("wall" in body or "corners" in body):
            return jsonify(error='expected JSON like {"wall": "..."} or {"corners": [...]}'), 400
        try:
            return jsonify(state.set(wall=body.get("wall"), corners=body.get("corners")))
        except KeyError:
            return jsonify(error=f"unknown wall {body.get('wall')!r}"), 404
        except ValueError as e:
            return jsonify(error=str(e)), 400

    @app.get("/calibrate")
    def calibrate():
        return send_from_directory(app.static_folder, "calibrate.html")

    @app.get("/walls")
    def walls():
        return jsonify({name: {"angle_deg": w.get("angle_deg"),
                               "corners": warp.wall_corners(w.get("warp", {}))}
                        for name, w in state.walls.items()})

    @app.post("/walls/<name>")
    def save(name):
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error='expected JSON like {"corners": [...], "angle_deg": 40}'), 400
        angle = body.get("angle_deg")
        try:
            check_corners(body.get("corners"))
            if angle is not None and not isinstance(angle, (int, float)):
                raise ValueError("angle_deg must be a number")
        except ValueError as e:
            return jsonify(error=str(e)), 400
        state.walls[name] = save_wall(presets_path, name, body["corners"], angle)
        return jsonify(state.walls[name])

    @app.get("/warp/stream")
    def stream():
        def events():
            seen = -1
            while True:
                seen, snap = state.wait(seen, timeout=15)
                yield f"data: {json.dumps(snap)}\n\n"

        return Response(events(), mimetype="text/event-stream",
                        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT, threaded=True)
