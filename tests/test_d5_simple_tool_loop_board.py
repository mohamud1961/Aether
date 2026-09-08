from pathlib import Path
from evals.performance import d5_simple_tool_loop_board as d5
ROOT=Path(__file__).resolve().parents[1]; M=ROOT/'evals/performance/D5_SIMPLE_TOOL_LOOP_BOARD_V1.json'
def test_d5_provider_free_graders(tmp_path:Path):
 q=d5.qualify_provider_free(d5.load(M),tmp_path/'q'); assert q['status']=='PASS' and q['case_count']==4
def row(cid,arm,passed=True,wall=1.0,inp=100): return {'case_id':cid,'arm':arm,'provider_invalid':False,'valid_grader_pass':passed,'wall_s':wall,'solver_provider_attempts':1,'verifier_provider_attempts':1 if arm=='AETHER' else 0,'solver_input_tokens':inp,'verifier_input_tokens':50 if arm=='AETHER' else None}
def test_d5_adjudication_accepts_equal_success_bounded_tax():
 m=d5.load(M); rows=[]
 for c in m['cases']: rows += [row(c['id'],'AETHER',wall=2,inp=120),row(c['id'],'MINIMAL',wall=1,inp=100)]
 x=d5.adjudicate(rows,m); assert x['passed'] and x['decision']=='PASS_AETHER_EARNS_STRUCTURE'
def test_d5_adjudication_rejects_unique_minimal_success():
 m=d5.load(M); rows=[]
 for c in m['cases']: rows += [row(c['id'],'AETHER'),row(c['id'],'MINIMAL')]
 rows[0]['valid_grader_pass']=False; x=d5.adjudicate(rows,m); assert not x['passed'] and x['minimal_unique_passes']
def test_d5_adjudication_rejects_excessive_tax():
 m=d5.load(M); rows=[]
 for c in m['cases']: rows += [row(c['id'],'AETHER',wall=4,inp=400),row(c['id'],'MINIMAL',wall=1,inp=100)]
 assert d5.adjudicate(rows,m)['passed'] is False


def test_d5_minimal_continuity_helpers_commit_and_reject_exact_scope():
 class Fake:
  def __init__(self): self.events=[]
  def commit_pending_response(self,*,run_id,task_id): self.events.append(('commit',run_id,task_id))
  def reject_pending_response(self,*,run_id,task_id): self.events.append(('reject',run_id,task_id))
 f=Fake(); d5._commit_pending(f,'r','t'); d5._reject_pending(f,'r','t')
 assert f.events == [('commit','r','t'),('reject','r','t')]

def test_d5_minimal_continuity_helpers_are_optional_for_plain_models():
 class Plain: pass
 d5._commit_pending(Plain(),'r','t'); d5._reject_pending(Plain(),'r','t')


def test_d5b_provider_free_graders(tmp_path:Path):
 m=ROOT/'evals/performance/D5B_SIMPLE_TOOL_LOOP_POSTFIX_V1.json'
 q=d5.qualify_provider_free(d5.load(m),tmp_path/'q-d5b')
 assert q['status']=='PASS' and q['case_count']==4

def test_d5_minimal_loop_rejects_bad_candidate_then_commits_accepted(monkeypatch,tmp_path:Path):
 import json,re
 class FakeSolver:
  def __init__(self): self.calls=0; self.events=[]; self.tele=[]
  def bind_run_cancellation(self,event): self.event=event
  def call_with_telemetry_scope(self,messages,**kwargs):
   self.calls += 1
   self.tele.append({'event_kind':'provider_attempt','input_tokens':10,'output_tokens':5})
   if self.calls == 1: return 'not-json'
   if self.calls == 2: return json.dumps({'kind':'act','action':{'kind':'read_file','arguments':{'path':'x.txt'}}})
   refs=re.findall(r'evidence:[0-9a-f]{16}','\n'.join(str(m.get('content','')) for m in messages))
   return json.dumps({'kind':'finish','claim':'done','evidence_refs':[refs[-1]]})
  def commit_pending_response(self,*,run_id,task_id): self.events.append(('commit',run_id,task_id))
  def reject_pending_response(self,*,run_id,task_id): self.events.append(('reject',run_id,task_id))
  def drain_telemetry(self): out=tuple(self.tele); self.tele.clear(); return out
  def drain_continuity_admission_telemetry(self): return ()
  def clear_continuity_scope(self,**kwargs): pass
  def close_run_transport(self): pass
 fake=FakeSolver()
 import aether.harbor_runtime as hr
 monkeypatch.setattr(hr,'build_selected_luna_models',lambda:(fake,object()))
 (tmp_path/'x.txt').write_text('ok')
 case={'id':'d5-fake-handshake','task':'Read x.txt and finish.'}
 run,_=d5.run_minimal(case,tmp_path,{'wall_timeout_s':30,'max_decision_steps':5})
 assert run['status']=='completed'
 assert [e[0] for e in fake.events] == ['reject','commit','commit']
 assert run['parse_errors']==1


def test_d5c_provider_free_graders(tmp_path:Path):
 m=ROOT/'evals/performance/D5C_SIMPLE_TOOL_LOOP_POSTFIX_V1.json'
 q=d5.qualify_provider_free(d5.load(m),tmp_path/'q-d5c')
 assert q['status']=='PASS' and q['case_count']==4


def test_d5d_provider_free_graders(tmp_path:Path):
 m=ROOT/'evals/performance/D5D_SIMPLE_TOOL_LOOP_POSTFIX_V1.json'
 q=d5.qualify_provider_free(d5.load(m),tmp_path/'q-d5d')
 assert q['status']=='PASS' and q['case_count']==4


def test_d5e_provider_free_graders(tmp_path:Path):
 m=ROOT/'evals/performance/D5E_SIMPLE_TOOL_LOOP_POSTFIX_V1.json'
 q=d5.qualify_provider_free(d5.load(m),tmp_path/'q-d5e')
 assert q['status']=='PASS' and q['case_count']==4

def test_d5_live_paths_are_canonical_absolute(tmp_path:Path,monkeypatch):
 monkeypatch.chdir(tmp_path)
 p=d5.absolute_path(Path('relative/live'))
 assert p.is_absolute() and p == (tmp_path/'relative/live').resolve()


def test_d5f_provider_free_graders(tmp_path:Path):
 m=ROOT/'evals/performance/D5F_SIMPLE_TOOL_LOOP_LINUX_V1.json'
 q=d5.qualify_provider_free(d5.load(m),tmp_path/'q-d5f')
 assert q['status']=='PASS' and q['case_count']==4


def test_d5g_provider_free_graders(tmp_path:Path):
 m=ROOT/'evals/performance/D5G_SIMPLE_TOOL_LOOP_LINUX_OVERLAY_V1.json'
 q=d5.qualify_provider_free(d5.load(m),tmp_path/'q-d5g')
 assert q['status']=='PASS' and q['case_count']==4

def test_d5_virtual_executor_routes_only_app_task_commands(tmp_path:Path,monkeypatch):
 ex=d5._build_task_executor(tmp_path,{'linux_virtual_app':True})
 calls=[]
 class R:
  success=True; exit_code=0; stdout='VIRTUAL'; stderr=''; timed_out=False; modified_paths=(); produced_artifacts=(); removed_paths=(); state_delta={}; metrics={}; stdout_overflow_path=None; stderr_overflow_path=None; stdout_bytes_total=7; stderr_bytes_total=0
 monkeypatch.setattr(ex,'run_command_with_virtual_workspace',lambda command,virtual_workspace_root='/app',timeout_s=30:(calls.append((command,virtual_workspace_root,timeout_s)) or R()))
 v=ex.run_command('echo task',cwd='/app',timeout_s=7); assert v.stdout=='VIRTUAL' and calls
 host=ex.run_command('pwd',cwd=None,timeout_s=7); assert host.success and str(tmp_path.resolve()) in host.stdout
 ex.close()


def test_d5_physical_verifier_overlay_binding_preserves_logical_app(tmp_path:Path):
 import aether.kernel_verifier as kv
 ex=d5._build_task_executor(tmp_path,{'linux_virtual_app':True})
 original=kv.VerifierOverlay
 with d5._bind_d5_physical_verifier_overlay_root(tmp_path,{'linux_virtual_app':True}):
  assert kv.VerifierOverlay is not original
  overlay=kv.VerifierOverlay(ex,'/app',require_independent_isolation=False)
  assert overlay._workspace_root == str(tmp_path.resolve())
 assert kv.VerifierOverlay is original
 ex.close()


def test_d5i_provider_free_graders(tmp_path:Path):
 m=ROOT/'evals/performance/D5I_SIMPLE_TOOL_LOOP_CLEAN_OVERLAY_V1.json'
 q=d5.qualify_provider_free(d5.load(m),tmp_path/'q-d5i')
 assert q['status']=='PASS' and q['case_count']==4
