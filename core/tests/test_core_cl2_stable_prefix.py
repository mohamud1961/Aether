"""CL2 (17 Nov, G14d layout CL vs GV): the CLM request changes mid-history only at a cut.

1. AETHER_CORE_IMAGE_AGING=cut: images leave only at a cut (window cut, checkpoint, accepted edit). Known-bad: the
   default batch aging rewrote the request 7 times on layout CL, each re-billing 73-106K tokens uncached.
2. AETHER_CORE_CLM_NUDGES=off: no nudges or reminders. Known-bad: the late reminder led to deep self-edits.
"""

import json

import pytest

from aether.core import images
from aether.core.clm import ClmContext, ClmSettings
from aether.core.harbor_config import ConfigError, build_config
from aether.core.loop import CoreConfig
from tests.core_fakes import call
from tests.test_core_image_region import _wide
from tests.test_core_v2 import _run


def _first_change(a, b):
    return next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), None)


def _grow(at_cut, n=12):
    ctx = ClmContext(pinned=[], settings=ClmSettings(budget_tokens=10**6, reserve_tokens=0, image_keep=2,
                                                     image_batch=4, image_age_at_cut=at_cut))
    ctx.append({"role": "user", "content": "task"})
    breaks, prev = 0, None
    for i in range(n):
        ctx.append({"role": "assistant", "content": f"look {i}"})
        ctx.append(images.message(f"view {i}", f"data:image/png;base64,{i}"))
        req = ctx.request()
        breaks += prev is not None and _first_change(prev, req) is not None
        prev = req
    return ctx, breaks


def _shown(req):
    return sum(images.count(m) for m in req)


def test_images_stay_until_a_cut_then_only_the_newest_keep_remain():
    batch, batch_breaks = _grow(False)
    cut, cut_breaks = _grow(True)
    assert batch_breaks == 2 and _shown(batch.request()) <= 2 + 4 - 1  # known-bad: the prefix moves between cuts
    assert cut_breaks == 0 and _shown(cut.request()) == 12  # append-only until the cut
    before = cut.tokens()
    assert cut.age_images() == 10
    req = cut.request()
    assert _shown(req) == 2 and images.count(req[-1]) == 1 and cut.tokens() < before
    assert "image no longer shown" in json.dumps(req[2])  # the oldest image is replaced by a note, not deleted
    assert cut.age_images() == 0 and _shown(cut.request()) == 2  # aging again changes nothing
    cut.append({"role": "assistant", "content": "next"})
    cut.append(images.message("view 12", "data:image/png;base64,12"))
    assert _shown(cut.request()) == 3  # a new image is added after the cut, not traded for an old one


def test_a_reused_message_id_is_never_hidden():
    ctx, _ = _grow(True, n=3)
    ctx.age_images()
    ctx.editable = [dict(m) for m in ctx.editable]  # an accepted edit rebuilds the messages
    assert _shown(ctx.request()) == 3


def _e2e(tmp_path, at_cut):
    (tmp_path / "work").mkdir()
    for i in range(10):
        _wide(tmp_path / "work" / f"{i}.png")
    script = [call("view_image", {"path": f"{i}.png"}, f"v{i}") for i in range(10)]
    script += [call("terminal", {"input": "printf '%s' '" + "x" * 30000 + "'"}, "big"),
               call("finish", {"summary": "done"}, "f")]
    settings = ClmSettings(budget_tokens=26_000, reserve_tokens=500, image_keep=2, image_batch=4,
                           image_age_at_cut=at_cut, checkpoint_policy="window", window_cut_margin_tokens=8000,
                           replay_reasoning="segment",  # the CL arm; "newest" drops the previous turn's reasoning
                           mirror_path=str(tmp_path / "ctl" / "live"), history_path=str(tmp_path / "ctl" / "history"))
    result, trace, client = _run(tmp_path, script, config=CoreConfig(images=True, context="clm", clm=settings,
                                                                     control_dir=str(tmp_path / "ctl")))
    assert result.status == "finished", result.error
    reqs = [r["messages"] for r in client.requests if "tools" in r]
    counts = [sum(images.count(m) for m in r) for r in reqs]
    moved = [k for k in range(1, len(reqs)) if _first_change(reqs[k - 1], reqs[k]) is not None]
    return reqs, counts, trace, moved


def test_end_to_end_a_window_cut_ages_images_and_the_prefix_holds_between_cuts(tmp_path):
    pytest.importorskip("PIL")
    reqs, counts, events, moved = _e2e(tmp_path, True)
    aged = [e for e in events if e["event"] == "context_images_aged"]
    assert counts[:11] == list(range(11)) and aged and aged[0]["hidden"] >= 1  # every image kept until the cut
    assert counts[-1] <= 2
    cut_at = next(k for k in range(1, len(reqs)) if counts[k] < counts[k - 1])
    assert moved == [cut_at]  # the request changed mid-history once: at the cut


def test_known_bad_batch_aging_moves_the_prefix_between_cuts(tmp_path):
    pytest.importorskip("PIL")
    _, counts, _, moved = _e2e(tmp_path, False)
    assert max(counts) <= 2 + 4 - 1 and moved == [6, 10]  # two mid-history moves (images drop 4 at a time), vs one cut


def test_nudges_off_sends_no_reminder():
    def nudge(on):
        ctx = ClmContext(pinned=[], settings=ClmSettings(budget_tokens=4000, reserve_tokens=0,
                                                         reminder_room_tokens=2048, nudges=on))
        ctx.append({"role": "user", "content": "x" * 12000})
        return ctx.nudge()

    assert "Condense" in nudge(True)  # known-bad: the late reminder fires near the limit
    assert nudge(False) == ""


def test_switches_are_opt_in_and_validated():
    env = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off",
           "AETHER_CORE_IMAGES": "on"}
    base = build_config(environ=env).clm
    assert not base.image_age_at_cut and base.nudges and base.reminder_room_tokens == 2048
    cl2 = build_config(environ={**env, "AETHER_CORE_IMAGE_AGING": "cut", "AETHER_CORE_CLM_NUDGES": "off"}).clm
    assert cl2.image_age_at_cut and not cl2.nudges and cl2.reminder_room_tokens == 0
    for name in ("AETHER_CORE_IMAGE_AGING", "AETHER_CORE_CLM_NUDGES"):
        with pytest.raises(ConfigError):
            build_config(environ={**env, name: "sometimes"})
