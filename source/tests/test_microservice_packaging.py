"""Typed deployment and Helm packaging preserve native operations and configuration identity."""
import json
import yaml
from pathlib import Path
import pytest
from models.microservice_deployment import MicroserviceDeployment
from runtime.service_generation.deployment_configuration import load_deployment, deployment_readiness, read_deployment, write_deployment
from runtime.service_generation.microservice_output import managed_resources, merge_managed_resources, validate_initialization
from tools.deployment_tools.helm_renderer import render_helm
from tools.deployment_tools.helm_validation import validate_helm


def specification(database='default'):
    return MicroserviceDeployment.model_validate(dict(operation=dict(identity='INTERNET/Example',database=database,
        initialization={'Channel':'INTERNET','CaseSensitive':{'NestedID':['A','B']}}),
        http=dict(path='/api/INTERNET/Example'),
        databases={database:dict(credentialsSecret=dict(name='example-database'))} if database else {}))


def test_seed_once_preserves_selected_database_without_copying_secrets(tmp_path):
    (tmp_path/'standalone').mkdir();(tmp_path/'standalone/operation.json').write_text('{"database":"read-only"}')
    (tmp_path/'Operation.java').write_text('unchanged')
    item=dict(project=str(tmp_path),channel='INTERNET',operation_id='Example',payload=dict(
        contract=dict(service_api=dict(method_signatures=['public String execute(String xml, Connection connection)']))))
    result=load_deployment(item)
    assert result.operation.database=='read-only'
    assert result.operation.initialization=={}
    saved=yaml.safe_load((tmp_path/'values.yaml').read_text())
    assert 'password' not in saved['databases']['read-only']
    assert saved['databases']['read-only']['credentialsSecret']['passwordKey']=='password'
    assert load_deployment(item)==result
    (tmp_path/'standalone/operation.json').unlink()
    assert load_deployment(item)==result
    assert (tmp_path/'Operation.java').read_text()=='unchanged'


def test_yaml_definition_preserves_comments_case_and_string_values(tmp_path):
    spec=specification()
    spec.operation.initialization={'BankID':'0012','Enabled':False,'Text':'on','Empty':None}
    path=tmp_path/'values.yaml'
    write_deployment(path,spec)
    path.write_text('# Deployment configuration\n'+path.read_text(encoding='utf-8'),encoding='utf-8')
    assert read_deployment(path)==spec
    item=dict(project=str(tmp_path),channel='INTERNET',operation_id='Example',payload={})
    before=path.read_bytes()
    assert load_deployment(item)==spec and path.read_bytes()==before
    assert not (tmp_path/'microservice-deployment.json').exists()


def test_yaml_definition_rejects_invalid_configuration_and_unsafe_tags(tmp_path):
    path=tmp_path/'values.yaml'
    path.write_text('operation: {identity: INTERNET/Example, database: missing}\nhttp: {path: /api/test}\n')
    with pytest.raises(ValueError,match='unknown database'):read_deployment(path)
    path.write_text('!!python/object/apply:builtins.str [unsafe]')
    with pytest.raises(yaml.YAMLError):read_deployment(path)


def test_deployment_cli_reads_yaml_without_performing_external_actions(tmp_path,monkeypatch,capsys):
    import deploy_microservice
    spec=specification();path=tmp_path/'values.yaml';write_deployment(path,spec)
    calls=[]
    monkeypatch.setattr('sys.argv',['deploy_microservice.py','--project',str(tmp_path),'--definition',str(path)])
    monkeypatch.setattr(deploy_microservice,'execute_deployment',lambda project,definition,**flags:
        calls.append((project,definition,flags)) or {'deployed':False})
    deploy_microservice.main()
    assert calls==[(str(tmp_path),spec,dict(build=False,publish=False,deploy=False,values_path=path.resolve()))]
    assert json.loads(capsys.readouterr().out)=={'deployed':False}


def test_unknown_selected_database_is_not_defaulted():
    with pytest.raises(ValueError,match='unknown database'):
        MicroserviceDeployment.model_validate(dict(operation=dict(identity='A/B',database='other'),
            http=dict(path='/api/A/B'),databases={'default':dict(credentialsSecret=dict(name='secret'))}))


def test_http_resources_do_not_create_an_unneeded_database_pool(tmp_path):
    item=dict(project=str(tmp_path),channel='INTERNET',operation_id='Example',payload=dict(
        service_connections=[dict(resource_kind='external')],contract=dict(
            service_api=dict(method_signatures=['public String execute(String xml)']),
            runtime_resources=[dict(resource_type='RestClient',provider_type='RestClient')])))
    result=load_deployment(item)
    assert result.operation.database is None and result.databases=={}


def test_pool_bounds_and_plaintext_credentials_are_rejected():
    raw=specification().model_dump();raw['databases']['default']['password']='forbidden'
    with pytest.raises(ValueError):MicroserviceDeployment.model_validate(raw)
    raw=specification().model_dump();raw['databases']['default']['pool']['minimumIdle']=20
    with pytest.raises(ValueError):MicroserviceDeployment.model_validate(raw)


def test_managed_properties_and_case_sensitive_binding_cannot_be_changed():
    spec=specification();resources=managed_resources(spec)
    with pytest.raises(ValueError,match='converter-owned'):
        merge_managed_resources(dict(files={'src/main/resources/application.properties':'other'}),resources)
    with pytest.raises(ValueError,match='no native binding'):
        validate_initialization({'src/main/resources/initialization-bindings.json':'{"consumed_keys":["channel"]}'},spec)
    assert json.loads(resources['src/main/resources/operation-initialization.json'])==spec.operation.initialization


@pytest.mark.parametrize('database',['default','read-only',None])
def test_helm_lint_render_and_package_preserve_selection_and_context(tmp_path,database):
    spec=specification(database);(tmp_path/'target').mkdir();(tmp_path/'target/service.jar').write_bytes(b'fixture')
    chart,readiness=render_helm(tmp_path,spec)
    report=validate_helm(chart,spec)
    assert report['helm_passed'] and Path(report['chart_package']).exists()
    assert not readiness['deployment_ready'] and not readiness['deployed']
    values=(tmp_path/'values.yaml').read_text()
    assert 'password:' not in values and 'passwordKey:' in values if database else 'password:' not in values
    assert not (tmp_path/'standalone').exists()
    assert not (tmp_path/'src/main/java').exists()


def test_deployment_readiness_does_not_claim_image_or_database_exists():
    result=deployment_readiness(specification())
    assert not result['deployment_ready']
    assert 'databases.default.jdbcUrl' in result['unresolved']
    assert not result['deployed'] and not result['image_published']
