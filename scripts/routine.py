"""Scan an RFID tag and switch to the Chromium tab mapped to it in preset.json.

Run scripts/start_kiosk.sh first. Every mapped page is preloaded at startup, so a tap only
switches tabs instead of loading a page."""

import json
import sys
import os
import time

os.environ.setdefault("DISPLAY", ":0")


from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from display.tabs import TabSwitcher
from hardware.rfid import RFIDReader

CONFIG = ROOT / "config" / "preset.json"


def main():
    tags = json.loads(CONFIG.read_text())["rfid_tags"]
    reader = RFIDReader()
    tabs = TabSwitcher()
    for url in tags.values():
        tabs.show(url)
        time.sleep(1)
    print("Scan a tag (Ctrl+C to quit)...")
    try:
        while True:
            uid = reader.wait_for_scan()
            url = tags.get(uid)
            if url is None:
                print(f"{uid}: unknown tag, ignoring")
                continue
            print(f"{uid}: showing {url}")
            tabs.show(url)
    except KeyboardInterrupt:
        print("\nDone.")
    finally:
        reader.close()


if __name__ == "__main__":
    main()
