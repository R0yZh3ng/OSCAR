"""Scan an RFID tag and open the YouTube video mapped to it in presets.json."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hardware.rfid import RFIDReader

CONFIG = ROOT / "config" / "preset.json"


def main():
    tags = json.loads(CONFIG.read_text())["rfid_tags"]
    reader = RFIDReader()
    print("Scan a tag (Ctrl+C to quit)...")
    try:
        while True:
            uid = reader.wait_for_scan()
            url = tags.get(uid)
            if url is None:
                print(f"{uid}: unknown tag, ignoring")
                continue
            print(f"{uid}: opening {url}")
            subprocess.Popen(["chromium", url])
    except KeyboardInterrupt:
        print("\nDone.")
    finally:
        reader.close()


if __name__ == "__main__":
    main()
