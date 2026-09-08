from evals.performance.h10_provider_concurrency_adjudicate import adjudicate,EXPECTED_CLOSURE,EXPECTED_PROFILE,EXPECTED_TOOL


def host(width,passed=True):
 return {'passed':passed,'requested_width':width,'completed_provider_calls':width if passed else 0,'candidate':{'package_closure_sha256':EXPECTED_CLOSURE,'model_profile_sha256':EXPECTED_PROFILE,'tool_schema_sha256':EXPECTED_TOOL,'solver_reasoning_effort':'high'}}


def test_adjudication_promotes_four_only_after_1_2_4_pass():
 out=adjudicate(host(1),[host(1),host(1)],[host(2),host(2)])
 assert out['qualified'] is True and out['max_parallel']==4


def test_adjudication_falls_back_without_rerun():
 out=adjudicate(host(1),[host(1),host(1)],[host(2),host(2,False)])
 assert out['max_parallel']==2
 out=adjudicate(host(1),[host(1),host(1,False)],[host(2),host(2)])
 assert out['max_parallel']==1
 out=adjudicate(host(1,False),[host(1),host(1)],[host(2),host(2)])
 assert out['qualified'] is False and out['max_parallel']==0


def test_host_canary_uses_independent_workers_without_live_provider(monkeypatch):
    import evals.performance.h10_provider_concurrency_canary as canary

    class FakeModel:
        def __init__(self): self._tel=[]
        def call_with_telemetry_scope(self,msgs,run_id,task_id):
            self._tel=[{'status':'completed','provider_transport_mode':'websocket','native_tool_call_count':1,'native_tool_name':'read_file','attempt_ordinal':1}]
            return '{"kind":"act"}'
        def drain_telemetry(self): return tuple(self._tel)
        def drain_continuity_admission_telemetry(self): return ()
        def close_run_transport(self): pass

    class Closure:
        sha256='x'*64
        file_count=102

    monkeypatch.setattr(canary,'package_closure',lambda:Closure())
    monkeypatch.setattr(canary,'production_tool_schema_sha256',lambda:'y'*64)
    out=canary.run_width(2,'unit',factory=FakeModel)
    assert out['passed'] is True
    assert out['completed_provider_calls']==2
    assert len(out['workers'])==2
