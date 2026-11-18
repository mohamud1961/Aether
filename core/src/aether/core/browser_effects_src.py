"""C16: one line of fact after each browser action the model's code takes (switch AETHER_CORE_BROWSER_EFFECTS, off).

Why: Playwright MCP and browser-use both report what an action did. browser-use's form, one line from a before/after
probe ("navigated to <url>" / "page changed" / "no change"), is the cheaper of the two (F4_BROWSER_SOURCE_STUDY). Core
let the model write ordinary Playwright and printed only the page state at the end of the call, so a click that did
nothing, or a field the page rewrote, looked the same as one that worked until the model looked again.

What it is: text appended to the ``aether_browser`` module (browser_session_src) when the switch is on. On import it
wraps Playwright's own action methods (Locator, Page, Mouse, Keyboard), so the model's code is unchanged. Around each
action it takes a cheap probe of the page (URL, document identity, element count, text length and a text hash, the
number of tabs), watches the page settle (at least 0.5 s, done when two probes 0.1 s apart agree, at most 1.5 s), and
prints one line: ``[effect: click <target> -> navigated to <url>]``, ``URL changed to <url> (same document)``,
``page changed``, ``opened new tab <url>``, ``no visible change within <s> s``. A fill or type also states the field's value
afterwards, so a field the page rewrote or refused shows. Dialogs and downloads recorded by page facts (C3) during
the action are named in the line. An action that raises prints nothing (its error is the fact); a probe that fails
says so. After 20 lines in one call it says once that later actions are not listed.

It states what changed, never what the model should do (E13).
"""

SOURCE = r'''

# ---- C16: per-action effect lines (AETHER_CORE_BROWSER_EFFECTS) ----
import functools as _ft

from playwright.sync_api import Keyboard as _Keyboard, Locator as _Locator, Mouse as _Mouse, Page as _Page

_EFFECT = {"n": 0, "busy": False}
_EFFECT_LIMIT = 20
_PROBE_JS = """() => { const b = document.body; const t = b ? b.innerText : "";
  let h = 0; for (let i = 0; i < t.length; i++) { h = (h * 31 + t.charCodeAt(i)) | 0; }
  return [location.href, performance.timeOrigin, document.getElementsByTagName("*").length, t.length, h]; }"""
_SETTLE = ("click", "dblclick", "tap", "press", "check", "uncheck", "set_checked", "select_option",
           "set_input_files", "go_back", "go_forward", "reload")
_VALUE = ("fill", "type", "press_sequentially", "clear")


def _probe(pg):
    try:
        url, origin, nodes, length, digest = pg.evaluate(_PROBE_JS)
    except Exception:
        return None
    try:
        tabs = len(pg.context.pages)
    except Exception:
        tabs = None
    return {"url": url, "doc": origin, "dom": (nodes, length, digest), "tabs": tabs}


def _after_probe(pg):
    """Probe after the action: watch for at least 0.5 s (a page often reacts a few hundred ms late), then stop once
    two probes 0.1 s apart agree, at most 1.5 s. A page still loading (no probe possible) gets up to 3 s more to reach
    DOMContentLoaded. Returns the probe and how long the page was watched."""
    start = time.monotonic()
    last = _probe(pg)
    while time.monotonic() - start < 1.5:
        time.sleep(0.1)
        now = _probe(pg)
        if now is not None and now == last and time.monotonic() - start >= 0.5:
            break
        last = now
    if last is None:
        try:
            pg.wait_for_load_state("domcontentloaded", timeout=3000)
        except Exception:
            pass
        last = _probe(pg)
    return last, time.monotonic() - start


def _target(obj, args):
    if isinstance(obj, _Locator):
        m = re.search(r"selector='([^']*)'", repr(obj))
        return (m.group(1) if m else "locator")[:80]
    if args and isinstance(args[0], str):
        return args[0][:80]
    if len(args) >= 2 and all(isinstance(a, (int, float)) for a in args[:2]):
        return f"({args[0]:g}, {args[1]:g})"
    return ""


def _describe(before, after, pg, watched):
    if after is None:
        return "not observed (the page could not be probed after the action)"
    if before is None:
        return f"page now {after['url']} (no probe before the action)"
    parts = []
    if before["tabs"] is not None and after["tabs"] is not None and after["tabs"] > before["tabs"]:
        try:
            tab = pg.context.pages[-1]
            try:
                tab.wait_for_load_state("commit", timeout=3000)
            except Exception:
                pass
            parts.append("opened new tab " + tab.url)
        except Exception:
            parts.append("opened a new tab")
    if after["doc"] != before["doc"]:
        parts.append("navigated to " + after["url"])
    elif after["url"] != before["url"]:
        parts.append(f"URL changed to {after['url']} (same document)")
    if after["doc"] == before["doc"] and after["dom"] != before["dom"]:
        parts.append("page changed")
    return "; ".join(parts) or f"no visible change within {watched:.1f} s"


def _say(line):
    _EFFECT["n"] += 1
    if _EFFECT["n"] <= _EFFECT_LIMIT:
        print(line, flush=True)
    elif _EFFECT["n"] == _EFFECT_LIMIT + 1:
        print(f"[effect lines stop after {_EFFECT_LIMIT} actions in one call; later actions are not listed]",
              flush=True)


def _wrap(cls, name, page_of):
    original = getattr(cls, name, None)
    if original is None:
        return

    @_ft.wraps(original)
    def act(self, *args, **kwargs):
        if _EFFECT["busy"]:
            return original(self, *args, **kwargs)
        pg = page_of(self)
        if pg is None:
            return original(self, *args, **kwargs)
        _EFFECT["busy"] = True
        try:
            before = _probe(pg)
            seen = {k: len(_S[k]) for k in ("dialogs", "downloads")}
            result = original(self, *args, **kwargs)
            after, watched = (_probe(pg), 0.0) if name in _VALUE else _after_probe(pg)
            text = _describe(before, after, pg, watched)
            if name in _VALUE and isinstance(self, _Locator):
                try:
                    text += f"; field value now {self.input_value(timeout=500)[:120]!r}"
                except Exception:
                    pass
            for key in ("dialogs", "downloads"):
                new = _S[key][seen[key]:]
                if new:
                    text += f"; {key[:-1]} " + "; ".join(new[:3])
            target = _target(self, args)
            _say(f"[effect: {name}{' ' + target if target else ''} -> {text}]")
            return result
        finally:
            _EFFECT["busy"] = False

    setattr(cls, name, act)


for _name in _SETTLE + _VALUE:
    _wrap(_Locator, _name, lambda loc: loc.page)
    _wrap(_Page, _name, lambda pg: pg)
for _name in ("click", "dblclick"):
    _wrap(_Mouse, _name, lambda _m: _S["page"])
for _name in ("press", "type", "insert_text"):
    _wrap(_Keyboard, _name, lambda _k: _S["page"])
'''
