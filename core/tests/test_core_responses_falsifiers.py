"""Provider boundary falsifiers: malformed native Responses actions are never dispatchable."""
import asyncio
from types import SimpleNamespace

import pytest

from aether.core.calls import CallLog
from aether.core.provider import IncompleteStream, Turn
from aether.core.responses import ResponsesProvider


def event(kind, **fields):
    return SimpleNamespace(type=kind, **fields)


def done_item(**fields):
    return SimpleNamespace(model_dump=lambda exclude_none=True: dict(fields))


class Stream:
    def __init__(self, rows): self.rows=iter(rows)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self.rows)
        except StopIteration:
            raise StopAsyncIteration


class Client:
    def __init__(self, rows):
        self.rows = rows
        self.responses = SimpleNamespace(create=self.create)

    async def create(self, **kwargs):
        return Stream(self.rows)


class SequenceClient:
    def __init__(self, streams):
        self.streams = list(streams)
        self.responses = SimpleNamespace(create=self.create)

    async def create(self, **kwargs):
        return Stream(self.streams.pop(0))


def test_native_responses_rejects_duplicate_function_call_ids(tmp_path):
    rows=[event('response.output_item.done',item=done_item(type='function_call',call_id='same',name='terminal',arguments='{}')),
          event('response.output_item.done',item=done_item(type='function_call',call_id='same',name='finish',arguments='{}')),
          event('response.completed',response=SimpleNamespace(id='r',model='m',status='completed',usage=None))]
    p=ResponsesProvider(Client(rows),model='m',params={},log=CallLog(tmp_path/'calls'))
    with pytest.raises(IncompleteStream,match='duplicate'):
        asyncio.run(p._stream_once(p._request([],[],20,None),Turn()))


def test_native_responses_rejects_missing_function_call_id(tmp_path):
    rows=[event('response.output_item.done',item=done_item(type='function_call',name='terminal',arguments='{}')),
          event('response.completed',response=SimpleNamespace(id='r',model='m',status='completed',usage=None))]
    p=ResponsesProvider(Client(rows),model='m',params={},log=CallLog(tmp_path/'calls'))
    with pytest.raises(IncompleteStream,match='call ID'):
        asyncio.run(p._stream_once(p._request([],[],20,None),Turn()))


def test_duplicate_native_calls_are_rejected_before_real_loop_dispatch(tmp_path):
    from aether.core.loop import CoreConfig, Trace, run_agent
    from tests.core_fakes import LocalEnv

    work = tmp_path / 'work'
    work.mkdir()
    marker = work / 'must-not-exist'
    invalid = [
        event('response.output_item.done', item=done_item(
            type='function_call', call_id='same', name='terminal',
            arguments='{"input":"touch must-not-exist"}')),
        event('response.output_item.done', item=done_item(
            type='function_call', call_id='same', name='terminal',
            arguments='{"input":"touch must-not-exist-too"}')),
        event('response.completed', response=SimpleNamespace(
            id='bad', model='m', status='completed', usage=None)),
    ]
    valid = [
        event('response.output_item.done', item=done_item(
            type='function_call', call_id='good', name='finish',
            arguments='{"summary":"done"}')),
        event('response.completed', response=SimpleNamespace(
            id='good', model='m', status='completed', usage=None)),
    ]
    client = SequenceClient([invalid, valid])
    log = CallLog(tmp_path/'calls')
    async def no_wait(_seconds): return None
    p = ResponsesProvider(client, model='m', params={'tool_choice':'required'}, log=log, sleep=no_wait)
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task='Do no work for this transport test.', workdir=str(work),
        provider=p, timeout_s=60, trace=Trace(tmp_path/'trace.jsonl'),
        config=CoreConfig(control_dir=str(tmp_path/'ctl'))))
    assert result.status == 'finished'
    assert not marker.exists() and not (work/'must-not-exist-too').exists()
    attempts = list(__import__('aether.core.calls', fromlist=['requests']).requests(tmp_path/'calls'))
    assert [(x['attempt'], x['ok']) for x in attempts] == [(1, False), (2, True)]


def test_seeded_native_history_pairing_property_preserves_every_call_and_output():
    import json
    import random

    from aether.core.responses import input_items

    rng = random.Random(20261025)
    messages = [{'role': 'system', 'content': 'system α'}, {'role': 'user', 'content': 'task 雪'}]
    expected = [{'role': 'system', 'content': 'system α'}, {'role': 'user', 'content': 'task 雪'}]
    for group in range(40):
        calls = []
        outputs = []
        reasoning = {'type': 'reasoning', 'id': f'r-{group}',
                     'encrypted_content': f'enc-{group}-☃', 'content': f'summary {group}', 'summary': []}
        for slot in range(rng.randint(1, 4)):
            identity = f'call-{group}-{slot}-{rng.randrange(1_000_000)}'
            name = f'tool_{rng.randrange(100)}'
            arguments = json.dumps({'group': group, 'slot': slot, 'unicode': 'α雪\n',
                                    'value': rng.randrange(10**9)}, ensure_ascii=False)
            output = f"observed {identity} · α雪\n"
            calls.append({'id': identity, 'type': 'function',
                          'function': {'name': name, 'arguments': arguments}})
            outputs.append({'role': 'tool', 'tool_call_id': identity, 'content': output})
        messages.append({'role': 'assistant', 'content': None,
                         'reasoning_content': [reasoning], 'tool_calls': calls})
        messages.extend(outputs)
        user = {'role': 'user', 'content': f'continue {group} · λ'}
        messages.append(user)

        expected.append(reasoning)
        expected.extend({'type': 'function_call', 'call_id': call['id'],
                         'name': call['function']['name'], 'arguments': call['function']['arguments']}
                        for call in calls)
        expected.extend({'type': 'function_call_output', 'call_id': output['tool_call_id'],
                         'output': output['content']} for output in outputs)
        expected.append(user)

    actual = input_items(messages)
    assert actual == expected


def test_seeded_native_stream_identity_fuzz_rejects_bad_groups(tmp_path):
    import random

    rng = random.Random(910247)
    for case in range(48):
        first = f'id-{rng.randrange(10**9)}'
        second = first if case % 2 == 0 else None
        rows = [
            event('response.output_item.done', item=done_item(
                type='function_call', call_id=first, name='terminal', arguments='{}')),
            event('response.output_item.done', item=done_item(
                type='function_call', **({'call_id': second} if second is not None else {}),
                name='terminal', arguments='{}')),
            event('response.completed', response=SimpleNamespace(
                id=f'r-{case}', model='m', status='completed', usage=None)),
        ]
        case_dir = tmp_path / f'case-{case}'
        case_dir.mkdir()
        p = ResponsesProvider(Client(rows), model='m', params={},
                              log=CallLog(case_dir / 'calls'))
        turn = Turn()
        with pytest.raises(IncompleteStream, match='call ID|duplicate'):
            asyncio.run(p._stream_once(p._request([], [], 20, None), turn))
        assert turn.tool_calls == []
