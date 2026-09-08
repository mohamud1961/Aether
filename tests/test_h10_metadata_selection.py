import pytest
from evals.performance.h10_metadata_inventory import _mb
from evals.performance.h10_metadata_select import select


def row(task_id, benchmark, stratum, *, cpus=1, memory=2048, storage=10240, gpus=0, timeout=1800):
    category, subcategory = stratum.split('/', 1)
    return {
        'benchmark': benchmark,
        'task_id': task_id,
        'task_toml_path': f'/metadata/{task_id}/task.toml',
        'task_toml_sha256': task_id.ljust(64, '0')[:64],
        'category': category,
        'subcategory': subcategory,
        'stratum': stratum,
        'tags': [],
        'agent_timeout_s': timeout,
        'verifier_timeout_s': 900,
        'environment': {'cpus': cpus, 'memory_mb': memory, 'storage_mb': storage, 'gpus': gpus},
    }


def inventory(rows):
    return {'task_toml_only': True, 'instruction_files_read': 0, 'tasks': rows}


def test_size_parser_is_conservative_and_normalized():
    assert _mb('2G') == 2048
    assert _mb('1.5GiB') == 1536
    assert _mb(4096) == 4096
    with pytest.raises(ValueError):
        _mb('unknown')


def test_selection_is_exact_metadata_only_unique_and_resource_safe():
    tb4 = inventory([
        row('tb4-a','tb4','software/frontend',timeout=7200),
        row('tb4-b','tb4','science/math',timeout=7200),
        row('tb4-c','tb4','security/crypto'),
        row('tb4-d','tb4','ops/logistics'),
        row('tb4-gpu','tb4','ml/gpu',gpus=1),
    ])
    tb2 = inventory([
        row('tb2-a','tb2','systems/debug'),
        row('tb2-b','tb2','data/database'),
        row('tb2-c','tb2','language/compiler'),
        row('tb2-d','tb2','media/transform'),
        row('tb2-e','tb2','ml/inference'),
        row('tb2-f','tb2','formal/proof'),
        row('tb2-contaminated','tb2','other/x'),
    ])
    out = select(tb4, tb2, {'tb2-contaminated'})
    ids = [r['task_id'] for r in out['rows']]
    assert len(ids) == 10 and len(set(ids)) == 10
    assert 'tb4-gpu' not in ids and 'tb2-contaminated' not in ids
    assert out['instruction_content_used'] is False
    assert out['long_horizon_count'] >= 2


def test_selection_fails_closed_on_instruction_read_or_horizon_imbalance():
    tb4 = inventory([row(f'tb4-{i}','tb4',f'c{i}/s',timeout=1800) for i in range(4)])
    tb2 = inventory([row(f'tb2-{i}','tb2',f'd{i}/s',timeout=1800) for i in range(6)])
    bad = dict(tb4); bad['instruction_files_read'] = 1
    with pytest.raises(ValueError, match='instruction'):
        select(bad, tb2, set())
    with pytest.raises(ValueError, match='horizon balance'):
        select(tb4, tb2, set())
