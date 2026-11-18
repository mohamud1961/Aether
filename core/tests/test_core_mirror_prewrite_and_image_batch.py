"""Two cost/speed fixes from the 16 Nov scan.

1. loop_mirror: the CLM context mirror is written while the model call is in flight (it was one sandbox round trip,
   median 0.33 s, before every tool dispatch). The file it leaves is the same; known-bad: without ``start`` the write
   happens only after the model returns.
2. images.limit(batch=N): old images leave in groups, so the request prefix before them changes once per N new images
   instead of on every one. batch=1 is the original behaviour (known-bad for the stable-prefix property).
"""

import asyncio
from types import SimpleNamespace

import pytest

from aether.core import images, loop_mirror
from aether.core.clm_mirror import ClmMirror

# ---- loop_mirror -------------------------------------------------------------------------------------------------


class _Clm(ClmMirror):
    def __init__(self, msgs, path):
        self.editable = msgs
        self.settings = SimpleNamespace(mirror_path=path)


def _session(msgs, writes, delay=0.01, fail=False):
    async def put(env, data, path, **kw):
        writes.append(("begin", data.decode(), path))
        await asyncio.sleep(delay)
        if fail:
            raise OSError("sandbox gone")
        writes.append(("end", data.decode(), path))

    return SimpleNamespace(clm=_Clm(msgs, "/m"), env=None, mirror_prewrite=None), put


def test_an_identical_prewrite_is_used_and_not_repeated(monkeypatch):
    writes = []
    s, put = _session([{"role": "user", "content": "task"}], writes)
    monkeypatch.setattr(loop_mirror, "put_bytes", put)

    async def go():
        loop_mirror.start(s)
        s.clm.editable.append({"role": "assistant", "content": "x"})  # the turn's reply arrives
        upto = len(s.clm.editable) - 1
        await loop_mirror.write(s, upto, s.clm.render(upto))

    asyncio.run(go())
    assert [w[0] for w in writes] == ["begin", "end"] and s.mirror_prewrite is None


def test_a_changed_history_is_written_again_after_the_old_write_lands(monkeypatch):
    writes = []
    s, put = _session([{"role": "user", "content": "task"}], writes)
    monkeypatch.setattr(loop_mirror, "put_bytes", put)

    async def go():
        loop_mirror.start(s)
        s.clm.editable[0] = {"role": "user", "content": "task (edited)"}
        s.clm.editable.append({"role": "assistant", "content": "x"})
        upto = len(s.clm.editable) - 1
        await loop_mirror.write(s, upto, s.clm.render(upto))

    asyncio.run(go())
    assert [w[0] for w in writes] == ["begin", "end", "begin", "end"]  # never overlapping
    assert "edited" in writes[-1][1] and "edited" not in writes[0][1]


def test_a_failed_prewrite_raises_where_the_direct_write_did(monkeypatch):
    writes = []
    s, put = _session([{"role": "user", "content": "task"}], writes, fail=True)
    monkeypatch.setattr(loop_mirror, "put_bytes", put)

    async def go():
        loop_mirror.start(s)
        await loop_mirror.write(s, 1, s.clm.render(1))

    with pytest.raises(OSError, match="sandbox gone"):
        asyncio.run(go())


def test_abandon_cancels_a_write_in_flight(monkeypatch):
    writes = []
    s, put = _session([{"role": "user", "content": "task"}], writes, delay=5)
    monkeypatch.setattr(loop_mirror, "put_bytes", put)

    async def go():
        loop_mirror.start(s)
        await asyncio.sleep(0)
        task = s.mirror_prewrite[2]
        loop_mirror.abandon(s)
        await asyncio.sleep(0)
        return task

    assert asyncio.run(go()).cancelled() and writes == [("begin", "[[CTX_TURN 0 role=user]]\ntask", "/m")]


def _order_run(tmp_path, monkeypatch, prewrite):
    from aether.core import env as env_mod
    from aether.core.provider import ChatProvider
    from tests.core_fakes import call
    from tests.test_core_v2 import _clm_config, _run

    events = []
    real_put, real_complete = env_mod.put_bytes, ChatProvider.complete
    mirror = str(tmp_path / "ctx" / "LIVE_CTX.txt")

    async def put(env, data, path, **kw):
        if path == mirror:
            events.append("mirror")
        return await real_put(env, data, path, **kw)

    async def complete(self, *a, **kw):
        out = await real_complete(self, *a, **kw)
        await asyncio.sleep(0.05)  # a model call takes time; the prewrite runs inside it
        events.append("model")
        return out

    monkeypatch.setattr(loop_mirror, "put_bytes", put)
    monkeypatch.setattr(ChatProvider, "complete", complete)
    if not prewrite:
        monkeypatch.setattr(loop_mirror, "start", lambda s: None)
    script = [call("terminal", {"input": "echo one"}, "c1"), call("terminal", {"input": "echo two"}, "c2"),
              call("finish", {"summary": "done"}, "c3")]
    result = _run(tmp_path, script, config=_clm_config(tmp_path))[0]
    return result, events, open(mirror).read()


def test_end_to_end_the_mirror_is_written_during_the_model_call(tmp_path, monkeypatch):
    result, events, text = _order_run(tmp_path, monkeypatch, prewrite=True)
    assert result.status == "finished"
    # every tool turn's mirror write began before that turn's model call returned
    assert events[:4] == ["mirror", "model", "mirror", "model"]
    assert "echo one" in text and "[[CTX_TURN" in text


def test_known_bad_without_the_prewrite_the_write_follows_the_reply(tmp_path, monkeypatch):
    _, events, text = _order_run(tmp_path, monkeypatch, prewrite=False)
    assert events[:4] == ["model", "mirror", "model", "mirror"]
    assert "echo one" in text and "[[CTX_TURN" in text  # the same file either way


# ---- images.limit(batch) -----------------------------------------------------------------------------------------

def _img(i):
    return {"role": "user", "content": [{"type": "text", "text": f"[view_image] {i}"},
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{i}"}}]}


def _shown(msgs):
    return [i for i, m in enumerate(msgs) if isinstance(m.get("content"), list)]


def _first_change(a, b):
    return next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), None)


@pytest.mark.parametrize("batch", [1, 3, 4])
def test_image_batch_shows_keep_to_keep_plus_batch_minus_one(batch):
    history = []
    for i in range(12):
        history += [_img(i), {"role": "assistant", "content": f"saw {i}"}]
        n = len(_shown(images.limit(history, batch=batch)))
        assert images.KEEP_IMAGES <= n or i + 1 < images.KEEP_IMAGES
        assert n <= images.KEEP_IMAGES + batch - 1
    assert images.limit(history, batch=1) == images.limit(history)  # batch=1 is the original behaviour


def test_image_batch_breaks_the_prefix_once_per_batch_and_batch_one_every_time():
    def breaks(batch):
        history, prev, n = [], None, 0
        for i in range(12):
            history += [_img(i), {"role": "assistant", "content": f"saw {i}"}]
            req = images.limit(history, batch=batch)
            if prev is not None and _first_change(prev, req) is not None:
                n += 1
            prev = req
        return n

    assert breaks(1) == 10  # known-bad: every image after the second rewrites an older one
    assert breaks(4) == 2  # images 6 and 10 drop four at a time


def test_image_batch_env_is_wired_and_defaults_to_four():
    from aether.core import harbor_config as hc

    base = {hc.REVIEW_ENV: "off", hc.CONTEXT_ENV: "clm", hc.REPL_ENV: "off", hc.IMAGES_ENV: "on"}
    assert hc.build_config(environ=base).clm.image_batch == 4
    assert hc.build_config(environ={**base, hc.IMAGE_BATCH_ENV: "1"}).clm.image_batch == 1
    assert hc.build_config(environ={**base, hc.IMAGE_BATCH_ENV: "4"}).clm.image_batch == 4
    with pytest.raises(hc.ConfigError):
        hc.build_config(environ={**base, hc.IMAGE_BATCH_ENV: "5"})
