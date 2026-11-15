"""Source of ``aether_browser``, the module the model's browser code imports to use one browser kept open all task.

Why: every ``browser`` call was a fresh Python process with a fresh Chromium, so pages, logins, form state and
element references vanished between calls. A model that wanted to look, then act, then check had to redo the whole
navigation in each call, or put everything in one script before seeing the page.

What it is: Chromium runs detached in the sidecar with a profile directory, listening for DevTools on a port it picks
itself (port 0, read back from ``DevToolsActivePort``), so it never takes a port the task needs. Each call's code
connects to it with Playwright (``connect_over_cdp``), so the page it left is the page the next call finds. The model
keeps writing ordinary Playwright; nothing here interprets the page.

Element references are Playwright's own (``page.aria_snapshot(mode="ai")`` lists elements as ``[ref=e5]``,
``page.locator("aria-ref=e5")`` targets one). Refs are bound per connection, so ``page()`` takes a fresh snapshot to
rebind them. ``ref()`` checks the tab's main document and the element's role and name against the last snapshot shown
for that page. A full navigation can change the document while keeping the same URL.

Records, in ``HOME`` (``/tmp/.aether-browser``): ``profile/`` (Chromium's), ``chrome.pid``, ``snap_<n>.txt`` every
snapshot shown, with its page and URL, ``last_<page>.txt`` the latest one per page. When the call ends, one line of page
state is printed: open tabs and the current page's title and URL, and any console errors during the call. With page
facts (C3, AETHER_CORE_BROWSER_PAGE_FACTS=on, ``source(page_facts=True)``) it also lists the call's failed requests
(network failures and HTTP status >= 400), dialogs and downloads. All are recorded passively: dialogs through a
separate DevTools session, because a Playwright ``dialog`` listener would stop Playwright dismissing them itself.
"""


def source(page_facts: bool = False) -> str:
    """The module text, with page facts (C3) switched on or off."""
    return SOURCE.replace("_PAGE_FACTS = False", f"_PAGE_FACTS = {bool(page_facts)}", 1)


SOURCE = r'''
"""One browser kept open for the whole task. Use page() to get it; see its docstrings."""
import atexit, glob, json, os, re, signal, subprocess, sys, time

from playwright.sync_api import sync_playwright

HOME = os.environ.get("AETHER_BROWSER_HOME", "/tmp/.aether-browser")
_PAGE_FACTS = False
_S = {"pw": None, "browser": None, "page": None, "errors": [], "restarted": False, "failed": [], "dialogs": [],
      "downloads": [], "devtools": []}
_REF_LINE = re.compile(r"^\s*- (.*?)\s*\[ref=([a-z0-9]+)\]")
_NOISE = re.compile(r"\s*\[(?:ref|active|cursor|checked|expanded|selected|level|disabled|pressed)[^\]]*\]")


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return True


def _port():
    profile = os.path.join(HOME, "profile")
    pidfile = os.path.join(HOME, "chrome.pid")
    portfile = os.path.join(profile, "DevToolsActivePort")
    try:
        pid = int(open(pidfile).read())
    except (OSError, ValueError):
        pid = 0
    if not (pid and _alive(pid)):
        os.makedirs(profile, exist_ok=True)
        if pid:
            _S["restarted"] = True
        for stale in (portfile, os.path.join(profile, "SingletonLock")):
            try:
                os.unlink(stale)
            except OSError:
                pass
        exe = sync_playwright().start()
        try:
            chrome = exe.chromium.executable_path
        finally:
            exe.stop()
        proc = subprocess.Popen(
            [chrome, "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--no-first-run",
             "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0", f"--user-data-dir={profile}",
             "about:blank"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=open(os.path.join(HOME, "chrome.log"), "ab"),
            start_new_session=True)
        with open(pidfile + ".tmp", "w") as f:
            f.write(str(proc.pid))
        os.replace(pidfile + ".tmp", pidfile)
    for _ in range(300):
        try:
            return int(open(portfile).read().split()[0])
        except (OSError, ValueError, IndexError):
            time.sleep(0.05)
    raise RuntimeError("the task browser did not start (no DevTools port after 15 s)")


def _document(page):
    cdp = page.context.new_cdp_session(page)
    try:
        target = cdp.send("Target.getTargetInfo")["targetInfo"]["targetId"]
        loader = cdp.send("Page.getFrameTree")["frameTree"]["frame"]["loaderId"]
        return target, loader
    finally:
        cdp.detach()


def _listed(label, items):
    more = len(items) - 5
    return f"; {label} during this call: " + "; ".join(items[:5]) + (f" (+{more} more)" if more > 0 else "")


def _watch(page):
    """C3: record the page's failed requests, dialogs and downloads without changing how any is handled."""
    page.on("requestfailed", lambda r: _S["failed"].append(f"{r.method} {r.url[:150]} ({r.failure})"))
    page.on("response", lambda r: r.status >= 400 and _S["failed"].append(
        f"HTTP {r.status} {r.request.method} {r.url[:150]}"))
    page.on("download", lambda d: _S["downloads"].append(f"{d.suggested_filename} from {d.url[:150]}"))
    try:
        devtools = page.context.new_cdp_session(page)
        devtools.send("Page.enable")
        devtools.on("Page.javascriptDialogOpening", lambda e: _S["dialogs"].append(
            f"{e.get('type')} {str(e.get('message', ''))[:150]!r}"))
        _S["devtools"].append(devtools)
    except Exception as exc:
        _S["dialogs"].append(f"(dialogs not observable: {type(exc).__name__})")


def _finish():
    try:
        browser, page = _S["browser"], _S["page"]
        if browser is not None:
            pages = [p for c in browser.contexts for p in c.pages]
            current = page if page is not None and not page.is_closed() else (pages[-1] if pages else None)
            where = f"{current.title()!r} {current.url}" if current is not None else "none"
            line = f"[browser state: {len(pages)} tab(s) open; current page {where}"
            if _S["errors"]:
                line += _listed("console errors", _S["errors"])
            if _PAGE_FACTS:
                for label, key in (("failed requests", "failed"), ("dialogs", "dialogs"), ("downloads", "downloads")):
                    if _S[key]:
                        line += _listed(label, _S[key])
            print(line + "]", flush=True)
    except Exception as exc:
        print(f"[browser state unavailable: {type(exc).__name__}]", flush=True)
    finally:
        if _S["pw"] is not None:
            _S["pw"].stop()


def page(tab=None):
    """The task browser's current page (tab ``tab`` by index if given). The browser, its tabs, cookies and logins stay
    open between browser calls. The first call opens it."""
    if _S["browser"] is None:
        port = _port()
        _S["pw"] = sync_playwright().start()
        atexit.register(_finish)
        _S["browser"] = _S["pw"].chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        if _S["restarted"]:
            print("[the task browser had stopped and was started again: earlier tabs and logins are gone]", flush=True)
    browser = _S["browser"]
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    pages = context.pages or [context.new_page()]
    current = os.path.join(HOME, "current_tab")
    if tab is None:
        try:
            tab = int(open(current).read())
        except (OSError, ValueError):
            tab = len(pages) - 1
        tab = tab if 0 <= tab < len(pages) else len(pages) - 1
    chosen = pages[tab]
    with open(current, "w") as f:
        f.write(str(tab))
    if chosen is not _S["page"]:
        chosen.on("console", lambda m: m.type == "error" and _S["errors"].append(m.text[:200]))
        chosen.on("pageerror", lambda e: _S["errors"].append(str(e)[:200]))
        if _PAGE_FACTS:
            _watch(chosen)
        try:
            chosen.aria_snapshot(mode="ai")  # binds aria-ref locators for this connection
        except Exception:
            pass
    _S["page"] = chosen
    return chosen


def snapshot(target=None, depth=None):
    """Accessibility snapshot of the page (or a locator) with element refs; printed, kept as snap_<n>.txt, and
    returned. Act on an element with ref("e5")."""
    pg = target if target is not None and hasattr(target, "goto") else page()
    root = target if target is not None and not hasattr(target, "goto") else pg
    target_id, loader = _document(pg)
    text = root.aria_snapshot(mode="ai", depth=depth)
    if _document(pg) != (target_id, loader):
        raise LookupError("the document changed during the snapshot; take a new snapshot()")
    n = len(glob.glob(os.path.join(HOME, "snap_*.txt"))) + 1
    head = f"[snapshot #{n}; page {target_id[:12]}; {pg.url}]"
    for name, record in ((f"snap_{n}.txt", head), (f"last_{target_id}.txt", loader)):
        with open(os.path.join(HOME, name + ".tmp"), "w") as f:
            f.write(record + "\n" + text)
        os.replace(os.path.join(HOME, name + ".tmp"), os.path.join(HOME, name))
    print(head + "\n" + text, flush=True)
    return text


def _described(text, ref):
    for line in text.splitlines():
        m = _REF_LINE.match(line)
        if m and m.group(2) == ref:
            return _NOISE.sub("", m.group(1)).rstrip(":").strip()
    return None


def ref(name, pg=None):
    """Locator for element ``name`` (e.g. "e5" or "f1e2") from the last snapshot shown for this page. Refuses when
    the main document changed or the snapshot's ref no longer has the same role and name."""
    pg = pg or page()
    target_id, loader = _document(pg)
    try:
        with open(os.path.join(HOME, f"last_{target_id}.txt")) as f:
            shown_loader = f.readline().rstrip("\n")
            shown = f.read()
    except OSError:
        raise LookupError("no snapshot of this page has been shown yet; call snapshot() first") from None
    if loader != shown_loader:
        raise LookupError(f"stale ref {name}: the page document changed; take a new snapshot()")
    was = _described(shown, name)
    if was is None:
        raise LookupError(f"ref {name} is not in the last snapshot of this page")
    now = _described(pg.aria_snapshot(mode="ai"), name)
    if _document(pg) != (target_id, loader):
        raise LookupError(f"stale ref {name}: the page document changed; take a new snapshot()")
    if now != was:
        raise LookupError(f"stale ref {name}: it was {was!r} in the last snapshot shown, now "
                          f"{repr(now) if now else 'absent'}; take a new snapshot()")
    return pg.locator(f"aria-ref={name}")


def shot(name, target=None, full_page=False):
    """Save a PNG of the page, a locator, or ref string ``target`` under /tmp/<name>; pass name as `screenshot` to see
    it."""
    path = os.path.join("/tmp", os.path.basename(name if name.endswith(".png") else name + ".png"))
    pg = page()
    if isinstance(target, str):
        target = ref(target, pg)
    (target or pg).screenshot(path=path, **({} if target is not None else {"full_page": full_page}))
    print(f"[screenshot saved: {path}]", flush=True)
    return path
'''
