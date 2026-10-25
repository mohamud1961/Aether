"""A retried Chat response cannot execute a partial tool action twice."""
import asyncio
import json

from openai import AsyncOpenAI

from aether.core.calls import CallLog, requests
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv
from tests.test_core_http import server, sse


def test_real_sdk_retry_dispatches_only_the_completed_tool_turn(tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    calls = tmp_path / 'calls.jsonl'
    trace_path = tmp_path / 'trace.jsonl'
    arguments = json.dumps({'input': 'printf "effect\\n" >> effects.txt'})
    partial = sse([({'tool_calls': [{'index': 0, 'id': 'write-once', 'type': 'function',
                                    'function': {'name': 'terminal', 'arguments': arguments}}]}, None)])
    completed = sse([({'tool_calls': [{'index': 0, 'id': 'write-once', 'type': 'function',
                                      'function': {'name': 'terminal', 'arguments': arguments}}]}, None),
                     ({}, 'tool_calls')])
    finish = sse([({'tool_calls': [{'index': 0, 'id': 'finish', 'type': 'function',
                                   'function': {'name': 'finish', 'arguments': '{"summary":"done"}'}}]}, None),
                  ({}, 'tool_calls')])
    with server([partial, completed, finish]) as (url, seen):
        async def execute():
            async with AsyncOpenAI(api_key='offline-fixture-key', base_url=url + '/openai/v1/',
                                   max_retries=0) as client:
                provider = ChatProvider(client, model='scripted', params={},
                                        log=CallLog(calls), sleep=lambda _: asyncio.sleep(0))
                return await run_agent(env=LocalEnv(work), task='Append one effect line then finish.',
                                       workdir=str(work), provider=provider, timeout_s=60,
                                       trace=Trace(trace_path), config=CoreConfig(control_dir=str(tmp_path/'ctl')))
        result = asyncio.run(execute())

    assert result.status == 'finished'
    assert (work / 'effects.txt').read_text() == 'effect\n'
    rows = list(requests(calls))
    assert [(row['attempt'], row['ok']) for row in rows] == [(1, False), (2, True), (1, True)]
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    tool_rows = [row for row in trace if row.get('event') == 'tool' and row.get('name') == 'terminal']
    assert len(tool_rows) == 1
    model_rows = [row for row in trace if row.get('event') == 'model']
    assert len(model_rows) == 2 and model_rows[0]['attempts'] == 2
    assert len(seen) == 3
