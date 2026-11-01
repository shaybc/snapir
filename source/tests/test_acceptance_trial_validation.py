"""Trial publication uses real Maven/JUnit and the existing executable acceptance receipt."""
from pathlib import Path
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.behavior_conversion.testing_contract import testing_contract as platform_contract
from runtime.behavior_conversion.verification_state import record_verification
from tools.behavior_verification.acceptance_trial_validation import AcceptanceTrialValidator
from tools.state_store_tools.db import get_connection,create_all_tables
from tools.state_store_tools.runs import upsert_run
from test_executable_verification import fixture
from test_behavior_verification_boundaries import boundary_tool


def test_trial_validator_requires_actual_build_and_comparison(boundary_tool,tmp_path,monkeypatch):
    from tests.runtime.test_scoped_native import actual_build
    with java_scope(PipelineConfiguration(java_version=25)):
        original,bundle,config,session=fixture(boundary_tool,tmp_path)
        profile=PipelineConfiguration(java_version=25)
        request=dict(requirements={'result':'Preserve original result'},testing_contract=platform_contract(profile))
        bundle.coverage={'result':[bundle.files[1].path]}
        monkeypatch.setattr('tools.behavior_verification.acceptance_trial_validation.create_build_context',actual_build)
        checks=[];validator=AcceptanceTrialValidator(session,profile,request,tmp_path/'candidate',lambda:checks.append('fresh'))
        metadata_bundle=bundle.model_copy(deep=True)
        metadata_bundle.files=[file for file in metadata_bundle.files if file.path.startswith('src/main/')]
        validator.validate_metadata(metadata_bundle);proof=validator(bundle)
        assert proof['build_validation']['tests_passed'] and checks==['fresh','fresh']
        conn=get_connection(':memory:');create_all_tables(conn);upsert_run(conn,run_id=config.run_id,run_mode='acceptance_trials')
        try:record_verification(conn,config,original['unit_id'],'accepted',session.last_report)
        finally:conn.close()
        assert (tmp_path/'candidate'/bundle.files[0].path).is_file()
