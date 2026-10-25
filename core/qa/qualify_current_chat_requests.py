#!/usr/bin/env python3
"""Replay eligible captured Chat packets through the installed current adapter, no I/O client.

Uses an already T0/T1-qualified corpus with explicit roots. Does not execute tools,
call a model, or reconstruct native Responses input as Chat. Outputs no payloads.
"""
import argparse
import gzip
import json
from pathlib import Path

import replay_corpus as replay
from aether.core.provider import ChatProvider


def require(condition, label):
    if not condition:
        raise ValueError(label)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('corpus', 'roots', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--expected-corpus-sha256', required=True)
    p.add_argument('--expected-chat', type=int, required=True)
    p.add_argument('--expected-non-chat', type=int, required=True)
    args = p.parse_args()
    with gzip.open(args.corpus, 'rt') as stream:
        corpus = json.load(stream)
    require(replay._manifest_digest(corpus) == args.expected_corpus_sha256, 'corpus digest mismatch')
    roots = json.loads(args.roots.read_text())
    passed = skipped = 0
    protected = ('rolling-shutter', 'extract-elf', 'make-doom')
    for root in roots.values():
        require(not any(n in str(root).lower() or n in str(Path(root).resolve()).lower() for n in protected), 'protected root denied')
    for case in corpus['cases']:
        require(not any(n in json.dumps(case['source_symbol']).lower() for n in protected), 'protected source denied')
        if not case['expected']['client_capture_present']:
            continue
        trace, reason = replay.resolve_symbol(case['source_symbol'], roots)
        if trace is None:
            raise RuntimeError(reason)
        rows, errors = replay.read_jsonl(trace.with_name('core_calls.jsonl').read_bytes())
        require(not errors, 'invalid call-log JSON')
        parsed = replay.parse_call_log(rows)
        for row in case['requests']:
            if row.get('fidelity') != replay.EXACT_FIDELITY:
                continue
            start = parsed['starts'][row['client_call_seq']]
            source, misses = replay.expand_request(start.get('request') or {}, parsed['blobs'])
            require(not misses and replay.sha256_bytes(replay.canonical(source)) == row['resolved_request_sha256'], 'captured request hash mismatch')
            if 'messages' not in source:
                skipped += 1
                continue
            field = next(k for k in ('max_tokens', 'max_completion_tokens') if k in source)
            # No usable client is supplied: only the real pure adapter is exercised.
            adapter = ChatProvider(None, model=source['model'], params=source.get('params', {}), limit_field=field)
            before = replay.canonical(source['messages'])
            actual = adapter._request(source['messages'], source.get('tools'), source[field], None)
            require(replay.canonical(actual['messages']) == before, 'current adapter altered messages')
            require(actual['model'] == source['model'] and actual[field] == source[field], 'model or ceiling changed')
            require(actual.get('tools') == source.get('tools'), 'tool schema changed')
            expected_params = dict(source.get('params', {}))
            expected_params.update(stream=True, stream_options={'include_usage': True})
            if expected_params.get('reasoning_effort', '') is None:
                expected_params.pop('reasoning_effort')
            if source.get('tools') is None:
                expected_params.pop('tool_choice', None)
                expected_params.pop('parallel_tool_calls', None)
            require(actual['params'] == expected_params, 'unexpected provider parameters')
            require(replay.canonical(source['messages']) == before, 'source messages mutated')
            passed += 1
    require(passed > 0 and passed == args.expected_chat and skipped == args.expected_non_chat, 'declared packet denominator mismatch')
    result = {'scope': 'installed current Chat adapter, historical packets; no CLM reconstruction, action execution, model inference or grading',
              'corpus_sha256': args.expected_corpus_sha256, 'expected_chat': args.expected_chat, 'expected_non_chat': args.expected_non_chat,
              'chat_packets_passed': passed, 'non_chat_packets_not_converted': skipped,
              'core_provider_module': __import__('aether.core.provider', fromlist=['x']).__file__}
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
