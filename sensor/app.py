import json
import os
import sys
import time
import wave

if not __package__:  # allow `python sensor/app.py` as well as `python -m sensor.app`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    __package__ = "sensor"

from flask import Flask, jsonify, send_from_directory
from flask_socketio import SocketIO

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sensor.json")
DATA_DIR = os.environ.get("OSCAR_SENSOR_DATA", os.path.join(ROOT, "voice", "model", "data"))
PORT = int(os.environ.get("OSCAR_SENSOR_PORT", 5002))
CERT = os.environ.get("OSCAR_SENSOR_CERT", os.path.join(ROOT, "data", "certs", "sensor.crt"))
KEY = os.environ.get("OSCAR_SENSOR_KEY", os.path.join(ROOT, "data", "certs", "sensor.key"))
RATE = 16000
NS = "/sensor"

socketio = SocketIO(cors_allowed_origins="*", max_http_buffer_size=4_000_000)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def write_wav(path, pcm):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)


def safe_label(label, allowed):
    return label if label in allowed else None


def create_app(data_dir=None):
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["DATA_DIR"] = data_dir or DATA_DIR
    socketio.init_app(app)
    streams = {}  # sid -> bytearray, the live "stream to WAV" test capture

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "sensor.html")

    @app.get("/api/config")
    def config():
        return jsonify(load_config())

    @socketio.on("connect", namespace=NS)
    def on_connect():
        socketio.emit("sensor_control", {"mic": load_config().get("mic_on_boot", False)},
                      namespace=NS, to=None)

    @socketio.on("disconnect", namespace=NS)
    def on_disconnect():
        from flask import request
        streams.pop(request.sid, None)

    # Step 2: raw stream -> one WAV, for judging phone-mic quality by ear.
    @socketio.on("stream_start", namespace=NS)
    def stream_start():
        from flask import request
        streams[request.sid] = bytearray()

    @socketio.on("audio", namespace=NS)
    def audio(chunk):
        from flask import request
        buf = streams.get(request.sid)
        if buf is not None:
            buf.extend(chunk)

    @socketio.on("stream_stop", namespace=NS)
    def stream_stop():
        from flask import request
        buf = streams.pop(request.sid, None)
        if not buf:
            return {"ok": False}
        path = os.path.join(app.config["DATA_DIR"], "streams", time.strftime("%Y%m%d-%H%M%S") + ".wav")
        write_wav(path, bytes(buf))
        return {"ok": True, "path": os.path.relpath(path, ROOT), "seconds": len(buf) / 2 / RATE}

    # Step 3: labeled clips -> voice/model/data/raw/<label>/
    @socketio.on("clip", namespace=NS)
    def clip(label, pcm):
        cfg = load_config()
        allowed = set(cfg["keywords"]) | {cfg["background_label"]}
        if not safe_label(label, allowed) or not pcm:
            return {"ok": False, "error": "bad label or empty clip"}
        name = "%s-%d.wav" % (label, time.time() * 1000)
        path = os.path.join(app.config["DATA_DIR"], "raw", label, name)
        write_wav(path, bytes(pcm))
        count = len(os.listdir(os.path.dirname(path)))
        return {"ok": True, "path": os.path.relpath(path, ROOT), "count": count}

    @socketio.on("counts", namespace=NS)
    def counts():
        cfg = load_config()
        out = {}
        for label in cfg["keywords"] + [cfg["background_label"]]:
            d = os.path.join(app.config["DATA_DIR"], "raw", label)
            out[label] = len(os.listdir(d)) if os.path.isdir(d) else 0
        return out

    return app


def main():
    app = create_app()
    ssl = (CERT, KEY) if os.path.exists(CERT) and os.path.exists(KEY) else None
    if not ssl:
        print("WARNING: no TLS cert at %s; iOS Safari will refuse the mic over plain HTTP.\n"
              "Run scripts/make_sensor_cert.sh or set OSCAR_SENSOR_CERT/OSCAR_SENSOR_KEY." % CERT)
    socketio.run(app, host="0.0.0.0", port=PORT, ssl_context=ssl, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
