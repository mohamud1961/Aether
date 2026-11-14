"""Combined real Core CLM recovery + file/evidence mechanics; scripted, no inference."""
import asyncio
import hashlib
import json
import re
import time

import pytest

from aether.core.clm import ClmSettings
from aether.core.harbor_agent import _write_record
from aether.core.loop import CoreConfig, Trace, run_agent
from aether.core.provider import ChatProvider
from tests.core_fakes import LocalEnv, ScriptedClient, call


def normalized(value):
    if isinstance(value, list): return [normalized(v) for v in value]
    if isinstance(value, dict): return {k: normalized(v) for k,v in value.items()}
    if not isinstance(value, str): return value
    value = re.sub(r'\[t=\d+(?:\.\d+)?s of [\d.]+s\]', '[t=<elapsed>s of <limit>s]', value)
    return re.sub(r'(\[exit -?\d+ · )\d+(?:\.\d+)?s', r'\g<1><elapsed>s', value)


async def trial(root, policy, notes):
    work, ctl = root/'work', root/'ctl'
    work.mkdir(exist_ok=True)
    mirror, history = root/'ctx'/'LIVE_CTX.txt', root/'ctx'/'HISTORY.txt'
    payload = 'ORIGINAL-α-' + 'x'*30_000 + '-TAIL-雪\n'
    (work/'source.txt').write_text(payload)
    (work/'artifact.txt').unlink(missing_ok=True)
    script = [
        call('read_file', {'path':'source.txt'}, 'source'),
        call('write_file', {'path':str(mirror), 'content':'[[CTX_TURN 0 role=user]]\nMy work notes; source omitted.'}, 'edit'),
        call('read_history', {'message_id':1,'offset':0,'limit':12000}, 'page0'),
        call('read_history', {'message_id':1,'offset':12000,'limit':12000}, 'page1'),
        call('read_history', {'message_id':1,'offset':24000,'limit':12000}, 'page2'),
        call('write_file', {'path':'artifact.txt','content':'recovered source; correct artifact\n'}, 'artifact'),
        call('finish', {'summary':'scripted source recovery'}, 'finish'),
    ]
    client = ScriptedClient(script)
    provider = ChatProvider(client,model='scripted-offline',params={'tool_choice':'required','parallel_tool_calls':False})
    config = CoreConfig(context='clm',evidence_presentation=policy,control_dir=str(ctl),end_processes='stop',record=True,
        clm=ClmSettings(notes_voice=notes,mirror_path=str(mirror),history_path=str(history),attest_original_history=policy=='history_index'))
    trace = root/f'{policy}.jsonl'
    result = await run_agent(env=LocalEnv(work),task='Read source.txt, recover original evidence after editing notes, and write artifact.txt.',
        workdir=str(work),provider=provider,timeout_s=90,trace=Trace(trace),config=config)
    rows = [json.loads(s) for s in trace.read_text().splitlines()]
    assert result.status=='finished' and not result.extras['cleanup_errors'] and not result.extras['left_running']
    assert (work/'artifact.txt').read_bytes()==b'recovered source; correct artifact\n'
    edits=[r for r in rows if r['event']=='context_edit' and r.get('accepted')]
    assert len(edits)==1
    pages=[r['result'].split('\n',1)[1] for r in rows if r['event']=='tool' and r.get('name')=='read_history']
    original=json.loads(''.join(pages))
    first=next(r['result'] for r in rows if r['event']=='tool' and r.get('name')=='read_file')
    assert original['role']=='tool' and original['tool_call_id']=='source'
    assert original['content'].startswith(first) and 'ORIGINAL-α-' in original['content'] and '-TAIL-雪' in original['content']
    if policy=='history_index':
        events=[r for r in rows if r['event']=='context_evidence_presentation']
        assert sum(r.get('changed') is True for r in events)==1
        card=json.loads(client.requests[2]['messages'][-1]['content'].split('\n',1)[1])
        entry=next(r for r in card['records'] if r['message_id']==1)
        assert entry['sha256']==hashlib.sha256(json.dumps(original,ensure_ascii=False).encode()).hexdigest()
    logs=root/f'logs-{policy}'
    _write_record(logs,result,started=time.time(),workdir=str(work),config=config,review=None,provider=provider)
    record=json.loads((logs/'aether_run_record.json').read_text())
    assert record['config']['evidence_presentation']==policy
    assert record['config']['clm']['attest_original_history'] is (policy=='history_index')
    return client.requests


@pytest.mark.parametrize('notes',['legacy','own'])
def test_combined_clm_recovery_and_default_off_preservation(tmp_path,notes):
    off=asyncio.run(trial(tmp_path,'off',notes))
    on=asyncio.run(trial(tmp_path,'history_index',notes))
    assert normalized(off[:2])==normalized(on[:2])
    assert normalized(off[2]['messages'])==normalized(on[2]['messages'][:-1])
    assert off[2]['tools']==on[2]['tools'] and off[2]['model']==on[2]['model']
    assert all(not any('Historical Core tool references;' in str(m.get('content')) for m in r['messages']) for r in on[3:])


def test_exact_path_finds_historical_result_after_overwrite_and_context_edit(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "original").write_text("first measurement α\n")
    (work / "other").write_text("different input\n")
    mirror = tmp_path / "control" / "live"
    history = tmp_path / "control" / "history"
    class RecoveringClient(ScriptedClient):
        async def _create(self, **kwargs):
            tools = {m["tool_call_id"]: m["content"] for m in kwargs["messages"] if m["role"] == "tool"}
            if len(self.requests) == 5:
                locator, _ = json.JSONDecoder().raw_decode(tools["locate"])
                self.script.insert(0, call("read_history", {"message_id": locator["records"][0]["message_id"]}, "retrieve"))
            if len(self.requests) == 7:
                archived, _ = json.JSONDecoder().raw_decode(tools["retrieve"].split("\n", 1)[1])
                measured_line = next(line for line in archived["content"].splitlines() if "measurement" in line)
                self.script.insert(0, call("write_file", {"path": "comparison", "content": measured_line.split()[-1]}, "deliver"))
            return await super()._create(**kwargs)

    client = RecoveringClient([
        call("read_file", {"path": "original"}, "early"),
        call("read_file", {"path": "other"}, "other"),
        call("write_file", {"path": "original", "content": "current data\n"}, "replace"),
        call("write_file", {"path": str(mirror), "content": "[[CTX_TURN 0 role=user]]\nOnly keep these notes."}, "compact"),
        call("find_history", {"path": "original"}, "locate"),
        call("read_file", {"path": "original"}, "current"),
        call("finish", {"summary": "Done."}, "finish"),
    ])
    result = asyncio.run(run_agent(
        env=LocalEnv(work), task="Compare old and current contents.", workdir=str(work),
        provider=ChatProvider(client, model="offline", params={}), timeout_s=40, trace=Trace(tmp_path / "trace"),
        config=CoreConfig(context="clm", evidence_presentation="path_lookup", control_dir=str(mirror.parent),
                          clm=ClmSettings(attest_original_history=True, mirror_path=str(mirror), history_path=str(history))),
    ))
    assert result.status == "finished"
    assert not any("first measurement" in str(m.get("content")) for m in client.requests[4]["messages"])
    messages = {m["tool_call_id"]: m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"}
    located, _ = json.JSONDecoder().raw_decode(messages["locate"])
    original, _ = json.JSONDecoder().raw_decode(messages["retrieve"].split("\n", 1)[1])
    assert located["matched"] == 1 and located["records"][0]["message_id"] == 1
    assert located["records"][0]["sha256"] == hashlib.sha256(json.dumps(original, ensure_ascii=False).encode()).hexdigest()
    assert original["tool_call_id"] == "early" and "first measurement α" in original["content"]
    assert "current data" in messages["current"] and (work / "original").read_text() == "current data\n"
    assert (work / "comparison").read_text() == "α"
