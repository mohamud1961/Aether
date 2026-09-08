from __future__ import annotations
import json
from pathlib import Path
from evals.performance.e2_a2_extract import extract


def test_extracts_actions_submits_verifier_and_failures(tmp_path: Path) -> None:
    p=tmp_path/'run.json'
    payload={
      'runtime_identity':{'task_id':'t','run_id':'r'},'status':'completed','step':3,
      'model_exchange_records':[
        {'model_role':'solver','provider_call_succeeded':True,'output_sha256':'a','output':json.dumps({'kind':'act','action':{'kind':'read_file','arguments':{'path':'x'}}})},
        {'model_role':'solver','provider_call_succeeded':True,'output_sha256':'b','output':json.dumps({'kind':'submit','claim':'done','evidence_refs':['e']})},
        {'model_role':'verifier','provider_call_succeeded':True,'output_sha256':'c','output':json.dumps({'kind':'inspect','requests':[{'kind':'read_file'}]})},
      ],
      'model_call_telemetry':[{'role':'solver','logical_call_id':2,'attempt_ordinal':1,'attempt_phase':'terminal','status':'server_error','elapsed_s':1.2}],
      'receipt_records':[{'kind':'primary_decision'},{'kind':'primary_decision'}],
      'run_metrics':{'solver_parse_error_count':0},
    }
    p.write_text(json.dumps(payload))
    out=extract(p)
    assert out['task_id']=='t'
    assert out['solver_action_count']==1
    assert out['submit_count']==1
    assert out['verifier_turn_count']==1
    assert out['provider_failure_count']==1
    assert out['receipt_kind_counts']['primary_decision']==2
