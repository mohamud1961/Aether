"""History-scale allocation regression; original history stays page verified."""
import tracemalloc

from aether.core.clm import ClmContext, ClmSettings
from aether.core.evidence_context import select_context


def test_optional_index_does_not_duplicate_all_historical_payloads():
    ctx=ClmContext([],settings=ClmSettings(attest_original_history=True))
    for i in range(1000):ctx.append({'role':'tool','tool_call_id':str(i),'content':'α雪'*15000})
    ctx.editable=[];ctx.stats.edits_accepted=1
    tracemalloc.start()
    try:
        projected,meta=select_context(ctx,[],[{'function':{'name':'read_history'}}],policy='history_index')
        _,peak=tracemalloc.get_traced_memory()
    finally:tracemalloc.stop()
    assert meta['changed'] and meta['listed']==12 and meta['eligible']==1000
    assert len(projected)==1
    # 30M raw characters already exist. Index construction must allocate a
    # bounded card/page working set, not another encoded copy of every source.
    assert peak<3_000_000,f'index duplicated large historical payloads: {peak} bytes'
