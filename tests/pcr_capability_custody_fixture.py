from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace


def event(mode:str,status:str='completed',job_id:str|None=None)->dict:
    return {'event_kind':'provider_attempt','role':'solver','status':status,'provider_output_error':None if status=='completed' else 'synthetic_failure','pcr_reasoning_context_requested':mode,'pcr_reasoning_context_effective':mode if status=='completed' else None,'pcr_reasoning_context_status':'matched' if status=='completed' else 'unreported','pcr_primary_provider_schema_sha256':'1'*64,'input_sha256':'2'*64,'instructions_sha256':'3'*64,'prompt_cache_key_mode':'off','prompt_cache_retention':None,'job_id':job_id}

class FakeModel:
    def __init__(self,mode:str,fail:bool=False): self.mode=mode; self.fail=fail; self.telemetry=[]; self.admissions=[]
    def call_with_telemetry_scope(self,_messages,**_kwargs):
        if self.fail:
            self.telemetry=[event(self.mode,'failed')]; raise RuntimeError('synthetic provider failure')
        rid=f'resp-{self.mode}'; self.telemetry=[event(self.mode,job_id=rid)]; self.admissions=[{'event_kind':'pcr_continuity_parent_admission','pcr_continuity_parent_disposition':'committed','pcr_continuity_response_id':rid,'pcr_continuity_previous_committed_response_id':None}]; return '{"kind":"submit_outcome","summary":"synthetic","actions":[]}'
    def commit_pending_response(self,**_kwargs): return None
    def drain_telemetry(self): rows,self.telemetry=self.telemetry,[]; return rows
    def drain_continuity_admission_telemetry(self): rows,self.admissions=self.admissions,[]; return rows

def install(cap,monkeypatch,*,fail_second:bool=False,construction_failure:bool=False):
    state={'count':0}
    def make(**kwargs):
        state['count']+=1
        if construction_failure: raise RuntimeError('synthetic construction failure')
        return FakeModel(kwargs['pcr_reasoning_context'], fail_second and state['count']==2)
    monkeypatch.setattr(cap,'_verify_production_source',lambda *_a,**_k:{'synthetic':True})
    monkeypatch.setattr(cap.importlib,'import_module',lambda _name:SimpleNamespace(make_azure_callable=make))
    return state


def authorization(cap, plan:dict, cert:dict, unlock_sha:str='e'*64):
    binding={
        'schema_version':'pcr.current_all_external_unlock.v1',
        'production_commit':cert['commit'],
        'production_tree':cert['tree'],
        'task_freeze_sha256':plan['task_freeze_sha256'],
        'plan_authorization_code':plan['authorization_code'],
        'capability_canary':True,
        'maximum_provider_calls':2,
        'discovery_board':False,
    }
    return {'external_unlock_sha256':unlock_sha,'external_unlock_binding_sha256':cap._sha(binding),'external_unlock_binding':binding}
