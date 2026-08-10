from __future__ import annotations
import json
from typing import Any
import pytest
import aether.verify_completion_protocol as protocol
from aether.compiler import CapabilityRegistry, ConfigCompiler
from aether.model_hooks import ModelHooks
from aether.runtime_ir import CapabilityDescriptor, EnvMap, RuntimeConfigIR
from aether.verifier import parse_model_verifier_result
from aether.verifier_inspector import VerifierInspectionRequest


def _compiled():
    env=EnvMap(task_prompt="Write out.txt.",workspace_root="/app",capabilities={
        "shell":CapabilityDescriptor("shell","run commands"),
        "filesystem":CapabilityDescriptor("filesystem","read files")})
    return ConfigCompiler(CapabilityRegistry.from_envmap(env)).compile(RuntimeConfigIR(
        architect_summary="test",solver_identity_prompt="solver",
        selected_capabilities=("shell","filesystem"),verifier_identity_prompt="Inspect evidence."),env)


def _hooks(model):
    return ModelHooks(architect_model=lambda _m,**_k:"{}",solver_model=lambda _m,**_k:"{}",verifier_model=model)


def _ledger(): return type("Ledger",(),{"all_receipts":lambda self:[]})()


def _result(r:VerifierInspectionRequest)->dict[str,Any]:
    return {"request_id":r.request_id,"inspection_id":f"inspection:test:{r.request_id}","kind":r.kind,
            "path":r.path,"excerpt":"current bytes","eligible_for_proof":True,"evidence_ceiling":"exact_contract"}


def _uncertain()->str:
    return json.dumps({"verdict":"uncertain_missing_evidence","confidence":"high",
        "summary":"The bounded observations do not establish completion.",
        "missing_evidence_requests":["Read the current output after new evidence exists."]})


def test_uncertain_survives_auto_realization_budget_exhaustion(monkeypatch:pytest.MonkeyPatch)->None:
    monkeypatch.setenv("AETHER_VERIFIER_MAX_INVESTIGATION_BATCHES","1")
    calls=[]; inspections=[]
    def model(messages,*,max_output_tokens=8000):
        calls.append(list(messages))
        if len(calls)==1:
            return json.dumps({"kind":"inspect","requests":[{"request_id":"initial","kind":"read_file","path":"out.txt"}]})
        return _uncertain()
    def inspector(requests):
        batch=tuple(requests); inspections.append(batch); return [_result(r) for r in batch]
    monkeypatch.setattr(protocol,"_inspections_from_missing_evidence",lambda _result,*,packet:(VerifierInspectionRequest(request_id="optional",kind="read_file",path="out.txt"),))
    hooks=_hooks(model)
    raw=hooks.verify_with_inspector({"reason":"solver_submit","task_prompt":"Write out.txt"},_compiled(),_ledger(),inspector)
    assert parse_model_verifier_result(raw).verdict=="uncertain_missing_evidence"
    assert len(calls)==2 and len(inspections)==1 and hooks.last_parse_errors==[]


def test_uncertain_survives_structured_followup_budget_exhaustion(monkeypatch:pytest.MonkeyPatch)->None:
    monkeypatch.setenv("AETHER_VERIFIER_MAX_INVESTIGATION_BATCHES","1")
    calls=[]; inspections=[]
    def model(messages,*,max_output_tokens=8000): calls.append(list(messages)); return _uncertain()
    def inspector(requests):
        batch=tuple(requests); inspections.append(batch); return [_result(r) for r in batch]
    monkeypatch.setattr(protocol,"_inspections_from_missing_evidence",lambda _result,*,packet:(VerifierInspectionRequest(request_id="first-auto",kind="read_file",path="out.txt"),))
    monkeypatch.setattr(protocol,"_structured_missing_evidence_requests",lambda _raw:(VerifierInspectionRequest(request_id="second-auto",kind="read_file",path="out.txt"),))
    hooks=_hooks(model)
    raw=hooks.verify_with_inspector({"reason":"solver_submit","task_prompt":"Write out.txt"},_compiled(),_ledger(),inspector)
    assert parse_model_verifier_result(raw).verdict=="uncertain_missing_evidence"
    assert len(calls)==2 and len(inspections)==1 and hooks.last_parse_errors==[]
