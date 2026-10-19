"""Replay missing-driver startup failures with isolated real Spring wiring."""

import json
from pathlib import Path

import pytest

from models.maven_dependency import MavenDependency
from runtime.service_generation.startup_resources import validate_jdbc_driver, validate_startup_substitutes
from runtime.service_generation.operation_wiring import WIRING_INSTRUCTION, validate_wiring_execution
from runtime.behavior_conversion.corrections import route_native_correction
from tests.runtime.test_operation_wiring import wiring


def latest():
    return json.loads((Path(__file__).parent / 'fixtures/latest_startup_resource_failure.json').read_text())


def test_latest_failure_requires_external_resource_mocks_and_deployment_driver():
    fixture = latest()
    files = fixture['output']['files']
    proposals = [MavenDependency.model_validate(item) for item in fixture['output']['dependencies']]
    with pytest.raises(ValueError, match='register mocks.*javax.sql.DataSource'):
        validate_startup_substitutes(files, fixture['contract'])
    with pytest.raises(ValueError, match='deployment settings.*org.h2.Driver'):
        validate_jdbc_driver(files, proposals)
    bundle, _, corrected = wiring()
    validate_startup_substitutes(corrected, bundle.operation_contract.model_dump())
    assert 'BEFORE refresh' in WIRING_INSTRUCTION
    assert 'required_classes' in WIRING_INSTRUCTION


@pytest.mark.parametrize('driver', ['example.sql.Driver', 'another.vendor.JdbcDriver'])
def test_driver_owner_and_scope_validation_is_vendor_independent(driver):
    files = {'src/main/resources/application.properties':
             'spring.datasource.driver-class-name=${DEPLOYMENT_DRIVER:' + driver + '}'}
    with pytest.raises(ValueError, match='no verified compile/runtime dependency'):
        validate_jdbc_driver(files, [])
    dependency = MavenDependency(group_id='example', artifact_id='driver', version='1.0',
                                 scope='test', required_classes=[driver], reason='fixture')
    with pytest.raises(ValueError, match='no verified compile/runtime dependency'):
        validate_jdbc_driver(files, [dependency])
    dependency.scope = 'runtime'
    validate_jdbc_driver(files, [dependency])
    files['src/main/resources/application.properties'] = 'spring.datasource.driver-class-name=' + driver
    with pytest.raises(ValueError, match='environment placeholder'):
        validate_jdbc_driver(files, [dependency])


def test_substitution_check_is_generic_across_resource_types():
    contract = {'runtime_resources': [{'provider_type': 'example.RemoteClient'}]}
    source = '''import example.RemoteClient; class Test {
      void test() { var c = new AnnotationConfigApplicationContext();
      c.addBeanFactoryPostProcessor(f -> f.registerSingleton("client", mock(RemoteClient.class)));
      c.refresh(); c.getBean(Service.class); }
    }'''
    validate_startup_substitutes({'src/test/java/example/Test.java': source}, contract)
    with pytest.raises(ValueError, match='before Spring refresh'):
        validate_startup_substitutes({'src/test/java/example/Test.java': source.replace(
            'new AnnotationConfigApplicationContext()', 'new AnnotationConfigApplicationContext(Config.class)')}, contract)
    with pytest.raises(ValueError, match='register mocks'):
        validate_startup_substitutes({'src/test/java/example/Test.java': '// ' + source.replace('\n', '\n//')}, contract)


def test_failed_startup_execution_keeps_generation_correction_route(tmp_path):
    fixture = latest()
    result = {'build_passed': True, 'test_status': 'failed', 'failure_class': 'build_failure'}
    validate_wiring_execution(tmp_path, fixture['output']['files'], fixture['contract'], result)
    assert result['failure_class'] == 'build_failure'
    assert route_native_correction(None, None, None, result) == 'generation'


def test_url_autodetection_and_environment_only_driver_settings_remain_supported():
    validate_jdbc_driver({'src/main/resources/application.properties': 'spring.datasource.url=${DB_URL}'}, [])
    validate_jdbc_driver({'src/main/resources/application.properties': 'spring.datasource.driver-class-name=${DB_DRIVER}'}, [])
