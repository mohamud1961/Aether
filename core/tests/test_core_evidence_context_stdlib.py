"""Offline tests for default-off Core-native original history presentation.

No model API, task VM, benchmark, or PCR dependency.
"""
from __future__ import annotations

import json
import unittest

from aether.core.clm import ClmContext, ClmSettings
from aether.core.evidence_context import history_index, select_context
from aether.core.harbor_agent import build_config, ConfigError
from aether.core.loop import CoreConfig


PINNED = [
    {"role": "system", "content": "Source task rules"},
    {"role": "user", "content": "Original request field is value, not val"},
]
HISTORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "read_history",
            "parameters": {
                "type": "object",
                "properties": {"message_id": {"type": "integer"}},
            },
        },
    }
]


def action(n: int):
    call = str(n)
    return {
        "role": "assistant",
        "content": "Observed tool call",
        "tool_calls": [
            {
                "type": "function",
                "id": call,
                "function": {"name": "terminal", "arguments": '{"input":"cat proto"}'},
            }
        ],
    }


def result(n: int, text: str):
    return {"role": "tool", "tool_call_id": str(n), "content": text}


def edited(*data):
    ctx = ClmContext(pinned=PINNED, settings=ClmSettings(notes_voice="own", attest_original_history=True))
    ctx.append(*data)
    ok, _ = ctx.apply_edit("My notes claim that the task is done, without proof.", len(ctx.editable))
    assert ok
    return ctx


def card_json(messages):
    return json.loads(messages[-1]["content"].split("\n", 1)[1])


class HistoryEvidenceTest(unittest.TestCase):
    def test_default_off_exact_identity(self):
        ctx = edited(action(1), result(1, "old decisive evidence"))
        base = ctx.request()
        shown, report = select_context(ctx, base, HISTORY_TOOL)
        self.assertIs(base, shown)
        self.assertFalse(report["changed"])

    def test_when_source_still_hot_no_duplicate_prompt(self):
        ctx = ClmContext(pinned=PINNED, settings=ClmSettings())
        ctx.append(action(1), result(1, "source already visible"))
        base = ctx.request()
        shown, report = select_context(ctx, base, HISTORY_TOOL, policy="history_index")
        self.assertIs(base, shown)
        self.assertFalse(report["changed"])

    def test_after_edit_old_source_index_and_unchanged_original_state(self):
        ctx = edited(action(1), result(1, "SetValRequest val \u2713"))
        original_raw = json.dumps(ctx.raw, ensure_ascii=False)
        base = ctx.request()
        shown, report = select_context(ctx, base, HISTORY_TOOL, policy="history_index")
        self.assertTrue(report["changed"])
        self.assertEqual(shown[:-1], base)
        self.assertEqual(ctx.request(), base)
        self.assertEqual(json.dumps(ctx.raw, ensure_ascii=False), original_raw)
        entry = card_json(shown)["records"][0]
        self.assertEqual(entry["message_id"], 1)
        self.assertEqual(entry["message_id"], 1)
        self.assertIn("SetValRequest val", ctx.read_history(1))
        self.assertEqual(card_json(shown)["source"], "Core original tool history (append-time SHA256, page-verified)")

    def test_oldest_source_not_misclassified_while_bounded(self):
        ctx = edited(*(item for n in range(8) for item in (
            action(n), result(n, "original essential source" if n == 0 else f"less relevant {n}")
        )))
        shown, report = select_context(ctx, ctx.request(), HISTORY_TOOL, policy="history_index")
        self.assertTrue(report["changed"])
        card = card_json(shown)
        self.assertEqual([x["message_id"] for x in card["records"]], [15, 13, 11])
        self.assertEqual(card["coverage"]["eligible"], 8)
        self.assertEqual(card["coverage"]["unlisted"], 5)
        self.assertFalse(card["coverage"]["unlisted"] == 0)
        self.assertEqual(card["coverage"]["oldest_unlisted_id"], 1)
        self.assertIn("original essential", ctx.read_history(1))
        self.assertTrue(card["unlisted_may_matter"])

    def test_duplicate_outputs_maintain_distinct_occurrences(self):
        ctx = ClmContext(pinned=PINNED, settings=ClmSettings(attest_original_history=True))
        ctx.append(action(1), result(1, "identical"), action(2), result(2, "identical"))
        ok, _ = ctx.apply_edit("Short", 2)
        self.assertTrue(ok)
        # The second result is still in the editable snapshot, but the first
        # original result with its distinct tool_call_id has been displaced.
        card, _ = history_index(ctx, ctx.request())
        self.assertIsNotNone(card)
        refs = json.loads(card["content"].split("\n", 1)[1])["records"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["message_id"], 1)

    def test_unicode_and_pages(self):
        content = "at start \u00e9\u2713" + "long lines \u00e9\u2713\n" * 2400 + "\nend"
        ctx = edited(action(1), result(1, content))
        card, metadata = history_index(ctx, ctx.request())
        self.assertIsNotNone(card)
        self.assertEqual(metadata["listed"], 1)
        text = ctx.read_history(1)
        self.assertTrue(text.startswith("[history MSG 1"))
        # Paged source replay must preserve Unicode and the full original.
        pieces, offset = [], 0
        for _ in range(10):
            header, part = ctx.read_history(1, offset, 12000).split("\n", 1)
            pieces.append(part)
            offset += len(part)
            if "; complete]" in header:
                break
        self.assertEqual(json.loads("".join(pieces))["content"], content)

    def test_huge_original_not_claimed_verified(self):
        ctx = edited(action(1), result(1, "x" * 100_000))
        card, reason = history_index(ctx, ctx.request())
        self.assertIsNone(card)
        self.assertEqual(reason["reason"], "no_exact_source_pages_qualified")
        self.assertIn("x" * 120, ctx.read_history(1))

    def test_missing_history_tool_fails_closed(self):
        ctx = edited(action(1), result(1, "source"))
        base = ctx.request()
        shown, report = select_context(ctx, base, [], policy="history_index")
        self.assertIs(shown, base)
        self.assertEqual(report["reason"], "native_history_unavailable")

    def test_project_context_rejects_index_at_configuration(self):
        with self.assertRaises(ValueError):
            CoreConfig(context="project", evidence_presentation="history_index")

    def test_unknown_evidence_mode_rejected(self):
        with self.assertRaises(ValueError):
            CoreConfig(context="clm", evidence_presentation="something_else")

    def test_harbor_env_flag_off_and_on(self):
        env = {
            "AETHER_CORE_REVIEW": "off",
            "AETHER_CORE_CONTEXT": "clm",
            "AETHER_CORE_REPL": "on",
            "AETHER_CORE_IMAGES": "off",
        }
        self.assertEqual(build_config(environ=env).evidence_presentation, "off")
        env["AETHER_CORE_CONTEXT_EVIDENCE_PRESENTATION"] = "history_index"
        c = build_config(environ=env)
        self.assertEqual(c.evidence_presentation, "history_index")
        self.assertTrue(c.clm.attest_original_history)

    def test_harbor_bad_option_rejected(self):
        env = {
            "AETHER_CORE_REVIEW": "off",
            "AETHER_CORE_CONTEXT": "clm",
            "AETHER_CORE_REPL": "on",
            "AETHER_CORE_IMAGES": "off",
            "AETHER_CORE_CONTEXT_EVIDENCE_PRESENTATION": "verdict",
        }
        with self.assertRaises(ConfigError):
            build_config(environ=env)

    def test_budget_fail_closed(self):
        cfg = ClmSettings(budget_tokens=2050, reserve_tokens=2048, attest_original_history=True)
        ctx = ClmContext(pinned=PINNED, settings=cfg)
        ctx.append(action(1), result(1, "source"))
        ctx.apply_edit("small", 2)
        base = ctx.request()
        shown, report = select_context(ctx, base, HISTORY_TOOL, policy="history_index")
        self.assertIs(shown, base)
        self.assertFalse(report["changed"])

    def test_no_original_raw_copy_is_deleted(self):
        ctx = edited(action(1), result(1, "history"))
        prior_len, prior_raw = len(ctx.raw), json.dumps(ctx.raw, ensure_ascii=False)
        _ = select_context(ctx, ctx.request(), HISTORY_TOOL, policy="history_index")
        self.assertEqual(prior_len, len(ctx.raw))
        self.assertEqual(prior_raw, json.dumps(ctx.raw, ensure_ascii=False))

    def test_append_time_digest_is_stable_after_context_edit(self):
        ctx = edited(action(1), result(1, "source historical original é"))
        verified = ctx.original_message_digest(1)
        self.assertEqual(len(verified), 64)
        ctx.replace_with_checkpoint("model note", "checkpoint", len(ctx.editable))
        self.assertEqual(ctx.original_message_digest(1), verified)

    def test_raw_mutation_disqualifies_source_even_if_read_history_matches(self):
        ctx = edited(action(1), result(1, "original source"))
        ctx.raw[1]["content"] = "tampered later"
        self.assertIsNone(ctx.original_message_digest(1))
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            ctx.read_history(1)
        baseline = ctx.request()
        shown, status = select_context(ctx, baseline, HISTORY_TOOL, policy="history_index")
        self.assertIs(shown, baseline)
        self.assertFalse(status["changed"])
        self.assertEqual(status["reason"], "no_exact_source_pages_qualified")

    def test_unattested_context_never_sends_unverifiable_locator(self):
        ctx = ClmContext(pinned=PINNED, settings=ClmSettings())
        ctx.append(action(1), result(1, "history"))
        ok, _ = ctx.apply_edit("a model note", len(ctx.editable))
        self.assertTrue(ok)
        baseline = ctx.request()
        shown, status = select_context(ctx, baseline, HISTORY_TOOL, policy="history_index")
        self.assertIs(shown, baseline)
        self.assertFalse(status["changed"])

    def test_prepopulated_unattested_history_cannot_be_passed_off_as_attested(self):
        with self.assertRaises(ValueError):
            ClmContext(
                pinned=PINNED,
                raw=[result(0, "older source")],
                settings=ClmSettings(attest_original_history=True),
            )

    def test_config_evidence_feature_requires_source_attestation(self):
        with self.assertRaises(ValueError):
            CoreConfig(context="clm", evidence_presentation="history_index")
        self.assertEqual(
            CoreConfig(
                context="clm",
                evidence_presentation="history_index",
                clm=ClmSettings(attest_original_history=True),
            ).evidence_presentation,
            "history_index",
        )

    def test_native_responses_provider_preserves_encrypted_reasoning_and_tools(self):
        from aether.core.responses import ResponsesProvider

        ctx = edited(action(1), result(1, "older historical result"))
        reasoning = {
            "type": "reasoning", "id": "old_experiment_reasoning",
            "encrypted_content": "opaque_do_not_serialize_into_card", "summary": [],
        }
        new_call = action(2)
        new_call["reasoning_content"] = [reasoning]
        ctx.append(new_call, result(2, "latest real tool observation"))
        tools = HISTORY_TOOL
        provider = ResponsesProvider(
            None, model="Luna_stub_no_provider_request",
            params={"reasoning_effort": "high", "tool_choice": "required",
                    "parallel_tool_calls": False},
            cache_key="stable_experiment_cache_key",
        )
        control_msgs = ctx.request()
        control = provider._request(control_msgs, tools, 8192, None)
        msgs, status = select_context(
            ctx, control_msgs, tools, policy="history_index"
        )
        self.assertTrue(status["changed"])
        treated = provider._request(msgs, tools, 8192, None)
        self.assertEqual(control["params"], treated["params"])
        self.assertEqual(control["tools"], treated["tools"])
        self.assertEqual(control["input"], treated["input"][:-1])
        self.assertEqual(treated["input"][-1]["role"], "user")
        self.assertIn(reasoning, control["input"])
        self.assertNotIn("opaque_do_not_serialize_into_card", msgs[-1]["content"])

    def test_native_chat_provider_preserves_tools_and_original_request_prefix(self):
        from aether.core.provider import ChatProvider

        ctx = edited(action(1), result(1, "older historical source"))
        provider = ChatProvider(
            None, model="flint_stub_no_provider_request",
            params={"reasoning_effort": "high", "parallel_tool_calls": False},
        )
        baseline = ctx.request()
        request = provider._request(baseline, HISTORY_TOOL, 8192, None)
        alternative, status = select_context(
            ctx, baseline, HISTORY_TOOL, policy="history_index"
        )
        self.assertTrue(status["changed"])
        treated = provider._request(alternative, HISTORY_TOOL, 8192, None)
        self.assertEqual(request["messages"], treated["messages"][:-1])
        self.assertEqual(request["tools"], treated["tools"])
        self.assertEqual(request["params"], treated["params"])
        self.assertEqual(request["model"], treated["model"])

    def test_rollback_off_exact_identity(self):
        ctx = edited(action(1), result(1, "history"))
        base = ctx.request()
        augmented, info = select_context(ctx, base, HISTORY_TOOL, policy="history_index")
        self.assertTrue(info["changed"])
        off, status = select_context(ctx, base, HISTORY_TOOL, policy="off")
        self.assertIs(off, base)
        self.assertNotEqual(augmented, off)


if __name__ == "__main__":
    unittest.main()
