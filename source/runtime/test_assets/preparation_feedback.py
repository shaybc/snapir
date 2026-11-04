"""Return AI-reported fixture problems to scenario preparation without changing assertions."""
import json
from models.junit_test_scenario import JunitScenarioSuite
from models.native_test_bundle import NativeTestBundle
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from runtime.managed_conversion_response import _remove_response_fence
from runtime.behavior_conversion.response_json import clean_structural_escapes
from tools.state_store_tools import staged_conversion_state as state,behavior_units
from tools.component_inventory_tools.identity import stable_id


class PreparationCorrection(VerificationIncomplete):
    """A tests-only model cannot repair the fixture invocation that it was given."""
    def __init__(self,questions):
        super().__init__(dict(stage='test_preparation',errors=list(questions)))


def retain_feedback(tasks,questions,suite):
    """Bound preparation reviews and retain all original scenario IDs and assertions."""
    prior=state.read(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'preparation_feedback')
    previous=json.loads(prior['artifact_json']) if prior['artifact_json'] else {}
    round_number=previous.get('round',0)+1
    if round_number>tasks.profile.max_agent_task_retries:
        raise VerificationIncomplete(dict(stage='test_preparation',errors=['Bounded preparation correction limit reached',*questions]))
    value=dict(round=round_number,errors=list(questions),retained_scenarios=suite.model_dump(mode='json'))
    state.retain(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'preparation_feedback',value,stable_id(value))
    return value


def load_feedback(tasks,production_files):
    """Recover unresolved AI preparation reports from interrupted earlier tests-only work."""
    prior=state.read(tasks.conn,tasks.config.run_id,tasks.identity,tasks.revision,'preparation_feedback')
    if prior['artifact_json']:return json.loads(prior['artifact_json'])
    for request,raw in tasks.conn.execute("SELECT request_json,response FROM staged_conversion_attempts WHERE run_id=? AND identity=? AND revision=? AND stage='tests' AND response IS NOT NULL AND error IS NOT NULL ORDER BY attempt DESC",(tasks.config.run_id,tasks.identity,tasks.revision)):
        request=json.loads(request)
        if request.get('production_files')!=production_files or not request.get('junit_scenarios'):continue
        try:value=NativeTestBundle.model_validate_json(clean_structural_escapes(_remove_response_fence(raw)))
        except ValueError:continue
        if value.unresolved_questions:
            return retain_feedback(tasks,value.unresolved_questions,JunitScenarioSuite.model_validate(request['junit_scenarios']))
    return None


def prepare_review(tasks,request,feedback,check):
    """Reclassify the stale cached proposal and validate its corrected replacement."""
    baseline=JunitScenarioSuite.model_validate(feedback['retained_scenarios'])
    category='staged_junit_scenarios';identity=tasks.identity+':'+tasks.revision
    prior=behavior_units.snapshot(tasks.conn,tasks.config.run_id,category,identity)
    if prior and prior['status']=='accepted' and JunitScenarioSuite.model_validate_json(prior['data_json'])==baseline:
        behavior_units.save(tasks.conn,tasks.config.run_id,category,identity,prior['fingerprint'],
            json.loads(prior['data_json']),status='verification_incomplete',error=str(feedback['errors']))
    def reviewed(value):
        check(value)
        old={s.scenario_id:s for s in baseline.scenarios};new={s.scenario_id:s for s in value.scenarios}
        if set(old)-set(new) or any(not set(s.assertions)<=set(new[key].assertions) for key,s in old.items()):
            raise ValueError('Preparation review must preserve retained scenarios and assertions')
        if value==baseline and not value.unresolved and not any(s.unresolved for s in value.scenarios):
            raise ValueError('Unchanged preparation does not resolve the reported problem; correct setup or report it unresolved')
    return dict(request,preparation_feedback=feedback),reviewed


def tests_for_manifest(tasks,manifest_hash):
    """Give each immutable fixture revision a bounded tests role; retain old counters."""
    from runtime.behavior_conversion.stage_tasks import StageTasks
    return StageTasks(tasks.conn,tasks.config,tasks.profile,tasks.identity,stable_id(tasks.revision,'test_fixture_manifest',manifest_hash),
        tasks.model_call,tasks.validator,tasks.label,category=tasks.category,payload=tasks.payload)


def fixture_review(request,bank,feedback,check):
    """Return unresolved fixture setup to its owner without changing retained data."""
    def reviewed(value):
        check(value)
        if any(key not in value.fixtures or stable_id(value.fixtures[key].model_dump(mode='json'))!=stable_id(entry.model_dump(mode='json')) for key,entry in bank.fixtures.items()):
            raise ValueError('Fixture repair must preserve retained data; add missing entries instead')
    return dict(request,preparation_feedback=dict(feedback,fixture_errors=list(bank.unresolved),
        retained_fixture_bank=bank.model_dump(mode='json'))),reviewed


def junit_for_protocol(tasks):
    """Bind preparation attempts to the real supported protocol, not AI feedback edits."""
    from runtime.behavior_conversion.stage_tasks import StageTasks
    return StageTasks(tasks.conn,tasks.config,tasks.profile,tasks.identity,stable_id(tasks.revision,'junit_protocol',JunitScenarioSuite.model_json_schema()),
        tasks.model_call,tasks.validator,tasks.label,category=tasks.category,payload=tasks.payload)
