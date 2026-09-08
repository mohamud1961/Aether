import json
from evals.performance.h10_contamination_census import census,extract_ids


def test_extracts_only_explicit_task_fields_and_normalizes():
 doc={'task_id':'terminal-bench/a','nested':{'task_order':['b','terminal-bench/c']},'note':'task_id=d is only prose','shortlist':[{'name':'e'}]}
 assert extract_ids(doc)=={'a','b','c'}


def test_extracts_repository_exclusion_authority_fields():
 doc={
  'excluded_from_calibration_task_ids':['terminal-bench/a','b'],
  'authorities':[{'excluded_task_ids':['c']}],
  'selected_task_ids':['d'],
  'fresh_pool_partition_locked_task_ids':['e'],
 }
 assert extract_ids(doc)=={'a','b','c','d','e'}


def test_census_records_source_hashes_without_task_reads(tmp_path):
 a=tmp_path/'a.json'; b=tmp_path/'b.json'
 a.write_text(json.dumps({'task_id':'a'})); b.write_text(json.dumps({'consumed_task_ids':['b','a']}))
 out=census([a,b])
 assert out['task_ids']==['a','b']
 assert out['instruction_files_read']==0
 assert out['source_count']==2
 assert all(len(x['sha256'])==64 for x in out['sources'])
