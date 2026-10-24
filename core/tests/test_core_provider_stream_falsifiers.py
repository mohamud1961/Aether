"""Provider stream protocol adversaries, using production _stream_once and fake chunks."""
from __future__ import annotations
import asyncio
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_core_provider_stream_offline import chunk,tc,invoke
from aether.core.provider import IncompleteStream


class ProtocolFalsifiers(unittest.TestCase):
    def test_two_slots_must_not_share_tool_call_id(self):
        go,turn,stream,_=invoke([chunk(tool_calls=[
            tc(0,id="same-id",name="terminal",arguments='{"input":"echo a"}'),
            tc(1,id="same-id",name="terminal",arguments='{"input":"echo b"}'),
        ],finish="tool_calls")])
        with self.assertRaises(IncompleteStream):
            asyncio.run(go())
        self.assertTrue(stream.closed)
        self.assertEqual(turn.tool_calls,[])

    def test_same_stream_slot_cannot_replace_call_identity(self):
        go,turn,stream,_=invoke([
            chunk(tool_calls=[tc(0,id="first-id",name="terminal",arguments='{"input":')]),
            chunk(tool_calls=[tc(0,id="second-id",arguments='"echo changed"}')],finish="tool_calls"),
        ])
        with self.assertRaises(IncompleteStream):
            asyncio.run(go())
        self.assertTrue(stream.closed)

    def test_missing_tool_name_is_not_a_dispatchable_command(self):
        go,turn,stream,_=invoke([
            chunk(tool_calls=[tc(0,id="valid-id",arguments='{"input":"echo a"}')],finish="tool_calls")
        ])
        with self.assertRaises(IncompleteStream):
            asyncio.run(go())
        self.assertTrue(stream.closed)

    def test_fragmented_tool_name_remains_supported(self):
        go,turn,stream,_=invoke([
            chunk(tool_calls=[tc(0,id="valid-id",name="ter",arguments='{"input":')]),
            chunk(tool_calls=[tc(0,name="minal",arguments='"echo yes"}')],finish="tool_calls"),
        ])
        asyncio.run(go())
        self.assertEqual(turn.tool_calls[0]["function"]["name"],"terminal")
        self.assertTrue(stream.closed)

    def test_missing_id_can_use_unique_generated_fallback(self):
        go,turn,stream,_=invoke([
            chunk(tool_calls=[tc(0,name="terminal",arguments='{"input":"echo yes"}')],finish="tool_calls"),
        ])
        asyncio.run(go())
        self.assertEqual(turn.tool_calls[0]["id"],"call_0")
        self.assertTrue(stream.closed)

if __name__=="__main__":
    unittest.main(verbosity=2)
