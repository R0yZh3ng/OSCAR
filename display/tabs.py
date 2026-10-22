"""Switch between already-loaded Chromium tabs over its remote-debugging HTTP endpoint.

Chromium must be started with --remote-debugging-port (see scripts/start_kiosk.sh). Activating a
loaded tab is instant; opening a page only happens the first time a URL is seen.
"""

import json
import urllib.request
from urllib.parse import parse_qs, quote, urlsplit

PORT = 9222
STAGE = "http://localhost:5000"  # display/app.py, which serves the /stage warp wrapper


def _http(method, url):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=3) as resp:
        return resp.read().decode()


def stage_url(url, stage=STAGE):
    """Wrap url so it loads inside the warp wrapper (docs/PROJECTION_PLAN.md)."""
    return f"{stage}/stage?u={quote(url, safe='')}"


def unwrap(url):
    """The page inside a /stage URL; any other URL is returned unchanged."""
    parts = urlsplit(url)
    if parts.path == "/stage":
        inner = parse_qs(parts.query).get("u")
        if inner:
            return inner[0]
    return url


class TabSwitcher:
    """With `stage` set, pages open inside the warp wrapper but are still matched by their own URL."""

    def __init__(self, port=PORT, http=_http, stage=None):
        self._base = f"http://127.0.0.1:{port}"
        self._http = http
        self._stage = stage

    def tabs(self):
        return [t for t in json.loads(self._http("GET", self._base + "/json/list")) if t.get("type") == "page"]

    def find(self, url):
        """Find a loaded tab for url: exact match first, then same page ignoring query.

        SPA hash routes (e.g. the tracker's /#/year) are distinct tabs, so a wanted URL with a
        fragment only matches that fragment. One without a fragment may match any tab on that page.
        """
        def split(u):
            base, _, frag = u.partition("#")
            return base.split("?")[0].rstrip("/"), frag

        # a wrapped tab's own URL is the /stage one, so compare the page inside it
        tabs = [dict(t, url=unwrap(t["url"])) for t in self.tabs()]
        for t in tabs:
            if t["url"].rstrip("/") == url.rstrip("/"):
                return t
        wbase, wfrag = split(url)
        for t in tabs:
            if split(t["url"]) == (wbase, wfrag):
                return t
        if not wfrag:
            for t in tabs:
                if split(t["url"])[0] == wbase:
                    return t
        return None

    def show(self, url):
        """Bring url to the front, opening it if it isn't loaded. Returns True if it was already loaded."""
        tab = self.find(url)
        if tab:
            self._http("GET", f"{self._base}/json/activate/{tab['id']}")
            return True
        # urllib drops '#...' from a request URL, so escape it for Chromium to read back
        target = stage_url(url, self._stage) if self._stage else url
        self._http("PUT", f"{self._base}/json/new?{target.replace('#', '%23')}")
        return False

    def close(self, url):
        tab = self.find(url)
        if tab:
            self._http("GET", f"{self._base}/json/close/{tab['id']}")
        return bool(tab)
