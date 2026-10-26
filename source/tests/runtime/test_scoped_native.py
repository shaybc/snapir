"""Exercise opt-in scoped native generation with real offline Maven/JUnit execution."""

import json
import subprocess
import hashlib
from time import perf_counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from models.native_unit_bundle import NativeUnitBundle
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope, resolve_java_home
from runtime.workspace_paths import run_report_path
from tools.composer_mapper_tools.vault_importer import import_vault
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tools.maven_dependency_tools.pom_manager import initialize_managed_pom
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.runs import upsert_run, get_run
from tools.state_store_tools.behavior_units import snapshot
from tests.test_scoped_vault_identity import scoped_mapper, invoke_mapper


class OfflineVerifier(MavenRepositoryVerifier):
    """Use actual cached artifacts, compilation and Surefire; never fabricate reports."""

    verified = set()

    def _arguments(self):
        return super()._arguments() + ['--offline']

    def __call__(self, dependency):
        artifact = self.local_repository.joinpath(*dependency.group_id.split('.'), dependency.artifact_id,
            dependency.version, dependency.artifact_id + '-' + dependency.version + '.jar')
        with artifact.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        key = (dependency.model_dump_json(), digest, self.environment.get('JAVA_HOME'))
        if key not in self.verified:
            super().__call__(dependency)
            self.verified.add(key)

    def _run(self, arguments, directory):
        started = perf_counter()
        result = super()._run(arguments, directory)
        print('REAL_MAVEN', arguments[-1], 'exit=' + str(result.returncode),
              'seconds=' + str(round(perf_counter() - started, 2)), flush=True)
        return result


def actual_build(profile, project, artifact):
    from runtime.java_toolchain import java_environment
    initialize_managed_pom(str(project / 'pom.xml'), 'example.native', artifact, java_version=profile.java_version)
    verifier = OfflineVerifier(None, [], str(Path.home() / '.m2/repository'), timeout_seconds=120)
    verifier.environment = java_environment(profile.java_version, profile.java_home)
    return ManagedBuildContext(str(project / 'pom.xml'), verifier)


class NativeModel:
    """Deterministic candidates for two order-sensitive, source-evidenced transformations."""

    def __init__(self):
        self.requests = []

    def __call__(self, instruction, encoded):
        data = json.loads(encoded)
        self.requests.append(data)
        title = data['schema']['title']
        if title == 'BehaviorReview':
            return json.dumps(dict(approved=True, issues=[], unresolved_questions=[]))
        if title == 'RouteTestPlan':
            graph = data['closure']['routing_graph']
            edges = [dict(source=source, outcome='on0Do', target=targets['on0Do']) for source, targets in graph.items()]
            return json.dumps(dict(scenarios=[dict(scenario_id='increment-order', description='Apply configured transformations in source order',
                inputs=['input=4'], dependency_setup=[], expected_outcome='result=412', expected_side_effects=[],
                covers=list(data['requirements']), routes=edges)]))
        assert title == 'NativeUnitBundle'
        deps = data.get('testing_contract', {}).get('dependencies', [])
        if not deps and data.get('assembly_phase') != 'implementation_compile':
            deps = [dict(group_id='org.junit.jupiter', artifact_id='junit-jupiter', version='5.10.0', scope='test', reason='Executable behavior check')]
        if data.get('assembly_phase') == 'single_route_test':
            args = ', '.join('new ' + item['type_name'] + '()' for item in data['operation_contract']['step_dependencies'])
            content = ('package ' + data['test_package'] + '; public class ' + data['test_class'] +
                ' { @org.junit.jupiter.api.Test public void preservesOriginalSequence() { '
                'org.junit.jupiter.api.Assertions.assertEquals(412, new com.company.generated.nativeflow.FlowService(' + args + ').execute(4)); } }')
            return NativeUnitBundle(files=[dict(path=data['expected_test_path'], content=content)], dependencies=deps).model_dump_json()
        if 'unit_id' in data:
            amount = int(data['effective_configuration']['attributes']['increment'])
            package, name, method = data['native_package'], 'Increment', 'public int run(int input)'
            source = 'package ' + package + '; public class Increment { ' + method + ' { return input * 10 + ' + str(amount) + '; } }'
            testpath = 'src/test/java/' + package.replace('.', '/') + '/IncrementTest.java'
            test = ('package ' + package + '; public class IncrementTest { @org.junit.jupiter.api.Test public void addsConfiguredValue() {'
                'org.junit.jupiter.api.Assertions.assertEquals(' + str(40 + amount) + ', new Increment().run(4)); } }')
            return NativeUnitBundle(files=[dict(path='src/main/java/' + package.replace('.', '/') + '/Increment.java', content=source),
                dict(path=testpath, content=test)], dependencies=deps, coverage={key: [testpath] for key in data['requirements']},
                evidence_ids=data['evidence_ids'], input_type='int', output_type='int',
                unit_contract=dict(unit_id=data['unit_id'], apis=[dict(type_name=package + '.Increment', method_signatures=[method])],
                    requirements=data['requirements'], evidence_ids=data['evidence_ids'], dependency_units=[])).model_dump_json()
        dependencies = [dict(binding_id=item['binding_id'], unit_id=item['unit_id'], type_name=item['allowed_types'][0],
            parameter_name='step' + str(index), field_name='step' + str(index)) for index, item in enumerate(data['required_step_dependencies'])]
        fields = ' '.join('private final ' + item['type_name'] + ' ' + item['field_name'] + ';' for item in dependencies)
        constructor = ('public FlowService(' + ', '.join(item['type_name'] + ' ' + item['parameter_name'] for item in dependencies) + ') {' +
            ' '.join('this.' + item['field_name'] + ' = ' + item['parameter_name'] + ';' for item in dependencies) + '}')
        body = 'int result = input; ' + ' '.join('result = this.' + item['field_name'] + '.run(result);' for item in dependencies) + ' return result;'
        source = 'package com.company.generated.nativeflow; public class FlowService { ' + fields + constructor + 'public int execute(int input) {' + body + '} }'
        return NativeUnitBundle(files=[dict(path='src/main/java/com/company/generated/nativeflow/FlowService.java', content=source)],
            operation_contract=dict(sources=[dict(path='src/main/java/com/company/generated/nativeflow/FlowService.java', content=source)],
                units=[item['contract'] for item in data['accepted_units'].values()],
                service_api=dict(type_name='com.company.generated.nativeflow.FlowService', method_signatures=['public int execute(int input)']),
                request_type='int', success_type='int', error_type='int', step_dependencies=dependencies)).model_dump_json()


def scoped_state(tmp_path, mapper):
    root, vault = tmp_path / 'source', tmp_path / 'vault'
    channel = root / 'Channel/XML'
    channel.mkdir(parents=True)
    (channel / 'dse.ini').write_text('<dse.ini><kColl id="settings"><kColl id="files"><kColl id="selfDefOper">'
        '<operDef id="Flow.xml" value="Flow"/></kColl></kColl></kColl></dse.ini>')
    (channel / 'Flow.xml').write_text('''<XML><CCDSEServerOperation id="Flow" operationContext="Ctx">
      <opStep id="Repeat" implClass="example.Work" increment="1" on0Do="next"/>
      <opStep id="Repeat" implClass="example.Work" increment="2" on0Do="end"/>
    </CCDSEServerOperation><context id="Ctx" parent="nil"/></XML>''')
    java = root / 'src/example/Work.java'
    java.parent.mkdir(parents=True)
    java.write_text('package example;\npublic class Work { private int increment; '
        'public void setIncrement(int value) { increment=value; } public int run(int input) { return input*10+increment; } }')
    mapped = invoke_mapper(mapper, root, vault)
    assert mapped.returncode == 0, mapped.stderr
    conn = get_connection(':memory:')
    create_all_tables(conn)
    config = SimpleNamespace(run_id='native', run_mode=SimpleNamespace(value='full_inventory'), target_channels=[],
        include_operations=None, exclude_operations=None, source_root=str(root), vault_root=str(vault),
        output_root=str(tmp_path / 'generated'), max_agent_task_retries=1)
    upsert_run(conn, run_id='native', run_mode='full_inventory')
    import_vault(conn, str(vault), config, progress=lambda message: None)
    return conn, config


@pytest.mark.parametrize('entry', ['behavior', 'assembly'])
def test_real_scoped_native_generation_review_compile_and_behavior(tmp_path, scoped_mapper, entry):
    home = resolve_java_home(25)
    conn, config = scoped_state(tmp_path, scoped_mapper)
    profile = PipelineConfiguration(source_root=config.source_root, mapper_vault_layout='scoped', source_workspace_id='native',
        scoped_native_mode='behavior_units_v1', scoped_java_project='.', conversion_strategy='behavior_units',
        plan_approval_policy='automatic',
        java_version=25, java_home=home, model_provider='mock', max_agent_task_retries=1,
        gate_policies={'1': 'automatic', '2': 'automatic', '3': 'human', '4': 'human'}, classpath_jars=[], eclipse_classpath_variables={})
    model = NativeModel()
    with java_scope(profile):
        if entry == 'behavior':
            from runtime.behavior_conversion.runner import resume_behavior_pipeline
            resume_behavior_pipeline(conn, config, profile, tmp_path, model_call=model, context_factory=actual_build)
        else:
            from runtime.operation_assembly.runner import run_operation_assembly
            from models.migration_models import MigrationPlan, MigrationBatch, MigrationTaskPacket
            plan = MigrationPlan(plan_id='native', run_id='native', total_operations=1, unusual_count=0, status='pending',
                batches=[MigrationBatch(batch_id='native', run_id='native', is_pilot=True, status='pending', task_packets=[
                    MigrationTaskPacket(task_id='flow', run_id='native', channel='XML', operation_id='Flow',
                        target_language='java', group='multi_step_linear', status='pending')])])
            run_operation_assembly(conn, config, profile, plan, tmp_path, model_call=model, context_factory=actual_build)
    assert get_run(conn, 'native')['current_phase'] == 'gate_3_pending'
    accepted = snapshot(conn, 'native', 'operation', 'XML/Flow')
    assert accepted and accepted['status'] == 'accepted'
    implementation = json.loads(accepted['data_json'])
    assert implementation['review']['approved']
    assert len(implementation['bindings']) == 2
    assert len({item['unit_id'] for item in implementation['bindings'].values()}) == 2
    scenarios = conn.execute("SELECT data_json FROM behavior_snapshots WHERE category='route_test_report'").fetchall()
    assert scenarios
    manifest = json.loads(snapshot(conn, 'native', 'manifest', 'service:XML/Flow')['data_json'])
    assert manifest['validation']['build_passed'] and manifest['validation']['tests_passed']
    assert manifest['validation']['test_count'] >= 3
    assert conn.execute("SELECT count(*) FROM scoped_reuse_entries WHERE category='result'").fetchone()[0] > 0
    from runtime.behavior_conversion.evidence import collect_native_operation_evidence
    packaged_plan = SimpleNamespace(batches=[SimpleNamespace(task_packets=[SimpleNamespace(channel='XML', operation_id='Flow')])])
    with java_scope(profile):
        packaging = collect_native_operation_evidence(conn, config, profile, packaged_plan)
    assert not packaging[0]['issues'], packaging[0]['issues']
    assert packaging[0]['payload']['scoped_operation_identity']
    from runtime.scoped_native.scope import require_task
    with pytest.raises(ValueError, match='gated'):
        require_task(conn, config, profile, 'unit', next(iter(implementation['bindings'].values()))['unit_id'], {})
    def forbidden(instruction, encoded):
        current = json.loads(encoded)
        prior = next((item for item in model.requests if item.get('unit_id') == current.get('unit_id')
                      and item['schema']['title'] == current['schema']['title']), {})
        differences = {key: (prior.get(key), current.get(key)) for key in set(prior) | set(current)
                       if prior.get(key) != current.get(key)}
        pytest.fail('Unchanged scoped native run repeated a model task: ' + repr(differences))
    with java_scope(profile):
        if entry == 'behavior':
            resume_behavior_pipeline(conn, config, profile, tmp_path, model_call=forbidden, context_factory=actual_build)
        else:
            run_operation_assembly(conn, config, profile, plan, tmp_path, model_call=forbidden, context_factory=actual_build)
    conn.close()


def test_original_fixture_java_establishes_an_order_sensitive_oracle(tmp_path, scoped_mapper):
    home = Path(resolve_java_home(25))
    conn, config = scoped_state(tmp_path, scoped_mapper)
    oracle = tmp_path / 'Oracle.java'
    oracle.write_text('public class Oracle { public static void main(String[] args) {'
        'example.Work first=new example.Work(); first.setIncrement(1);'
        'example.Work second=new example.Work(); second.setIncrement(2);'
        'if(second.run(first.run(4)) != 412 || first.run(second.run(4)) != 421) throw new AssertionError();'
        'System.out.print(second.run(first.run(4))); } }')
    classes = tmp_path / 'oracle-classes'
    subprocess.run([str(home / 'bin/javac'), '-d', str(classes), str(Path(config.source_root) / 'src/example/Work.java'),
        str(oracle)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(home / 'bin/java'), '-cp', str(classes), 'Oracle'],
        check=True, capture_output=True, text=True)
    assert result.stdout == '412'
    conn.close()
