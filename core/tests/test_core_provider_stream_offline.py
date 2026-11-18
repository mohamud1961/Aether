"""Scripted streamed provider assembly without any actual model or API.

Exercises production Provider._stream_once using a fake async stream.
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as Obj
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from aether.core.provider import ChatProvider as Provider,Turn,IncompleteStream


def tc(index, *, id=None, name=None, arguments=None):
    return Obj(index=index,id=id,function=Obj(name=name,arguments=arguments))

def chunk(*,tool_calls=None,finish=None,content=None,reasoning=None,usage=None):
    return Obj(id="reply-id",model="flint",
               usage=usage,
               choices=[Obj(delta=Obj(content=content,reasoning_content=reasoning,
                                      tool_calls=tool_calls or []),
                            finish_reason=finish)])

class Stream:
    def __init__(self,parts,close_error=None):
        self.parts=list(parts)
        self.close_error=close_error
        self.closed=False
    def __aiter__(self):
        self._iter=iter(self.parts)
        return self
    async def __anext__(self):
        try:return next(self._iter)
        except StopIteration:raise StopAsyncIteration
    async def aclose(self):
        self.closed=True
        if self.close_error:raise self.close_error

class Completion:
    def __init__(self,stream):
        self.stream=stream
        self.args=[]
    async def create(self,**kwargs):
        self.args.append(kwargs)
        return self.stream

def invoke(parts,close_error=None):
    stream=Stream(parts,close_error=close_error)
    endpoint=Completion(stream)
    provider=Provider.__new__(Provider)
    provider._client=Obj(chat=Obj(completions=endpoint))
    turn=Turn()
    async def go():
        await provider._stream_once({"model":"flint","messages":[],"params":{"stream":True}},turn)
    return go,turn,stream,endpoint


class StreamTests(unittest.TestCase):
    def test_interleaved_fragments_reassemble_exact_call_arguments(self):
        go,turn,stream,endpoint=invoke([
          chunk(tool_calls=[tc(0,id="a1",name="terminal",arguments='{"input":')]),
          chunk(tool_calls=[tc(1,id="b2",name="read_file",arguments='{"path":')]),
          chunk(tool_calls=[tc(0,arguments='"echo ok"}'),tc(1,arguments='"/app/out"}')],
                finish="tool_calls"),
        ])
        asyncio.run(go())
        self.assertEqual(len(turn.tool_calls),2)
        self.assertEqual([x["id"] for x in turn.tool_calls],["a1","b2"])
        self.assertEqual(turn.tool_calls[0]["function"]["arguments"],'{"input":"echo ok"}')
        self.assertEqual(turn.tool_calls[1]["function"]["arguments"],'{"path":"/app/out"}')
        self.assertTrue(stream.closed)
        self.assertEqual(turn.finish_reason,"tool_calls")
        self.assertEqual(endpoint.args[0]["model"],"flint")

    def test_incomplete_stream_does_not_publish_finished_turn(self):
        go,turn,stream,_=invoke([chunk(tool_calls=[tc(0,id="x",name="terminal",arguments='{"input":')])])
        with self.assertRaises(IncompleteStream):
            asyncio.run(go())
        self.assertTrue(stream.closed)
        self.assertEqual(turn.tool_calls,[])
        self.assertIn(0,turn.streamed_calls)

    def test_delivered_content_and_reasoning_are_kept_separate(self):
        go,turn,_,_=invoke([
          chunk(content="hello ",reasoning="consider ",finish=None),
          chunk(content="world",reasoning="evidence",finish="stop"),
        ])
        asyncio.run(go())
        self.assertEqual(turn.content,"hello world")
        self.assertEqual(turn.reasoning,"consider evidence")
        self.assertEqual(turn.tool_calls,[])

    def test_stream_close_failure_is_recorded_separately(self):
        go,turn,stream,_=invoke([chunk(finish="stop")],close_error=RuntimeError("close transport"))
        asyncio.run(go())
        self.assertTrue(stream.closed)
        self.assertIn("close transport",turn.stream_close_error)

    def test_length_finish_with_partial_call_must_not_be_treated_as_full_valid_json(self):
        go,turn,_,_=invoke([
          chunk(tool_calls=[tc(0,id="x",name="terminal",arguments='{"input":')],finish="length")
        ])
        asyncio.run(go())
        self.assertEqual(turn.finish_reason,"length")
        self.assertEqual(turn.tool_calls[0]["function"]["arguments"],'{"input":')
        # Caller must reject malformed arguments and never execute the partial command.
        self.assertEqual(turn.tool_calls[0]["id"],"x")


if __name__=="__main__":
    unittest.main(verbosity=2)
