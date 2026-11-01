"""Route proven executable failures without turning tool limitations into code repairs."""
import json
from runtime.behavior_conversion.verification_feedback import VerificationFailure,VerificationIncomplete
from tools.component_inventory_tools.identity import stable_id
from tools.state_store_tools import staged_conversion_state as state
import subprocess

VERSION='bounded-failure-routing-v1'


class AdapterRepairRequired(VerificationFailure):
    """Converter-owned invocation wiring failed; production must remain frozen."""
    staged_retry_owner='adapter'


def stage_error(error,stage):
    """Unknown build/tool failures cannot request arbitrary business-code changes."""
    if isinstance(error,VerificationIncomplete):return error
    feedback=getattr(error,'verification_feedback',{})
    if feedback.get('stage')=='cases' and feedback.get('expected_settings'):
        return AdapterRepairRequired(dict(feedback,stage='settings_binding',
            action='Repair native settings wiring before requesting or correcting tests'))
    correction=getattr(error,'compiler_correction',None)
    if stage!='implementation' and correction and any(d.get('file','').startswith('src/main/java/') for d in correction.get('diagnostics',[])):
        error.staged_retry_owner='implementation'
        return error
    message=str(error)
    parser_tool=message.startswith('Native JavaParser inspection failed:') and 'Native parse failed:' not in message
    unknown_build=message.startswith('Candidate validation failed:') and not correction and not getattr(error,'test_correction',None)
    if isinstance(error,(OSError,subprocess.TimeoutExpired)) or parser_tool or unknown_build:
        return VerificationIncomplete(dict(stage='stage_tooling',owner=stage,errors=[message],action='Resolve tooling or missing validation evidence; do not edit production'))
    return error


def record_correction(tasks,owner,feedback):
    """Bound cached failure cycles durably without resetting any role's call budget."""
    prior=state.read(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'failure_routes')
    rows=tasks.conn.execute('SELECT stage,attempts FROM staged_conversion_tasks WHERE run_id=? AND identity=? AND revision=? AND attempts>0 ORDER BY stage',
        (tasks.config.run_id,tasks.identity,tasks.revision)).fetchall()
    progress=stable_id([(row[0],row[1]) for row in rows])
    entries=json.loads(prior['artifact_json']) if prior['artifact_json'] else []
    if any(entry['progress']==progress for entry in entries) or len(entries)>=8*tasks.profile.max_agent_task_retries:
        raise VerificationIncomplete(dict(stage='retry_progress',owner=owner,errors=['Correction made no model-attempt progress or exhausted transition budget']))
    entries.append(dict(owner=owner,progress=progress,feedback_hash=stable_id(feedback)))
    state.retain(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'failure_routes',entries,stable_id(entries))


def adapter_failure(report):
    """Only explicit trusted-adapter provenance can justify wiring correction."""
    if report.issues:return None
    failures=[case for case in report.cases if case['native'].get('failure_origin')=='adapter_binding']
    if not failures:return None
    if any(case['legacy']['status']!='completed' for case in report.cases):return None
    return dict(stage='adapter_invocation',errors=['Converter-owned adapter binding failed'],
        failing_cases=[dict(case=case['case'],errors=case['native']['issues']) for case in failures])
