import json
from pathlib import Path
from evals.performance.phase_f_final_audit import EXPECTED,audit


def write_row(root:Path,ordinal:int,task:str,version:str,**overrides):
 rid=f'phase-f-{version}-{ordinal:02d}-{task}-20260907';(root/'_s6_controller').mkdir(parents=True,exist_ok=True)
 metrics={'valid':True,'official_reward':1.0,'aether_terminal_status':'completed','solver_provider_turns':1,'solver_previous_response_chain_intact':True}
 metrics.update(overrides)
 (root/f'{rid}.typed_metrics.json').write_text(json.dumps(metrics))
 (root/'_s6_controller'/f'{rid}.completed.json').write_text(json.dumps({'child_custody':{'valid':True}}))


def test_mixed_v2_v3_v4_complete_and_continuity_visible(tmp_path):
 roots={k:tmp_path/k for k in ('v2','v3','v4')}
 for p in roots.values():p.mkdir()
 for ordinal,task,version in EXPECTED:
  extra={'solver_previous_response_chain_intact':False} if ordinal==7 else {}
  write_row(roots[version],ordinal,task,version,**extra)
 out=audit(roots['v2'],roots['v3'],roots['v4'])
 assert out['complete'] is True
 assert out['row_count']==15
 assert out['solver_continuity_break_count']==1
 assert out['rows'][13]['campaign']=='v4'
 assert out['rows'][14]['campaign']=='v4'
