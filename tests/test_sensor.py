import os
import time
import tempfile
import unittest
import wave

from sensor import app as sensor_app


class SensorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = sensor_app.create_app(self.tmp.name)
        self.client = sensor_app.socketio.test_client(self.app, namespace=sensor_app.NS)

    def test_clip_writes_labeled_wav(self):
        pcm = b"\x01\x00" * 16000
        r = self.client.emit("clip", "oscar", pcm, namespace=sensor_app.NS, callback=True)
        self.assertTrue(r["ok"])
        d = os.path.join(self.tmp.name, "raw", "oscar")
        (name,) = os.listdir(d)
        with wave.open(os.path.join(d, name)) as w:
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getnframes()), (16000, 1, 16000))

    def test_clip_rejects_unknown_label(self):
        r = self.client.emit("clip", "../evil", b"\x00\x00", namespace=sensor_app.NS, callback=True)
        self.assertFalse(r["ok"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "raw")))

    def test_stream_saves_wav(self):
        self.client.emit("stream_start", namespace=sensor_app.NS)
        self.client.emit("audio", b"\x00\x00" * 8000, namespace=sensor_app.NS)
        r = self.client.emit("stream_stop", namespace=sensor_app.NS, callback=True)
        self.assertTrue(r["ok"])
        self.assertAlmostEqual(r["seconds"], 0.5)


class ListenTest(unittest.TestCase):
    def test_audio_reaches_listener_and_reply_comes_back(self):
        class Fake:
            def feed(self, pcm):
                return [("oscar hi", "hello %d" % len(pcm))]

        app = sensor_app.create_app(tempfile.mkdtemp(), make_listener=Fake)
        c = sensor_app.socketio.test_client(app, namespace=sensor_app.NS)
        self.assertTrue(c.emit("listen_start", namespace=sensor_app.NS, callback=True)["ok"])
        c.emit("listen_audio", b"\x00\x00" * 10, namespace=sensor_app.NS)
        for _ in range(50):
            got = [m for m in c.get_received(sensor_app.NS) if m["name"] == "assistant_reply"]
            if got:
                break
            time.sleep(0.05)
        self.assertEqual(got[0]["args"][0], {"heard": "oscar hi", "reply": "hello 20"})
        c.emit("listen_stop", namespace=sensor_app.NS)

    def test_disabled_by_default(self):
        app = sensor_app.create_app(tempfile.mkdtemp())
        c = sensor_app.socketio.test_client(app, namespace=sensor_app.NS)
        self.assertFalse(c.emit("listen_start", namespace=sensor_app.NS, callback=True)["ok"])


if __name__ == "__main__":
    unittest.main()
