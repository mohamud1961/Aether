"""One browser kept open across browser calls (AETHER_CORE_BROWSER=session), against a local fixture web app.

Real Chromium through Playwright, real processes: the sidecar's ``docker exec``/``docker cp`` run as local processes
(``local_host`` from the fault sweep), so every call is a separate Python process, as in the sidecar. The fixture app
has a login form that sets a cookie, a page behind it whose list item appears 0.8 s after a click, an iframe with its
own button, and a console error.

The job: sign in, add an item, press the button inside the frame. Each step is its own browser call, written only
from what earlier calls printed (refs are parsed from the printed snapshot), as a model would.
Known-bad: the same calls without the kept browser lose the page and the login between calls.
"""

import asyncio
import http.server
import importlib.util
import os
import re
import signal
import threading

import pytest

from aether.core import browser
from tests.test_core_browser_operation_faults_e2e import local_host

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None or not os.path.exists("/proc/self/stat"),
    reason="needs Linux with Playwright and Chromium (the browser fixture image)")

LOGIN = b"""<html><head><title>Sign in</title></head><body>
<form method=post action=/login><label>Username <input name=u></label><label>Password <input name=p type=password>
</label><button type=submit>Sign in</button></form></body></html>"""
APP = b"""<html><head><title>Items</title></head><body><h1>Items</h1><ul id=items></ul>
<button onclick="setTimeout(()=>{const li=document.createElement('li');li.textContent='item one';
document.getElementById('items').appendChild(li)},800)">Add item</button>
<iframe srcdoc="<button onclick=&quot;parent.document.title='frame pressed'&quot;>Frame button</button>"></iframe>
<script>console.error('fixture-console-error')</script></body></html>"""


class App(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, body, status=200, headers=()):
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/app":
            if "session=ada" not in (self.headers.get("Cookie") or ""):
                return self._send(b"", 303, [("Location", "/login")])
            return self._send(APP)
        return self._send(LOGIN)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        if "u=ada" in body and "p=pw" in body:
            return self._send(b"", 303, [("Location", "/app"), ("Set-Cookie", "session=ada; Path=/")])
        return self._send(LOGIN, 401)


@pytest.fixture()
def app():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), App)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def refs(text):
    """``{described element: ref}`` from a printed snapshot, as a model reads it."""
    found = {}
    for line in text.splitlines():
        m = re.match(r'\s*- (\w+) "([^"]*)".*\[ref=([a-z0-9]+)\]', line)
        if m:
            found[f'{m.group(1)} "{m.group(2)}"'] = m.group(3)
    return found


def job(tmp_path, app, persistent):
    os.environ["AETHER_BROWSER_HOME"] = str(tmp_path / "home")
    session = browser.BrowserSession(None, None, host=local_host, persistent=persistent)
    car = browser.Sidecar("c" * 64, local_host)
    car.started, car.runs.ops_dir = True, str(tmp_path / "ops")
    session.sidecar = car
    calls = []

    async def call(code):
        out = await session.use({"code": code, "wait_s": 60}, 600.0)
        calls.append(out)
        return out

    async def go():
        try:
            first = await call(f"from aether_browser import page, snapshot\npage().goto({app + '/login'!r})\nsnapshot()")
            r = refs(first)
            second = await call(
                "from aether_browser import page, ref\n"
                f"ref({r['textbox \"Username\"']!r}).fill('ada')\nref({r['textbox \"Password\"']!r}).fill('pw')\n"
                f"ref({r['button \"Sign in\"']!r}).click()\npage().wait_for_url('**/app')\nprint('signed-in')")
            third = await call("from aether_browser import page, snapshot\nprint('url', page().url)\nsnapshot()")
            r = refs(third)
            fourth = await call(
                "from aether_browser import page, ref, snapshot\n"
                f"ref({r['button \"Add item\"']!r}).click()\npage().get_by_text('item one').wait_for()\nsnapshot()")
            frame = refs(fourth)['button "Frame button"']
            fifth = await call(f"from aether_browser import page, ref\nref({frame!r}).click()\nprint('title', page().title())")
            shot = await call(f"from aether_browser import shot\nshot('items', {frame!r})")
            add = refs(fourth)['button "Add item"']
            stale = await call(f"from aether_browser import page, ref\npage().goto({app + '/login'!r})\nref({add!r})")
            return calls, first, second, third, fourth, fifth, stale, shot
        finally:
            pid = tmp_path / "home" / "chrome.pid"
            if pid.exists():
                os.kill(int(pid.read_text()), signal.SIGKILL)

    return asyncio.run(go())


def test_one_browser_is_kept_across_calls_and_refs_act_on_what_was_shown(tmp_path, app):
    calls, first, second, third, fourth, fifth, stale, shot = job(tmp_path, app, persistent=True)
    assert 'textbox "Username"' in first and "[ref=" in first and "[snapshot #1;" in first
    assert "signed-in" in second and "/app" in second.splitlines()[-1]  # the state line names the page now open
    assert f"url {app}/app" in third  # a new process finds the page and the login of the last call
    assert "item one" in fourth  # the delayed element, waited for in the same call that clicked
    assert "title frame pressed" in fifth  # a ref inside the iframe acts in the frame
    assert "fixture-console-error" in second  # the app page loaded (and logged its error) during the sign-in call
    assert "stale ref" in stale or "is not in the last snapshot" in stale  # a ref from a page since replaced
    assert "[screenshot saved: /tmp/items.png]" in shot
    assert len(calls) == 7


def test_without_the_kept_browser_each_call_starts_blank(tmp_path, app):
    """Known-bad: fresh-process mode has no aether_browser module, so a later call cannot reach the earlier page."""
    session = browser.BrowserSession(None, None, host=local_host, persistent=False)
    car = browser.Sidecar("c" * 64, local_host)
    car.started, car.runs.ops_dir = True, str(tmp_path / "ops")
    session.sidecar = car
    out = asyncio.run(session.use({"code": "from aether_browser import page\nprint(page().url)", "wait_s": 30}, 300))
    assert "No module named 'aether_browser'" in out


def test_the_tool_description_names_the_kept_browser_only_in_session_mode():
    plain = browser.with_tool([{"function": {"name": "x"}}, {"function": {"name": "finish"}}])
    kept = browser.with_tool([{"function": {"name": "x"}}, {"function": {"name": "finish"}}], True)
    assert "aether_browser" not in plain[1]["function"]["description"]
    assert "aether_browser" in kept[1]["function"]["description"]
    assert plain[1]["function"]["parameters"] == kept[1]["function"]["parameters"]
