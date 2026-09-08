from pathlib import Path
from evals.performance import d4_review_policy_board as d4
ROOT=Path(__file__).resolve().parents[1]; M=ROOT/'evals/performance/D4_REVIEW_POLICY_BOARD_V1.json'
def test_d4_provider_free_qualifies_ceilings_known_bad_and_bc_equivalence(tmp_path:Path):
 q=d4.qualify_provider_free(d4.load(M),tmp_path/'q'); assert q['status']=='PASS' and q['case_count']==5 and q['bc_operational_equivalence_proved'] is True
def _row(cid,arm,passed=True,**kw):
 d={'case_id':cid,'arm':arm,'provider_invalid':False,'valid_grader_pass':passed,'false_review_damage':False,'review_unavailable_block':False,'true_review_repair':False,'review_invoked':arm=='CURRENT_BC','no_review_policy_noncompliance':False,'solver_provider_attempts':1,'verifier_provider_attempts':1 if arm=='CURRENT_BC' else 0,'wall_s':1.0}; d.update(kw); return d
def test_d4_adjudication_prefers_current_on_equal_success_without_harm():
 m=d4.load(M); rows=[]
 for c in m['cases']:
  rows += [_row(c['id'],'A_NO_REVIEW'),_row(c['id'],'CURRENT_BC')]
 assert d4.adjudicate(rows,m)['decision']=='RETAIN_CURRENT_BC'
def test_d4_adjudication_prefers_higher_success_and_detects_false_harm():
 m=d4.load(M); rows=[]
 for c in m['cases']: rows += [_row(c['id'],'A_NO_REVIEW'),_row(c['id'],'CURRENT_BC')]
 rows[-1]['valid_grader_pass']=False; assert d4.adjudicate(rows,m)['decision']=='SELECT_NO_REVIEW'
 rows[-1]['valid_grader_pass']=True; next(r for r in rows if r['case_id']=='d4-false-review-correct' and r['arm']=='CURRENT_BC')['false_review_damage']=True
 assert d4.adjudicate(rows,m)['decision']=='SELECT_NO_REVIEW'
def test_d4_provider_invalid_stops_inconclusive():
 m=d4.load(M); r=_row(m['cases'][0]['id'],'A_NO_REVIEW'); r['provider_invalid']=True; assert d4.adjudicate([r],m)['decision']=='INCONCLUSIVE_PROVIDER_FAILURE'
