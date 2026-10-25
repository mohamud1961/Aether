"""Recreated export workflow: wrong self-test, independent contract, actual rebuild.

Fixed synthetic schema/reshard workload; real installed Core/process effects.
No historical environment or model-inference claim.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import pytest
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call

CONVERTER = '''import hashlib,json,pathlib
root=pathlib.Path('export'); root.mkdir(exist_ok=True)
rows=[json.loads(s) for s in pathlib.Path('input.jsonl').read_text().splitlines()]
manifest=[]
for part in range(4):
    subset=[{'id':r['id'],'val':r['value']} for r in rows if r['id']%4==part]
    data=''.join(json.dumps(r,ensure_ascii=False)+'\\n' for r in subset).encode()
    name='part-'+str(part)+'.jsonl'; (root/name).write_bytes(data)
    manifest.append({'name':name,'rows':len(subset),'sha256':hashlib.sha256(data).hexdigest()})
(root/'manifest.json').write_text(json.dumps(manifest))
'''
SELF_CHECK = '''import json,pathlib
for p in pathlib.Path('export').glob('part-*.jsonl'):
    for s in p.read_text().splitlines(): assert isinstance(json.loads(s)['val'],str)
print('self-check passed')
'''
PUBLIC_CHECK = '''import json,pathlib
for p in pathlib.Path('export').glob('part-*.jsonl'):
    for s in p.read_text().splitlines(): assert set(json.loads(s)) == {'id','value'}
print('public schema check passed')
'''


def grade_export(work, expected):
    """Independent oracle checks every row, partition/order and manifest content."""
    root = work / 'export'
    try:
        manifest = json.loads((root / 'manifest.json').read_text())
        if len(manifest) != 4 or {m['name'] for m in manifest} != {f'part-{i}.jsonl' for i in range(4)}: return False
        for part in range(4):
            name = f'part-{part}.jsonl'; raw = (root / name).read_bytes()
            rows = [json.loads(s) for s in raw.decode().splitlines()]
            if rows != [r for r in expected if r['id'] % 4 == part]: return False
            entry = next(m for m in manifest if m['name'] == name)
            if entry['rows'] != len(rows) or entry['sha256'] != hashlib.sha256(raw).hexdigest(): return False
        return True
    except (OSError, ValueError, KeyError, StopIteration): return False


@pytest.mark.parametrize('repair', [False, True], ids=['coupled-wrong', 'repaired'])
def test_export_needs_independent_contract_and_actual_rebuild(tmp_path, repair):
    work, ctl = tmp_path / 'work', tmp_path / 'ctl'; work.mkdir()
    expected = [{'id':i,'value':f'α-{i}-雪'} for i in range(500)]
    (work / 'input.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in expected))
    (work / 'contract_check.py').write_text(PUBLIC_CHECK)
    script = [
        call('write_file', {'path':'convert.py','content':CONVERTER}, 'source'),
        call('write_file', {'path':'self_check.py','content':SELF_CHECK}, 'selftest'),
        call('terminal', {'input':'python3 convert.py'}, 'build-wrong'),
        call('terminal', {'input':'python3 self_check.py'}, 'coupled-check'),
        call('terminal', {'input':'python3 contract_check.py'}, 'independent-fail'),
        call('read_file', {'path':'convert.py'}, 'inspect-source'),
        call('read_file', {'path':'export/manifest.json'}, 'inspect-manifest'),
    ]
    if repair:
        script.extend([
            call('edit_file', {'path':'convert.py','old_str':"'val'",'new_str':"'value'"}, 'fix-source'),
            call('edit_file', {'path':'self_check.py','old_str':"'val'",'new_str':"'value'"}, 'fix-selftest'),
            call('terminal', {'input':'python3 convert.py'}, 'actual-rebuild'),
            call('terminal', {'input':'python3 self_check.py'}, 'selftest-again'),
            call('terminal', {'input':'python3 contract_check.py'}, 'independent-pass'),
        ])
    script.append(call('finish', {'summary':'scripted export; independent artifact oracle applies'}, 'finish'))
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task='Export input.jsonl into four id%4 partitions. Preserve every row, order and exact id/value schema; manifest must describe actual final bytes.',
        workdir=str(work), provider=ChatProvider(ScriptedClient(script),model='scripted',params={}),timeout_s=120,
        trace=Trace(tmp_path / 'trace.jsonl'),config=CoreConfig(control_dir=str(ctl),end_processes='stop'),
    ))
    assert result.status == 'finished'
    rows = [json.loads(s) for s in (tmp_path / 'trace.jsonl').read_text().splitlines()]
    terminal = [r for r in rows if r['event']=='tool' and r.get('name')=='terminal']
    assert 'self-check passed' in terminal[1]['result'] and '[exit 0' in terminal[1]['result']
    assert '[exit 1' in terminal[2]['result']
    assert grade_export(work, expected) is repair
    assert not result.extras['cleanup_errors'] and not result.extras['left_running']
    if repair:
        assert 'public schema check passed' in terminal[-1]['result']
        measured = {Path(f['path']).relative_to(work).as_posix():f for f in result.extras['finish_report']['delivered_files']}
        for p in (work / 'export').iterdir():
            assert measured[p.relative_to(work).as_posix()]['sha256'] == hashlib.sha256(p.read_bytes()).hexdigest()

        # Falsify the artifact oracle independently: duplicate manifest entries,
        # then a self-consistent incomplete export, must both be rejected.
        manifest_path = work / 'export/manifest.json'
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        manifest_path.write_text(json.dumps(manifest + [manifest[0]]))
        assert not grade_export(work, expected)
        part_path = work / 'export/part-0.jsonl'
        part_bytes = part_path.read_bytes()
        try:
            shortened = b'\n'.join(part_bytes.splitlines()[1:]) + b'\n'
            part_path.write_bytes(shortened)
            manifest[0]['rows'] -= 1
            manifest[0]['sha256'] = hashlib.sha256(shortened).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            assert not grade_export(work, expected)
        finally:
            part_path.write_bytes(part_bytes)
            manifest_path.write_bytes(manifest_bytes)
        assert grade_export(work, expected)
