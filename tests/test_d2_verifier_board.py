from pathlib import Path
from evals.performance import d2_verifier_board as d2
ROOT=Path(__file__).resolve().parents[1]
M=ROOT/'evals/performance/D2_VERIFIER_BOARD_V1.json'
def test_manifest_and_truth_board():
 m=d2.load(M); q=d2.qualify_provider_free(m); assert q['status']=='PASS' and q['case_count']==8
def test_adjudication_requires_all_cases():
 m=d2.load(M); rows=[]
 for c in m['cases']:
  rows.append({'case_id':c['id'],'class':c['class'],'run_status':'incomplete','review_verdict':'review_unavailable' if c['class']=='unavailable' else ('completed' if c['class']=='correct' else 'needs_repair'),'provider_invalid':False,'passed':True,'verifier_provider_attempts':0})
 assert d2.adjudicate(rows,m)['decision']=='PASS'
 rows[2]['passed']=False; assert d2.adjudicate(rows,m)['decision']=='FAIL'
def test_provider_timeout_is_inconclusive():
 m=d2.load(M); rows=[{'case_id':'x','class':'defect','run_status':'timeout','review_verdict':'','provider_invalid':True,'passed':False,'verifier_provider_attempts':0}]
 assert d2.adjudicate(rows,m)['decision']=='INCONCLUSIVE_PROVIDER_FAILURE'

def test_unexpected_review_unavailable_is_provider_invalid():
 m=d2.load(M); rows=[{'case_id':'x','class':'defect','run_status':'incomplete','review_verdict':'review_unavailable','provider_invalid':True,'passed':False,'verifier_provider_attempts':0}]
 assert d2.adjudicate(rows,m)['decision']=='INCONCLUSIVE_PROVIDER_FAILURE'
