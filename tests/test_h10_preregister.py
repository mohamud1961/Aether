import copy
import pytest

from evals.performance.h10_parallel_schedule import build_waves, wave_host_requirements
from evals.performance.h10_preregister import assemble
from evals.performance.h10_serial_schedule import build_serial


def selection():
    rows=[]
    for i in range(1,11):
        rows.append({
            "ordinal":i,"benchmark":"tb4" if i<=4 else "tb2","task_id":f"t{i}",
            "task_toml_sha256":f"{i:064x}","environment":{"cpus":2,"memory_mb":4096,"storage_mb":10240,"gpus":0}
        })
    return {"instruction_content_used":False,"composition":{"terminal_bench_4_0":4,"terminal_bench_2x_untouched":6,"total":10},"rows":rows}


def schedule(sel, max_parallel=4):
    waves=build_waves(sel["rows"], max_parallel=max_parallel)
    return {"max_parallel":max(map(len,waves)),"waves":waves,"wave_host_requirements":[wave_host_requirements(w) for w in waves]}


def serial_schedule(sel):
    return build_serial(sel["rows"])


def candidate():
    return {"candidate":{
        "source_commit":"a"*40,"source_tree":"b"*40,"wheel_sha256":"c"*64,
        "installed_closure_sha256":"d"*64,"installed_file_count":103,"python_version":"3.12.3",
        "harbor_version":"0.20.0","model_profile_sha256":"e"*64,"tool_schema_sha256":"f"*64,
    }}


def vmq():
    keys=("exact_candidate_installed_closure","same_python","same_harbor","same_model_profile","same_tool_schema","same_kernel_os_docker_version","same_docker_root_and_driver")
    return {"candidate":copy.deepcopy(candidate()["candidate"]),"equivalence":{k:True for k in keys}}


def vmq_single():
    keys=(
        "exact_candidate_installed_closure","python_matches_candidate","harbor_matches_candidate",
        "model_profile_matches_candidate","tool_schema_matches_candidate","docker_version_bound",
        "docker_root_matches","docker_driver_matches","docker_buildx_available","storage_admission_valid","provider_free_smoke_passed",
    )
    return {
        "schema_version":"aether.h10.single_host_proteun_qualification.v1",
        "host":"proteun",
        "candidate":copy.deepcopy(candidate()["candidate"]),
        "single_host_serial_execution_qualified":True,
        "qualification":{k:True for k in keys},
    }


def provider_legacy(width=4):
    return {"qualified":True,"max_parallel":width,"candidate":copy.deepcopy(candidate()["candidate"])}


def provider_phase_e(width=1,status="QUALIFIED_SERIAL_WIDTH1"):
    return {"status":status,"qualified_global_width":width,"candidate_binding":copy.deepcopy(candidate()["candidate"])}


def custody():
    return {"selected_instruction_content_unopened":True,"selection_used_instruction_content":False}


def test_preregistration_freezes_exact_selection_and_schedule():
    sel=selection(); sch=schedule(sel)
    out=assemble(sel,sch,{"task_ids":["old-task"]},candidate(),vmq(),provider_legacy(4),custody(),{"selection":"1"*64})
    assert out["task_count"]==10
    assert out["task_order"]==[f"t{i}" for i in range(1,11)]
    assert out["status"]=="FROZEN_BEFORE_H10_INSTRUCTION_OPEN"
    assert out["vm_qualification_mode"]=="historical_two_host_equivalence"


def test_preregistration_accepts_sealed_phase_e_serial_authority():
    sel=selection(); sch=schedule(sel,max_parallel=1)
    out=assemble(sel,sch,[],candidate(),vmq(),provider_phase_e(),custody(),{})
    assert out["provider_qualified_max_parallel"]==1
    assert out["parallel_schedule"]["max_parallel"]==1


def test_preregistration_accepts_strict_single_host_proteun_qualification():
    sel=selection(); sch=serial_schedule(sel)
    out=assemble(sel,sch,[],candidate(),vmq_single(),provider_phase_e(),custody(),{})
    assert out["vm_qualification_mode"]=="single_host_proteun"
    assert out["parallel_schedule"]["execution_host"]=="proteun"
    assert out["parallel_schedule"]["max_parallel"]==1


def test_preregistration_rejects_incomplete_single_host_qualification():
    sel=selection(); sch=serial_schedule(sel); bad=vmq_single()
    bad["qualification"]["provider_free_smoke_passed"]=False
    with pytest.raises(ValueError,match="missing accepted checks"):
        assemble(sel,sch,[],candidate(),bad,provider_phase_e(),custody(),{})


def test_preregistration_rejects_single_host_without_buildx():
    sel=selection(); sch=serial_schedule(sel); bad=vmq_single()
    bad["qualification"]["docker_buildx_available"]=False
    with pytest.raises(ValueError,match="missing accepted checks"):
        assemble(sel,sch,[],candidate(),bad,provider_phase_e(),custody(),{})


def test_preregistration_rejects_wrong_single_host_binding():
    sel=selection(); sch=serial_schedule(sel); bad=vmq_single(); bad["host"]="aether-solver"
    with pytest.raises(ValueError,match="host=proteun"):
        assemble(sel,sch,[],candidate(),bad,provider_phase_e(),custody(),{})


def test_preregistration_rejects_single_host_receipt_for_non_single_host_schedule():
    sel=selection(); sch=schedule(sel,max_parallel=1)
    with pytest.raises(ValueError,match="two-VM provider-free equivalence"):
        assemble(sel,sch,[],candidate(),vmq_single(),provider_phase_e(),custody(),{})


def test_preregistration_rejects_phase_e_width_status_mismatch():
    sel=selection(); sch=schedule(sel,max_parallel=1)
    with pytest.raises(ValueError,match="width/status mismatch"):
        assemble(sel,sch,[],candidate(),vmq(),provider_phase_e(width=2,status="QUALIFIED_SERIAL_WIDTH1"),custody(),{})


def test_preregistration_rejects_stale_vm_candidate_receipt():
    sel=selection(); sch=schedule(sel,max_parallel=1); stale=vmq()
    stale["candidate"]["installed_file_count"]=102
    with pytest.raises(ValueError,match="VM qualification candidate identity mismatch"):
        assemble(sel,sch,[],candidate(),stale,provider_phase_e(),custody(),{})


def test_preregistration_rejects_stale_provider_candidate_receipt():
    sel=selection(); sch=schedule(sel,max_parallel=1); stale=provider_phase_e()
    stale["candidate_binding"]["wheel_sha256"]="0"*64
    with pytest.raises(ValueError,match="provider qualification candidate identity mismatch"):
        assemble(sel,sch,[],candidate(),vmq(),stale,custody(),{})


def test_preregistration_rejects_contamination_or_unqualified_width():
    sel=selection(); sch=schedule(sel)
    with pytest.raises(ValueError,match="contaminated"):
        assemble(sel,sch,{"task_ids":["t3"]},candidate(),vmq(),provider_legacy(4),custody(),{})
    with pytest.raises(ValueError,match="exceeds provider-qualified"):
        assemble(sel,sch,[],candidate(),vmq(),provider_legacy(2),custody(),{})


def test_preregistration_requires_instruction_custody():
    sel=selection(); sch=schedule(sel)
    with pytest.raises(ValueError,match="instruction custody"):
        assemble(sel,sch,[],candidate(),vmq(),provider_legacy(4),{"selected_instruction_content_unopened":False,"selection_used_instruction_content":False},{})
