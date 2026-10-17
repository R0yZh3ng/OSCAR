import os
import sys

if not __package__:  # allow `python tracker/app.py` as well as `python -m tracker.app`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "tracker"

from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO

from . import actions, stats
from .db import connect, parse, today

PORT = int(os.environ.get("OSCAR_TRACKER_PORT", 5001))

socketio = SocketIO(cors_allowed_origins="*")


def create_app(db_path=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["DB_PATH"] = db_path
    socketio.init_app(app)

    def db():
        return connect(app.config["DB_PATH"])

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/state")
    def state():
        conn = db()
        try:
            view = request.args.get("date")
            return jsonify(actions.build_state(conn, view=parse(view) if view else None))
        finally:
            conn.close()

    @app.get("/api/habits/<int:habit_id>")
    def habit_detail(habit_id):
        conn = db()
        try:
            h = conn.execute("SELECT * FROM habits WHERE id=?", (habit_id,)).fetchone()
            if not h:
                return jsonify({"error": "no such habit"}), 404
            return jsonify(stats.habit_detail(conn, h, today()))
        finally:
            conn.close()

    @app.get("/api/stats")
    def overview():
        conn = db()
        try:
            return jsonify(stats.overview(conn, today()))
        finally:
            conn.close()

    @app.post("/api/actions")
    def run_action():
        body = request.get_json(force=True)
        conn = db()
        try:
            out = actions.dispatch(conn, body["action"], body.get("args"), body.get("source", "api"))
            view = body.get("view")
            state = actions.build_state(conn, view=parse(view) if view else None)
        except actions.ActionError as e:
            return jsonify({"error": str(e)}), 400
        except KeyError as e:
            return jsonify({"error": f"missing field: {e}"}), 400
        finally:
            conn.close()
        socketio.emit("state_changed", {"source": body.get("source", "api")})
        return jsonify({**out, "state": state})

    return app


if __name__ == "__main__":
    socketio.run(create_app(), host="0.0.0.0", port=PORT, allow_unsafe_werkzeug=True)
