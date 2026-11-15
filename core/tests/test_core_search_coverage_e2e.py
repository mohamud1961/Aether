"""Search reports when a policy excludes parts of a real task workspace."""

import asyncio
import hashlib
import json
import sys

import pytest

from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux descriptor-scoped workspace search')


def run_search(work, control, trace, calls):
    client = ScriptedClient([*calls, call('finish', {'summary': 'done'}, 'finish')])
    result = asyncio.run(run_agent(env=LocalEnv(work), task='Find the requested literal in this workspace.',
        workdir=str(work), provider=ChatProvider(client, model='scripted', params={}), trace=Trace(trace),
        timeout_s=30, config=CoreConfig(workspace_search=True, control_dir=str(control))))
    assert result.status == 'finished'
    return {message['tool_call_id']: message['content'] for message in client.requests[-1]['messages']
            if message['role'] == 'tool'}


def search(call_id, query='NEEDLE', **args):
    return call('search_workspace', {'mode': 'text', 'query': query, **args}, call_id)


def test_hidden_policy_is_disclosed_and_explicit_read_recovers_evidence(tmp_path):
    work = tmp_path / 'work'
    (work / '.settings').mkdir(parents=True)
    (work / 'tmp').mkdir()
    hidden = work / '.settings' / 'required.txt'
    hidden.write_text('NEEDLE is here\n')
    (work / 'tmp' / 'ordinary.txt').write_text('unrelated\n')
    observations = run_search(work, tmp_path / 'control', tmp_path / 'trace', [
        search('broad'), search('explicit', subdir='.settings'),
        call('read_file', {'path': '.settings/required.txt'}, 'read')])
    broad = json.JSONDecoder().raw_decode(observations['broad'])[0]
    explicit = json.JSONDecoder().raw_decode(observations['explicit'])[0]
    assert broad['status'] == 'partial' and broad['matches_total'] == 0
    assert broad['policy_skipped']['hidden_directories'] == 1
    assert explicit['status'] == 'searched' and explicit['matches_total'] == 1
    assert explicit['matches'][0]['sha256'] == hashlib.sha256(hidden.read_bytes()).hexdigest()
    assert 'NEEDLE is here' in observations['read']


def test_mixed_scope_preserves_legitimate_tmp_and_explicit_control_access(tmp_path):
    work = tmp_path / 'work'
    for name, text in {'tmp/real.txt': 'NEEDLE\n', '.settings/hidden.txt': 'NEEDLE\n',
                       '.git/config': 'NEEDLE\n', 'node_modules/pkg/data': 'NEEDLE\n',
                       'control/history.txt': 'NEEDLE\n'}.items():
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    (work / 'link').symlink_to(work / 'tmp', target_is_directory=True)
    observations = run_search(work, work / 'control', tmp_path / 'trace', [
        search('mixed'), search('hidden', subdir='.settings'), search('control', subdir='control'),
        call('read_file', {'path': 'control/history.txt'}, 'history')])
    mixed = json.JSONDecoder().raw_decode(observations['mixed'])[0]
    hidden = json.JSONDecoder().raw_decode(observations['hidden'])[0]
    assert mixed['status'] == 'partial' and mixed['skipped_or_limited'] >= 1  # symlink
    assert mixed['policy_skipped'] == {'known_paths': 2, 'hidden_directories': 1, 'control': 1}
    assert [row['path'] for row in mixed['matches']] == ['tmp/real.txt']
    assert [row['path'] for row in hidden['matches']] == ['.settings/hidden.txt']
    assert '"status":"scope_unavailable"' in observations['control']
    assert 'NEEDLE' in observations['history']


def test_tree_without_exclusions_remains_complete(tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'source.txt').write_text('NEEDLE\n')
    result = run_search(work, tmp_path / 'control', tmp_path / 'trace', [search('clean')])
    clean = json.JSONDecoder().raw_decode(result['clean'])[0]
    assert clean['status'] == 'searched' and clean['matches_total'] == 1
    assert not clean.get('policy_skipped')
