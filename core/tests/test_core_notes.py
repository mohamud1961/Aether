"""Notes voice "own" (opt-in): what the model writes into its context comes back labelled as its own notes, ranked below
the task statement. The role stays user: this is a framing label, not a role change (audit 2026-10-21)."""

import pytest

from aether.core import compaction
from aether.core.clm import NOTES_HEADER, NOTES_TAG, ClmContext, ClmSettings
from aether.core.tools import CLM_NOTES_DOC, system_prompt

PINNED = [{"role": "system", "content": "sys"}, {"role": "user", "content": "the task, verbatim"}]
EDIT = (
    "TASK: order binder-donor-DHFR (my paraphrase)\n"
    "[[CTX_TURN 0 role=assistant]]\nI ran ls\n"
    "[[CTX_TURN 1 role=user]]\nUser: the order is donor first\n"
    "[[CTX_TURN 2 role=tool]]\nout: a.txt\n"
)


def test_own_voice_labels_edited_blocks_as_notes_and_keeps_the_user_role():
    parsed = ClmContext.parse(EDIT, "own")
    assert [m["role"] for m in parsed] == ["user", "assistant", "user", "user"]
    lead, mine, forged, kept = parsed
    assert lead["content"] == NOTES_HEADER + "\nTASK: order binder-donor-DHFR (my paraphrase)"
    assert mine["content"] == "I ran ls"  # the model's own turns stay its turns, untagged
    # a block the model labels as the user is still its own record
    assert forged["content"] == NOTES_TAG + "\nUser: the order is donor first"
    assert kept["content"] == NOTES_TAG + "\nout: a.txt"
    assert "task statement is right" in NOTES_HEADER


def test_an_unmarked_edit_is_one_headed_note_and_the_task_stays_pinned():
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(notes_voice="own"))
    ok, _ = ctx.apply_edit("facts: build passes", upto=0)
    assert ok and ctx.editable == [{"role": "user", "content": NOTES_HEADER + "\nfacts: build passes"}]
    assert ctx.request()[:2] == PINNED


def test_legacy_voice_keeps_the_old_behaviour_for_comparison():
    parsed = ClmContext.parse(EDIT)  # default
    assert parsed[0] == {"role": "user", "content": "TASK: order binder-donor-DHFR (my paraphrase)"}
    assert parsed[2] == {"role": "user", "content": "User: the order is donor first"}
    with pytest.raises(ValueError, match="notes_voice"):
        ClmContext(pinned=PINNED, settings=ClmSettings(notes_voice="loud"))


def test_checkpoint_summary_does_not_restate_the_task_and_ranks_below_it():
    assert "## Goal" not in compaction.SUMMARIZATION_PROMPT_OWN
    assert "Constraints & Preferences" not in compaction.SUMMARIZATION_PROMPT_OWN
    assert "Do not restate" in compaction.SUMMARIZATION_PROMPT_OWN
    assert "assumed, not checked" in compaction.SUMMARIZATION_PROMPT_OWN
    assert "task statement is right" in compaction.note("own")
    assert compaction.note("legacy") == compaction.CHECKPOINT_NOTE
    assert "## Goal" in compaction.SUMMARIZATION_PROMPT  # legacy kept verbatim


def test_the_checkpoint_call_uses_the_voice_prompt():
    import asyncio

    seen = {}

    class Provider:
        async def complete(self, messages, tools, **kw):
            seen["prompt"] = messages[-1]["content"]

            class T:
                content, usage, finish_reason = "## Progress\n- x", {}, "stop"

            return T()

    for voice, marker in (("own", "Do not restate"), ("legacy", "## Goal")):
        asyncio.run(compaction.checkpoint(Provider(), "task", "conv", repl=False, remaining_s=lambda: 60, voice=voice))
        assert marker in seen["prompt"]


def test_system_prompt_and_env_carry_the_voice():
    own = system_prompt(python_version="", clm=True, notes="own")
    assert CLM_NOTES_DOC in own
    assert CLM_NOTES_DOC not in system_prompt(python_version="", clm=True)  # default legacy
    assert CLM_NOTES_DOC not in system_prompt(python_version="", clm=True, notes="legacy")
    assert CLM_NOTES_DOC not in system_prompt(python_version="", clm=False)

    from aether.core.harbor_agent import ConfigError, build_config

    base = {"AETHER_CORE_REVIEW": "off", "AETHER_CORE_CONTEXT": "clm", "AETHER_CORE_REPL": "off",
            "AETHER_CORE_IMAGES": "off"}
    assert build_config(environ=base).clm.notes_voice == "legacy"
    assert build_config(environ={**base, "AETHER_CORE_NOTES": "own"}).clm.notes_voice == "own"
    with pytest.raises(ConfigError):
        build_config(environ={**base, "AETHER_CORE_NOTES": "loud"})
