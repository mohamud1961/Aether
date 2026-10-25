#!/usr/bin/env python3
"""Rebuild eligible native Responses packets through the installed Responses adapter.

The historical input is losslessly grouped into Core's chat-shaped internal messages,
then passed through the actual current ResponsesProvider request builder. No Chat API
flattening, network client, model execution, archive mutation, task action or grade.
"""
import argparse
import copy
import gzip
import json
from pathlib import Path

import replay_corpus as replay
from aether.core.responses import ResponsesProvider

ELIGIBLE_CORPUS_SHA256 = 'e68b715084d89087a289791beb4b072ee1529a47982191eba2cc453343cef447'
NATIVE_RESPONSES_PACKET_COUNT = 312


def require(condition, message):
    if not condition:
        raise ValueError(message)


def to_core_messages(items):
    """Losslessly group native input items into Core's internal history contract."""
    messages = []
    reasoning, calls = [], []

    def flush():
        nonlocal reasoning, calls
        if reasoning or calls:
            require(bool(calls), 'orphan Responses reasoning item has no assistant output')
            messages.append({
                'role': 'assistant', 'content': None,
                **({'reasoning_content': reasoning} if reasoning else {}),
                'tool_calls': calls,
            })
            reasoning, calls = [], []

    for item in items:
        kind = item.get('type')
        if kind == 'reasoning':
            reasoning.append(copy.deepcopy(item))
        elif kind == 'function_call':
            require(item.get('call_id') and item.get('name'), 'native function call lacks identity')
            calls.append({'id': item['call_id'], 'type': 'function',
                          'function': {'name': item['name'], 'arguments': item.get('arguments', '{}')}})
        elif kind == 'function_call_output':
            flush()
            require(item.get('call_id'), 'native function output lacks call ID')
            messages.append({'role': 'tool', 'tool_call_id': item['call_id'],
                             'content': item.get('output', '')})
        elif item.get('role') in ('system', 'user', 'developer'):
            flush()
            messages.append({'role': item['role'], 'content': copy.deepcopy(item.get('content', ''))})
        else:
            raise ValueError(f"unsupported native Responses history item: {kind or item.get('role')}")
    flush()
    return messages


def from_native_tool(spec):
    require(spec.get('type') == 'function' and spec.get('name'), 'unsupported native tool definition')
    fn = {'name': spec['name'], 'parameters': copy.deepcopy(spec['parameters'])}
    if 'description' in spec:
        fn['description'] = spec['description']
    return {'type': 'function', 'function': fn}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--roots', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    with gzip.open(args.corpus, 'rt', encoding='utf-8') as stream:
        corpus = json.load(stream)
    digest = replay._manifest_digest(corpus)
    require(digest == ELIGIBLE_CORPUS_SHA256, 'corpus digest mismatch')
    roots = json.loads(args.roots.read_text())
    protected = ('rolling-shutter', 'extract-elf', 'make-doom')
    for value in roots.values():
        require(not any(token in str(value).lower() or token in str(Path(value).resolve()).lower()
                        for token in protected), 'protected root denied')
    checked = 0
    for case in corpus['cases']:
        symbol = json.dumps(case['source_symbol'], sort_keys=True).lower()
        require(not any(token in symbol for token in protected), 'protected source denied')
        if not case['expected']['client_capture_present']:
            continue
        trace, error = replay.resolve_symbol(case['source_symbol'], roots)
        require(trace is not None, error or 'source resolution failed')
        rows, errors = replay.read_jsonl(trace.with_name('core_calls.jsonl').read_bytes())
        require(not errors, 'invalid client log')
        parsed = replay.parse_call_log(rows)
        for row in case['requests']:
            if row.get('fidelity') != replay.EXACT_FIDELITY:
                continue
            start = parsed['starts'].get(row['client_call_seq'])
            require(start is not None, 'missing matching request start')
            source, misses = replay.expand_request(start.get('request') or {}, parsed['blobs'])
            require(not misses and replay.sha256_bytes(replay.canonical(source)) == row.get('resolved_request_sha256'),
                    'source request reconstruction failed its frozen digest')
            if 'input' not in source:
                continue
            messages = to_core_messages(source['input'])
            tools = [from_native_tool(item) for item in source.get('tools', [])]
            params = source.get('params') or {}
            limit = source.get('max_output_tokens')
            require(type(limit) is int and limit > 0, 'invalid native output-token limit')
            provider = ResponsesProvider(None, model=source['model'], params=params, cache_key='')
            actual = provider._request(messages, tools if 'tools' in source else None, limit, None)
            require(replay.canonical(actual['input']) == replay.canonical(source['input']),
                    'current native Responses input serialization changed history')
            require(actual['model'] == source['model'] and actual['max_output_tokens'] == limit,
                    'current native Responses model/limit differs')
            require(replay.canonical(actual.get('tools')) == replay.canonical(source.get('tools')),
                    'current native Responses tool definitions differ')
            require(replay.canonical(actual['params']) == replay.canonical(params),
                    'current native Responses parameters differ')
            checked += 1
    require(checked == NATIVE_RESPONSES_PACKET_COUNT, 'native Responses packet denominator mismatch')
    result = {
        'scope': 'eligible captured native Responses packets rebuilt by current installed ResponsesProvider; no Chat conversion, network, model, action or grading',
        'corpus_sha256': digest, 'expected_packets': NATIVE_RESPONSES_PACKET_COUNT,
        'native_responses_packets_passed': checked,
        'current_module': __import__('aether.core.responses', fromlist=['x']).__file__,
    }
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
