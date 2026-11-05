"""Run a selected prepared whole-operation scenario against frozen Java and prebuilt JDBC tooling."""
import json
import os
from pathlib import Path
import subprocess
from runtime.fixture_demo.catalogue import prepare_catalogue
from runtime.fixture_jdbc_tools.releases import file_hash
from runtime.test_assets.store import load
from runtime.test_assets.references import resolve
from models.shared_test_fixture import SharedFixtureBank
from runtime.fixture_demo.artifact_paths import demo_artifact,migrate_demo_artifacts


def verify_operation_scenario(project,identity,profile,*,run=None,validate_build=True):
    """Run retained build/JUnit checks, then compare XML and sticky replay diagnostics.

    Expected XML is loaded before invocation. A native response is never used to
    manufacture an expectation. This validates a prepared native scenario, not equivalence.
    """
    project=Path(project).resolve()
    try:migrate_demo_artifacts(project)
    except (ValueError,OSError) as error:
        return dict(operation=identity,status='execution_failed',equivalence='not_assessed',error=str(error),java_and_pom_unchanged=True)
    directory=demo_artifact(project,'.demo-scenario-verification');directory.mkdir(parents=True,exist_ok=True)
    result=dict(operation=identity,status='execution_failed',equivalence='not_assessed')
    protected={p:file_hash(p) for p in [project/'pom.xml',*project.joinpath('src/main').rglob('*')] if p.is_file()}
    try:
        definition=json.loads(demo_artifact(project,'operation-demo-scenarios.json').read_text(encoding='utf-8'))
        _,evidence=prepare_catalogue(project,identity)
        selected=definition.get('selected_scenario') or (definition['scenarios'][0]['scenario_id'] if len(definition['scenarios'])==1 else None)
        if selected not in evidence['requests']:raise ValueError('Select one explicit operation scenario to execute')
        scenario=evidence['requests'][selected];result.update(scenario=selected,total_prepared_scenarios=len(definition['scenarios']),verified_scenarios=0)
        def value(ref):
            _,documents=load(ref['asset_root'],ref['manifest_hash'])
            return resolve(SharedFixtureBank.model_validate(documents['fixtures.json']),dict(fixture_id=ref['fixture_id'],pointer=ref['pointer']))
        if scenario['expected_xml'] is None:raise ValueError('Selected operation scenario has no pre-execution expected XML')
        request=value(scenario['input_xml']);expected=value(scenario['expected_xml'])
        (directory/'request.xml').write_bytes(request.encode('utf-8'));(directory/'expected.xml').write_bytes(expected.encode('utf-8'))
        if validate_build:
            from runtime.service_generation.validation import validate_service_project
            from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
            from runtime.java_toolchain import java_environment
            from types import SimpleNamespace
            verifier=MavenRepositoryVerifier(profile.maven_settings_path,profile.approved_maven_repository_urls,profile.maven_local_repository,
                timeout_seconds=profile.model_timeout_seconds)
            verifier.environment=java_environment(profile.java_version,profile.java_home);verifier.dependency_profile=profile
            build=validate_service_project(project,SimpleNamespace(verifier=verifier,
                allowed_ibm_classes=profile.allowed_ibm_classes,allowed_ibm_artifacts=profile.allowed_ibm_artifacts))
            (directory/'build.json').write_text(json.dumps(build,indent=2),encoding='utf-8')
            result['build']=dict(build_passed=build['build_passed'],test_status=build['test_status'],package_passed=build['package_passed'],test_count=build.get('test_count'))
            if not (build['build_passed'] and build['package_passed'] and build['test_status']=='passed'):
                raise ValueError('Saved operation build/JUnit checks failed; inspect '+str(directory/'build.json'))
        runtime_report=project/'standalone/.demo-runtime/last-run.json'
        old=json.loads(runtime_report.read_text(encoding='utf-8')).get('execution') if runtime_report.exists() else None
        if run is None:
            if os.name!='nt':raise ValueError('This standalone project supplies a Windows batch launcher; provide a supported execution runner')
            from runtime.java_toolchain import java_environment
            completed=subprocess.run(['cmd','/d','/c','call',str(project/'run-operation.bat'),str(directory/'request.xml'),'--demo'],
                cwd=project,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,
                env=java_environment(profile.java_version,profile.java_home))
        else:completed=run(project,directory/'request.xml')
        (directory/'actual.xml').write_bytes(completed.stdout.encode('utf-8'))
        (directory/'launcher.log').write_text(completed.stderr,encoding='utf-8')
        if not runtime_report.exists():raise ValueError('Standalone exited without a fixture execution report')
        observed=json.loads(runtime_report.read_text(encoding='utf-8'));result['execution']=observed
        if observed.get('execution')==old:raise ValueError('Standalone execution report is stale')
        if completed.returncode or observed['status']!='completed' or observed.get('replay',{}).get('failed',True):
            raise ValueError('Whole-operation invocation or JDBC replay failed')
        from tools.behavior_verification.boundary_xml import xml_structure
        result['xml_matched']=xml_structure(expected)==xml_structure(completed.stdout)
        executions=sum(event['operation']=='execute' for event in observed['replay']['events'])
        result.update(resource_executions=executions,expected_resource_executions=scenario['expected_resource_executions'])
        if not result['xml_matched']:raise ValueError('Whole-operation XML differs from the pre-execution expected response')
        if scenario['expected_resource_executions'] is not None and executions!=scenario['expected_resource_executions']:
            raise ValueError('Whole-operation JDBC execution count differs from the prepared scenario')
        result.update(status='verified_against_prepared_expectations',verified_scenarios=1)
    except Exception as error:result['error']=str(error)
    finally:
        result['java_and_pom_unchanged']=all(p.is_file() and file_hash(p)==expected for p,expected in protected.items())
        if not result['java_and_pom_unchanged']:result.update(status='execution_failed',error='Saved operation inputs changed during verification')
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result
