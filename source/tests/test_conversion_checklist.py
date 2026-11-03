"""Keep user-visible progress tied to actual completed, blocked and unreached stages."""
import json
from tools.behavior_verification.conversion_checklist import conversion_steps,publish_conversion_checklist


def test_stopped_partial_components_do_not_mark_units_or_chains_complete(tmp_path):
    status=dict(run_id='run',recorded_at='now',status='blocked',phase='components',process_running=False,
        total_units=7,total_operations=1,component_validated=8,accepted_units=0,accepted_operations=0,blockers=[])
    report=dict(groups={'one':dict(status='component_validated'),'two':dict(status='incomplete')})
    lines=conversion_steps(status,report)
    assert [line[:3] for line in lines]==['[V]','[V]','[X]','[ ]','[ ]','[ ]','[ ]']
    path=publish_conversion_checklist(tmp_path,status,report)
    assert path.name=='conversion-checklist.md' and 'Conversion is stopped' in path.read_text()
    report['format_chain_status']='running';status['process_running']=True
    assert conversion_steps(status,report)[3].startswith('[O]')
    report['format_chain_status']='blocked'
    assert conversion_steps(status,report)[3].startswith('[X]')


def test_only_complete_acceptance_marks_the_final_step_successful():
    status=dict(total_units=7,total_operations=1,component_validated=10,accepted_units=7,accepted_operations=1,
        acceptance_complete=True,process_running=False)
    report=dict(groups={'one':dict(status='component_validated')},format_chain_status='validated')
    assert all(line.startswith('[V]') for line in conversion_steps(status,report))
    status['acceptance_complete']=False;status['unverified_units']=['stale']
    lines=conversion_steps(status,report)
    assert lines[4].startswith('[X]') and lines[-1].startswith('[ ]')


def test_partial_success_cannot_finish_the_component_phase_and_fatal_stops_are_visible():
    status=dict(process_running=True,total_units=7,accepted_units=7,total_operations=1,accepted_operations=1)
    report=dict(groups={'one':dict(status='component_validated')},total_groups=3)
    lines=conversion_steps(status,report)
    assert lines[2].startswith('[O]') and lines[4].startswith('[O]') and lines[5].startswith('[O]')
    assert conversion_steps(status,dict(groups={},total_groups=3))[2].startswith('[O]')
    status['process_running']=False;report['fatal_error']='interrupted'
    report['format_chain_status']='running'
    lines=conversion_steps(status,report)
    assert lines[2].startswith('[X]') and lines[3].startswith('[X]')
