"""Replay the real Gate A cap transition through adapter, Hooks and Thin.

Provider-free mechanics evidence: a compact extraction of recorded model
responses and actual public file bytes in a deterministic executor. The fixture
hash points back to the immutable full Gate A capture. This does not measure
live model efficacy.
"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from aether.execution import MemoryExecutor
from aether.model_hooks import ModelHooks
from aether.providers.chat_model import ChatCompletionsModelCallable, _historical_observation_message
from aether.runtime_ir import CapabilityDescriptor, EnvMap
from aether.thin_loop import OUTPUT_CAP_MESSAGE, ThinLoopConfig, run_thin_loop

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'tests/harness/fixtures/gate_a_f06_correction_replay.json'


@pytest.mark.parametrize('mode', ['full_snapshot_control', 'observation_history_v1', 'latest_exchange_v1'])
@pytest.mark.parametrize('second_rejection', [False, True], ids=['cap', 'cap_then_bad_arguments'])
def test_capped_no_action_feedback_never_replaces_an_admitted_read_result(mode, second_rejection):
    fixture = json.loads(FIXTURE.read_text())
    assert fixture['source_run_id'] == 'gate-a-f06-service-corrected-full-20261002-02'
    assert fixture['source_row_result_sha256'] == '53f602ddfea2918f97709b453b6b2c5535621acab9471451e0995483ecb121ba'
    responses = deepcopy(fixture['responses'])
    # The adapter now re-issues a length truncation once at a doubled cap. Keep
    # the real captured cap transition reaching the factual-message path by
    # making the escalated response truncated as well.
    responses.insert(2, deepcopy(responses[1]))
    if second_rejection:
        # Known-bad contract control: a real captured native read with only its
        # argument JSON deliberately corrupted. It must remain unexecuted.
        malformed = deepcopy(responses[3])
        malformed['choices'][0]['message']['tool_calls'][0]['function']['arguments'] = 'not JSON'
        responses.insert(3, malformed)
    old_id = responses[0]['choices'][0]['message']['tool_calls'][0]['id']
    files = {f'/app/workspace/src/{name}': content
             for name, content in fixture['files'].items()}
    sent = []

    def transport(**request):
        sent.append(deepcopy(request))
        return responses[len(sent) - 1]

    model = ChatCompletionsModelCallable(transport=transport, deployment='FW-GLM-5.3-Flash-par',
        expected_returned_model='FW-GLM-5.3-Flash', native_persistent_tools=True)
    hooks = ModelHooks(model, lambda *_a, **_k: '{}', run_id='captured-cap', task_id='captured-cap')
    env = EnvMap(task_prompt='Inspect the service files.', workspace_root='/app/workspace',
        capabilities={'filesystem': CapabilityDescriptor('filesystem', 'files', tool_names=('read_file',))})
    result = run_thin_loop(env, MemoryExecutor(workspace_root='/app/workspace', files=files), hooks,
        config=ThinLoopConfig(max_steps=3, max_solver_turns=len(responses), solver_reality_transport_mode=mode))
    assert len(sent) == len(responses)
    assert result.accounting['solver_protocol_correction_calls'] == 1 + int(second_rejection)
    reads = [r for r in result.receipts if r.kind == 'read_file']
    assert len(reads) == 3 and all(r.success for r in reads)
    assert sent[2]['max_tokens'] == 2 * sent[1]['max_tokens']
    assert {k: v for k, v in sent[2].items() if k != 'max_tokens'} == {k: v for k, v in sent[1].items() if k != 'max_tokens'}
    prior = next(m for m in sent[1]['messages'] if m.get('tool_call_id') == old_id)
    corrected = next(m for m in sent[3]['messages'] if m.get('tool_call_id') == old_id)
    assert files['/app/workspace/src/serve.py'] in prior['content'] or json.dumps(files['/app/workspace/src/serve.py'])[1:-1] in prior['content']
    assert corrected == prior, 'No-action correction must preserve the successful native read/result binding'
    feedback = [m for m in sent[3]['messages'] if m.get('content') == OUTPUT_CAP_MESSAGE]
    assert len(feedback) == 1 and feedback[0]['role'] == 'user'
    assert 'tool_call_id' not in feedback[0]
    if second_rejection:
        second = next(m for m in sent[4]['messages'] if m.get('tool_call_id') == old_id)
        assert second == prior
        repair_feedback = [m for m in sent[4]['messages'] if '[solver_protocol_observation]' in str(m.get('content'))]
        assert len(repair_feedback) == 1 and repair_feedback[0]['role'] == 'user'
    if mode != 'latest_exchange_v1':
        committed = next(m for m in sent[-1]['messages'] if m.get('tool_call_id') == old_id)
        expected = _historical_observation_message(prior) if mode == 'observation_history_v1' else prior
        assert committed == expected, 'Successful correction must not commit feedback as a tool result'
