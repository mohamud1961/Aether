import pytest
from evals.performance.h10_serial_schedule import build_serial


def rows():
    return [{"ordinal":i,"task_id":f"t{i}","environment":{"cpus":1,"memory_mb":2048,"storage_mb":10240,"gpus":0}} for i in range(1,11)]


def test_serial_schedule_pins_all_rows_to_proteun():
    out=build_serial(rows())
    assert out["max_parallel"]==1
    assert out["wave_count"]==10
    assert [len(w) for w in out["waves"]]==[1]*10
    assert all(w[0]["host"]=="proteun" for w in out["waves"])
    assert [w[0]["ordinal"] for w in out["waves"]]==list(range(1,11))
    assert all(r["proteun"]["required_docker_free_mb"]==20480 for r in out["wave_host_requirements"])


def test_serial_schedule_fails_closed_on_bad_board_or_gpu():
    with pytest.raises(ValueError,match="10 rows"):
        build_serial(rows()[:9])
    bad=rows();bad[0]["environment"]["gpus"]=1
    with pytest.raises(ValueError,match="GPU"):
        build_serial(bad)
