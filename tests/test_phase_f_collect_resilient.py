from evals.performance.phase_f_collect_resilient import _environment_start_timeout,_pre_agent_trial_exception,_fallback_kind


def custody(status='executed_valid'):
 return {'status':status,'child_custody':{'valid':True}}


def env_timeout_job(exc='EnvironmentStartTimeoutError'):
 return {'stats':{'n_retries':0,'n_running_trials':0,'n_pending_trials':0,'n_input_tokens':None,'n_output_tokens':None,'cost_usd':None,
                  'evals':{'aether__adhoc':{'n_trials':0,'n_errors':1,'exception_stats':{exc:['trial']}}}}}


def pre_agent_trial(exc='RuntimeError'):
 return {'agent_result':None,'agent_setup':None,'agent_execution':None,
         'environment_setup':{'started_at':'s','finished_at':'f'},
         'exception_info':{'exception_type':exc,'exception_message':'environment failed'}}


def test_accepts_exact_environment_start_timeout_shape():
 job=env_timeout_job()
 assert _environment_start_timeout(job)
 assert _fallback_kind(custody(),{'status':'completed','exit_code':0},job,pre_agent_trial('EnvironmentStartTimeoutError'))=='pre_agent_environment_start_timeout_no_aether_run_record'


def test_accepts_terminal_pre_agent_environment_exception_shape():
 job=env_timeout_job('RuntimeError'); trial=pre_agent_trial()
 assert _pre_agent_trial_exception(job,trial)
 assert _fallback_kind(custody(),{'status':'completed','exit_code':0},job,trial)=='pre_agent_environment_failure_no_aether_run_record'


def test_rejects_post_agent_or_token_bearing_exception_shape():
 job=env_timeout_job('RuntimeError'); trial=pre_agent_trial(); trial['agent_execution']={'started_at':'x'}
 assert not _pre_agent_trial_exception(job,trial)
 assert _fallback_kind(custody(),{'status':'completed','exit_code':0},job,trial) is None
 job=env_timeout_job('RuntimeError');job['stats']['n_input_tokens']=1
 assert not _pre_agent_trial_exception(job,pre_agent_trial())
 assert _fallback_kind(custody(),{'status':'completed','exit_code':0},job,pre_agent_trial()) is None


def test_rejects_other_timeout_shape_without_trial_proof():
 job=env_timeout_job('AgentTimeoutError')
 assert not _environment_start_timeout(job)
 assert _fallback_kind(custody(),{'status':'completed','exit_code':0},job,None) is None


def test_preserves_original_harbor_failed_fallback_and_requires_custody():
 assert _fallback_kind(custody('executed_failed'),{'status':'harbor_failed','exit_code':1},None,None)=='pre_agent_harbor_failure_no_aether_run_record'
 bad={'status':'executed_failed','child_custody':{'valid':False}}
 assert _fallback_kind(bad,{'status':'harbor_failed','exit_code':1},None,None) is None
