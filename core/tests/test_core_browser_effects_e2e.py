"""C16: with effect lines on, each browser action the model's code takes prints what it changed (switch, off by default).

Real Chromium through Playwright, as in ``test_core_browser_page_facts_e2e``. One call drives a fixture page through
seven actions whose effects are known: a DOM change, a no-op, a change that lands 300 ms later, a same-document URL
change (pushState), a field the page rewrites (upper-cases), a link that opens a new tab and a link that navigates.
Both Page and Locator action methods are used, as model code does.

Known-bads:
- with the switch off, no effect line is printed and the state line is unchanged;
- with a broken probe (the after-probe replaced by the before-probe), every action reads "no visible change", and the
  same checks report the missing effects. So the checks can fail.
"""

import asyncio
import http.server
import importlib.util
import os
import signal
import threading

import pytest

from aether.core import browser, browser_effects_src
from tests.test_core_browser_operation_faults_e2e import local_host

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None or not os.path.exists("/proc/self/stat"),
    reason="needs Linux with Playwright and Chromium (the browser fixture image)")

PAGE = b"""<html><head><title>Effects</title></head><body>
<button id=grow onclick="document.body.appendChild(document.createElement('p')).textContent='added'">grow</button>
<button id=noop>noop</button>
<button id=late onclick="setTimeout(()=>{document.body.appendChild(document.createElement('p')).textContent='late'},300)">late</button>
<button id=push onclick="history.pushState({}, '', '/a?step=2')">push</button>
<input id=up oninput="this.value=this.value.toUpperCase()">
<a id=pop href=/b target=_blank>pop</a>
<a id=nav href=/b>nav</a>
</body></html>"""

SCRIPT = """from aether_browser import page
pg = page()
pg.goto(BASE + '/a')
pg.click('#grow')
pg.locator('#noop').click()
pg.locator('#late').click()
pg.click('#push')
pg.locator('#up').fill('abc')
pg.click('#pop')
pg.locator('#nav').click()
print('done', pg.url)
"""

EXPECT = {  # effect line fragment for each action, in order
    "#grow": "page changed",
    "#noop": "no visible change within",
    "#late": "page changed",
    "#push": "URL changed to {base}/a?step=2 (same document)",
    "#up": "field value now 'ABC'",
    "#pop": "opened new tab {base}/b",
    "#nav": "navigated to {base}/b",
}


class App(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = PAGE if self.path.startswith("/a") else b"<html><title>B</title><body>b</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def app():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), App)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def call(tmp_path, base, effects):
    os.environ["AETHER_BROWSER_HOME"] = str(tmp_path / "home")
    session = browser.BrowserSession(None, None, host=local_host, persistent=True, effects=effects)
    car = browser.Sidecar("c" * 64, local_host)
    car.started, car.runs.ops_dir = True, str(tmp_path / "ops")
    session.sidecar = car

    async def go():
        try:
            return await session.use({"code": f"BASE = {base!r}\n" + SCRIPT, "wait_s": 90}, 600.0)
        finally:
            pid = tmp_path / "home" / "chrome.pid"
            if pid.exists():
                os.kill(int(pid.read_text()), signal.SIGKILL)

    return asyncio.run(go())


def problems(out, base):
    """Each expected effect must appear on the effect line of its own action."""
    lines = [line for line in out.splitlines() if line.startswith("[effect:")]
    found = []
    for target, fragment in EXPECT.items():
        line = next((x for x in lines if f" {target} -> " in x), None)
        want = fragment.format(base=base)
        if line is None or want not in line:
            found.append(f"{target}: wanted {want!r}, got {line!r}")
    return found


def test_each_action_states_its_effect(tmp_path, app):
    out = call(tmp_path, app, effects=True)
    assert f"done {app}/b" in out, out
    assert problems(out, app) == [], out
    assert out.splitlines()[-1].startswith("[browser state:"), out  # the state line stays last


def test_known_bad_switch_off_prints_no_effect_lines(tmp_path, app):
    out = call(tmp_path, app, effects=False)
    assert f"done {app}/b" in out and "[effect:" not in out, out
    assert out.splitlines()[-1].startswith("[browser state:"), out


def test_known_bad_broken_probe_is_caught(tmp_path, app, monkeypatch):
    broken = browser_effects_src.SOURCE.replace("(_probe(pg), 0.0) if name in _VALUE else _after_probe(pg)", "(before, 0.5)")
    assert broken != browser_effects_src.SOURCE
    monkeypatch.setattr(browser_effects_src, "SOURCE", broken)
    out = call(tmp_path, app, effects=True)
    missing = problems(out, app)
    assert any(m.startswith("#grow") for m in missing) and any(m.startswith("#nav") for m in missing), out


def test_the_switch_only_appends_the_effects_text():
    from aether.core import browser_session_src as src
    assert src.source(False, False) == src.SOURCE
    assert src.source(False, True) == src.SOURCE + browser_effects_src.SOURCE
    assert src.source(True, True).startswith(src.source(True, False))
