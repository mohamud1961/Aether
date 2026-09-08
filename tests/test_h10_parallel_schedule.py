import pytest
from evals.performance.h10_parallel_schedule import build_waves, wave_host_requirements


def row(i, cpus=2, memory=4096, storage=10240, gpus=0):
    return {
        "ordinal": i,
        "task_id": f"task-{i:02d}",
        "environment": {"cpus": cpus, "memory_mb": memory, "storage_mb": storage, "gpus": gpus},
    }


def test_ten_light_rows_use_four_way_ceiling():
    waves = build_waves([row(i) for i in range(1, 11)])
    assert [len(w) for w in waves] == [4, 4, 2]
    assert {x["host"] for x in waves[0]} == {"proteun", "aether-solver"}
    assigned = [x for wave in waves for x in wave]
    assert sum(x["host"] == "proteun" for x in assigned) == 5
    assert sum(x["host"] == "aether-solver" for x in assigned) == 5
    req = wave_host_requirements(waves[0])
    assert req["proteun"] == {
        "task_count": 2,
        "committed_cpus": 4,
        "committed_memory_mb": 8192,
        "committed_storage_mb": 20480,
        "required_docker_free_mb": 32768,
    }


def test_provider_qualified_serial_ceiling_builds_one_task_waves():
    waves = build_waves([row(i) for i in range(1, 11)], max_parallel=1)
    assert [len(w) for w in waves] == [1] * 10
    assigned = [wave[0] for wave in waves]
    assert [x["host"] for x in assigned] == ["proteun", "aether-solver"] * 5


def test_invalid_parallel_ceiling_fails_closed():
    rows = [row(i) for i in range(1, 11)]
    with pytest.raises(ValueError, match="max_parallel"):
        build_waves(rows, max_parallel=0)
    with pytest.raises(ValueError, match="max_parallel"):
        build_waves(rows, max_parallel=5)


def test_heavy_row_monopolizes_its_vm():
    rows = [row(1, cpus=4, memory=8192)] + [row(i) for i in range(2, 11)]
    waves = build_waves(rows)
    first = waves[0]
    heavy = next(x for x in first if x["task_id"] == "task-01")
    assert sum(x["host"] == heavy["host"] for x in first) == 1


def test_storage_commit_prevents_overpacked_vm():
    waves = build_waves([row(i, storage=25000) for i in range(1, 11)])
    assert [len(w) for w in waves] == [2, 2, 2, 2, 2]
    assert all(len({x["host"] for x in wave}) == len(wave) for wave in waves)


def test_missing_resource_metadata_forces_exclusive_lane():
    rows = [row(i) for i in range(1, 11)]
    del rows[0]["environment"]["storage_mb"]
    waves = build_waves(rows)
    first = waves[0]
    unknown = next(x for x in first if x["task_id"] == "task-01")
    assert unknown["exclusive"] is True
    assert sum(x["host"] == unknown["host"] for x in first) == 1


def test_gpu_or_oversize_fails_closed():
    rows = [row(i) for i in range(1, 11)]
    rows[0] = row(1, gpus=1)
    with pytest.raises(ValueError, match="GPU"):
        build_waves(rows)
    rows = [row(i) for i in range(1, 11)]
    rows[0] = row(1, cpus=8)
    with pytest.raises(ValueError, match="exceeds VM envelope"):
        build_waves(rows)
    rows = [row(i) for i in range(1, 11)]
    rows[0] = row(1, storage=50000)
    with pytest.raises(ValueError, match="exceeds VM envelope"):
        build_waves(rows)
