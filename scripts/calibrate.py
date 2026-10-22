"""Start calibrating a wall: show it on the projector and print the page to drag its corners on.

Usage: python scripts/calibrate.py <wall> [--host 127.0.0.1] [--port 5000]
Run `python -m display.app` first. Open the printed URL on a laptop or a phone on the LAN; the
projector previews every drag live, and Save writes that wall to config/presets.json.
Once hardware/turntable.py exists, move the turntable to the wall's angle here before previewing.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request


def post(url, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.load(resp)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wall")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    base = f"http://{args.host}:{args.port}"
    try:
        post(f"{base}/warp", {"wall": args.wall})
        print(f"Showing saved warp for '{args.wall}'.")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        print(f"'{args.wall}' has no saved warp yet; starting from the current one.")
    except urllib.error.URLError as e:
        sys.exit(f"Can't reach the display service at {base} ({e.reason}). Run: python -m display.app")
    print(f"Calibrate at: {base}/calibrate?wall={args.wall}")


if __name__ == "__main__":
    main()
