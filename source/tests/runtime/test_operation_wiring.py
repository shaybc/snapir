"""Validate distinct Spring step beans and start real operation wiring offline."""

import json
import shutil
from types import SimpleNamespace

import pytest

from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.bundle_output import accept_bundle
from runtime.behavior_conversion.ownership import create_native_context
from runtime.java_toolchain import java_scope
from runtime.service_generation.operation_wiring import validate_operation_wiring
from runtime.service_generation.operation_wiring import validate_wiring_execution
from tools.maven_dependency_tools.build_context import ManagedBuildContext
from tests.runtime.test_behavior_conversion import profile
from tests.runtime.test_native_xml_build import OfflineVerifier
from tests.runtime.test_operation_injection_build import injected_latest


def wiring():
    bundle, saved, roles = injected_latest()
    configuration = 'package example; @org.springframework.context.annotation.Configuration public class ProductionWiring {\n'
    for index, item in enumerate(roles):
        value = "new " + item["type_name"] + "()"
        params = ""
        if item["type_name"].endswith(".FraudCheckStep"):
            params = 'com.company.generated.units.uf2c8754a25a6.FraudDetectionServicePort fraudPort'
            value = "new " + item["type_name"] + "(3000, fraudPort)"
        configuration += '@org.springframework.context.annotation.Bean(' + json.dumps(item["binding_id"]) + ') public ' + item["type_name"] + ' step' + str(index) + '(' + params + ') { return ' + value + '; }\n'
    configuration += '@org.springframework.context.annotation.Bean public javax.sql.DataSource database() { throw new IllegalStateException("external resource fixture must be supplied"); }\n'
    configuration += '@org.springframework.context.annotation.Bean public com.company.generated.units.uf2c8754a25a6.FraudDetectionServicePort fraudPort() { throw new IllegalStateException("external API fixture must be supplied"); }\n'
    parameters = ', '.join('@org.springframework.beans.factory.annotation.Qualifier(' + json.dumps(item["binding_id"]) + ') ' + item["type_name"] + ' ' + item["parameter_name"] for item in roles)
    arguments = ', '.join(item["parameter_name"] for item in roles) + ', database'
    configuration += '@org.springframework.context.annotation.Bean public com.company.generated.operations.TransferFundsOpService operation(' + parameters + ', javax.sql.DataSource database) { return new com.company.generated.operations.TransferFundsOpService(' + arguments + '); } }'
    assertions = '\n'.join('assertFalse(org.mockito.Mockito.mockingDetails(context.getBean(' + json.dumps(item["binding_id"]) + ')).isMock()); var field' + str(index) + ' = service.getClass().getDeclaredField(' + json.dumps(item["field_name"]) + '); field' + str(index) + '.setAccessible(true); assertSame(context.getBean(' + json.dumps(item["binding_id"]) + '), field' + str(index) + '.get(service));' for index, item in enumerate(roles))
    test = ('package example; import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*; '
        'public class ProductionWiringTest { @Test public void createsRealStepsAndInjectsNamedRoles() throws Exception { '
        'try(var context = new org.springframework.context.annotation.AnnotationConfigApplicationContext()) { '
        'context.addBeanFactoryPostProcessor(factory -> { factory.registerSingleton("database", org.mockito.Mockito.mock(javax.sql.DataSource.class)); '
        'factory.registerSingleton("fraudPort", org.mockito.Mockito.mock(com.company.generated.units.uf2c8754a25a6.FraudDetectionServicePort.class)); }); '
        'context.register(ProductionWiring.class); context.refresh(); '
        'var service = context.getBean(com.company.generated.operations.TransferFundsOpService.class); assertNotNull(service); '
        + assertions + ' } } }')
    files = dict(saved["accepted_sources"])
    files.update({file.path: file.content for file in bundle.files})
    files['src/main/java/example/ProductionWiring.java'] = configuration
    files['src/test/java/example/ProductionWiringTest.java'] = test
    files['src/main/resources/application.properties'] = 'spring.datasource.url=${DB_URL}\nspring.datasource.username=${DB_USER}\nspring.datasource.password=${DB_PASSWORD}\n'
    return bundle, saved, files


def test_named_factories_and_executable_startup_test_are_required():
    bundle, _, files = wiring()
    contract = bundle.operation_contract.model_dump()
    validate_operation_wiring(files, contract)
    broken = dict(files)
    broken['src/main/java/example/ProductionWiring.java'] = broken['src/main/java/example/ProductionWiring.java'].replace('@org.springframework.context.annotation.Bean("CheckLimits")', '@org.springframework.context.annotation.Bean("wrongRole")')
    with pytest.raises(ValueError, match="distinct named step-role"):
        validate_operation_wiring(broken, contract)
    qualified = dict(files)
    qualified['src/main/java/example/ProductionWiring.java'] = qualified['src/main/java/example/ProductionWiring.java'].replace(
        '@org.springframework.context.annotation.Bean("CheckLimits")',
        '@org.springframework.context.annotation.Bean @org.springframework.beans.factory.annotation.Qualifier("CheckLimits")')
    with pytest.raises(ValueError, match='factory @Qualifier alone does not set its bean name'):
        validate_operation_wiring(qualified, contract)
    broken = {name: content for name, content in files.items() if not name.startswith('src/test/java/')}
    with pytest.raises(ValueError, match="executable Spring wiring test"):
        validate_operation_wiring(broken, contract)
    broken = dict(files, **{'src/main/resources/application.properties': ''})
    with pytest.raises(ValueError, match="deployment settings"):
        validate_operation_wiring(broken, contract)
    broken = dict(files, **{'src/main/resources/application.properties': 'spring.datasource.url=jdbc:fixed\nspring.datasource.username=user\nspring.datasource.password=secret\n'})
    with pytest.raises(ValueError, match="deployment settings"):
        validate_operation_wiring(broken, contract)
    broken = dict(files)
    broken['src/main/java/example/ProductionWiring.java'] = broken['src/main/java/example/ProductionWiring.java'].replace('new com.company', 'org.mockito.Mockito.mock(com.company', 1)
    with pytest.raises(ValueError, match="real objects"):
        validate_operation_wiring(broken, contract)


def test_java25_spring_creates_real_step_objects_and_supplies_service_constructor(tmp_path):
    if not shutil.which('mvn'):
        pytest.skip('Offline Maven unavailable')
    bundle, saved, files = wiring()
    settings = profile(java_version=25, java_home='C:/Program Files/Java/jdk-25.0.3')
    validation = {'test_status': 'passed'}
    class WiringVerifier(OfflineVerifier):
        def compile_project(self, project, allowed=(), *, goal='compile'):
            result = super().compile_project(project, allowed, goal=goal)
            if goal == 'test' and result.returncode == 0:
                validate_wiring_execution(project, files, bundle.operation_contract.model_dump(), validation)
            return result
    verifier = WiringVerifier()
    def context(settings, project, artifact):
        return create_native_context(SimpleNamespace(run_id='spring-injection-replay'), settings, project,
            lambda settings, project, artifact: ManagedBuildContext(str(project / 'pom.xml'), verifier))
    dependencies = [MavenDependency.model_validate(item) for item in saved['known_dependencies']]
    dependencies.append(MavenDependency(group_id='org.springframework', artifact_id='spring-context', version='6.2.19', reason='Verified offline Spring wiring test'))
    with java_scope(settings):
        result, _ = accept_bundle(tmp_path / 'project', files, context, settings, dependencies)
    assert result['tests_passed'] and result['test_count'] == 1
    assert validation['wiring_passed']


def test_missing_or_skipped_startup_execution_is_not_accepted(tmp_path):
    bundle, _, files = wiring()
    report = tmp_path / 'target/surefire-reports/TEST-example.ProductionWiringTest.xml'
    report.parent.mkdir(parents=True)
    report.write_text('<testsuite><testcase classname="example.ProductionWiringTest"><skipped/></testcase></testsuite>')
    result = {'test_status': 'passed'}
    validate_wiring_execution(tmp_path, files, bundle.operation_contract.model_dump(), result)
    assert result['test_status'] == 'failed' and not result['wiring_passed']
