"""C3: the browser state line states the call's failed requests, dialogs and downloads (switch, off by default).

Real Chromium through Playwright, as in ``test_core_browser_session_e2e``. The fixture page raises an alert, loads a
missing image (HTTP 404), fetches from a closed port (network failure) and offers a file the next call downloads.
The alert must still be dismissed as Playwright does by default (the call goes on to read the title): recording a
dialog must not change how it is handled. Known-bad: with page facts off the same calls state none of it, while
console errors are still listed as before.
"""

import asyncio
import http.server
import importlib.util
import os
import signal
import socket
import threading

import pytest

from aether.core import browser
from tests.test_core_browser_operation_faults_e2e import local_host

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None or not os.path.exists("/proc/self/stat"),
    reason="needs Linux with Playwright and Chromium (the browser fixture image)")


def closed_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class App(http.server.BaseHTTPRequestHandler):
    dead = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/file":
            body, headers = b"report-body", [("Content-Disposition", 'attachment; filename="report.csv"'),
                                              ("Content-Type", "text/csv")]
        elif self.path == "/page":
            body = (f"<html><head><title>Facts</title></head><body><a id=dl href=/file>get</a>"
                    f"<img src=/missing.png><script>console.error('page-console-error');"
                    f"fetch('http://127.0.0.1:{App.dead}/x').catch(()=>{{}});alert('hello-dialog')</script>"
                    f"</body></html>").encode()
            headers = [("Content-Type", "text/html")]
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        for key, value in headers:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def app():
    App.dead = closed_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), App)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def calls(tmp_path, app, page_facts):
    os.environ["AETHER_BROWSER_HOME"] = str(tmp_path / "home")
    session = browser.BrowserSession(None, None, host=local_host, persistent=True, page_facts=page_facts)
    car = browser.Sidecar("c" * 64, local_host)
    car.started, car.runs.ops_dir = True, str(tmp_path / "ops")
    session.sidecar = car

    async def go():
        try:
            load = await session.use({"code": "from aether_browser import page\npg = page()\n"
                                              f"pg.goto({app + '/page'!r})\npg.wait_for_timeout(800)\n"
                                              "print('title', pg.title())", "wait_s": 60}, 600.0)
            fetch = await session.use({"code": "from aether_browser import page\npg = page()\n"
                                               "with pg.expect_download() as got:\n    pg.click('#dl')\n"
                                               "print('downloaded', got.value.suggested_filename)",
                                       "wait_s": 60}, 600.0)
            return load, fetch
        finally:
            pid = tmp_path / "home" / "chrome.pid"
            if pid.exists():
                os.kill(int(pid.read_text()), signal.SIGKILL)

    return asyncio.run(go())


def test_failed_requests_dialogs_and_downloads_are_stated(tmp_path, app):
    load, fetch = calls(tmp_path, app, page_facts=True)
    state = load.splitlines()[-1]
    assert "title Facts" in load  # the alert was dismissed as before; the page went on
    assert "dialogs during this call: alert 'hello-dialog'" in state, state
    assert "HTTP 404 GET" in state and "/missing.png" in state, state
    assert f"127.0.0.1:{App.dead}/x (net::" in state, state
    assert "page-console-error" in state
    assert "downloads during this call: report.csv from" in fetch.splitlines()[-1], fetch


def test_known_bad_without_page_facts_none_of_it_is_stated(tmp_path, app):
    load, fetch = calls(tmp_path, app, page_facts=False)
    state = load.splitlines()[-1]
    assert "title Facts" in load and "page-console-error" in state  # stock line unchanged
    assert "dialogs" not in state and "failed requests" not in state and "downloads" not in fetch


def test_the_switch_only_changes_the_flag_in_the_installed_module():
    from aether.core import browser_session_src as src
    off, on = src.source(False), src.source(True)
    assert off == src.SOURCE and "_PAGE_FACTS = True" in on
    assert [a for a, b in zip(off.splitlines(), on.splitlines()) if a != b] == ["_PAGE_FACTS = False"]
