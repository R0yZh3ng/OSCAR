import tempfile
import unittest
from pathlib import Path

from tracker.app import create_app


class MusicTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.music = root / "music"
        self.music.mkdir()
        (root / "secret.mp3").write_bytes(b"outside")
        self.client = create_app(db_path=str(root / "t.db"), music_dir=str(self.music)).test_client()

    def get(self, url):
        resp = self.client.get(url)
        self.addCleanup(resp.close)
        return resp

    def test_lists_only_audio_files_sorted(self):
        for name in ("b.MP3", "a.ogg", "notes.txt"):
            (self.music / name).write_bytes(b"x")
        self.assertEqual(self.get("/api/music").get_json(), ["a.ogg", "b.MP3"])

    def test_missing_folder_means_no_music(self):
        self.music.rmdir()
        self.assertEqual(self.get("/api/music").get_json(), [])

    def test_serves_a_track(self):
        (self.music / "rain song.mp3").write_bytes(b"audio")
        self.assertEqual(self.get("/music/rain%20song.mp3").data, b"audio")

    def test_cannot_leave_the_music_folder_or_fetch_other_files(self):
        (self.music / "notes.txt").write_bytes(b"x")
        self.assertEqual(self.get("/music/../secret.mp3").status_code, 404)
        self.assertEqual(self.get("/music/notes.txt").status_code, 404)


if __name__ == "__main__":
    unittest.main()
