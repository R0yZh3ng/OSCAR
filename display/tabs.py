"""Switch between already-loaded Chromium tabs over its remote-debugging HTTP endpoint.

Chromium must be started with --remote-debugging-port (see scripts/start_kiosk.sh). Activating a
loaded tab is instant; opening a page only happens the first time a URL is seen.
"""

import json
import urllib.request

PORT = 9222


def _http(method, url):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=3) as resp:
        return resp.read().decode()


class TabSwitcher:
    def __init__(self, port=PORT, http=_http):
        self._base = f"http://127.0.0.1:{port}"
        self._http = http

    def tabs(self):
        return [t for t in json.loads(self._http("GET", self._base + "/json/list")) if t.get("type") == "page"]

    def find(self, url):
        """Match a loaded tab by URL prefix, ignoring any redirect-added query/fragment."""
        want = url.split("#")[0].split("?")[0].rstrip("/")
        for t in self.tabs():
            have = t["url"].split("#")[0].split("?")[0].rstrip("/")
            if have == want or t["url"].startswith(url):
                return t
        return None

    def show(self, url):
        """Bring url to the front, opening it if it isn't loaded. Returns True if it was already loaded."""
        tab = self.find(url)
        if tab:
            self._http("GET", f"{self._base}/json/activate/{tab['id']}")
            return True
        self._http("PUT", f"{self._base}/json/new?{url}")
        return False

    def close(self, url):
        tab = self.find(url)
        if tab:
            self._http("GET", f"{self._base}/json/close/{tab['id']}")
        return bool(tab)
