"""Resolve internal and external endpoints without changing the service API contract."""
import pytest

from models.pipeline_configuration import PipelineConfiguration
from models.service_address import ServiceAddress
from runtime.service_addresses import operation_address, service_url
from runtime.service_generation.helm_values import deployment_values, deployment_from_values
from models.microservice_deployment import MicroserviceDeployment


def test_internal_and_external_profiles_use_the_same_property():
    profile = PipelineConfiguration(deployment_environment='test', service_environments={'test': dict(
        namespace='bank-test', external_url_pattern='https://{service_name}.apps.example.test', service_port=8081)})
    address = operation_address(profile, 'INTERNET', 'GetLinks', 'operations.links.base-url')
    assert service_url(address, 'microservice') == 'http://internet-getlinks.bank-test.svc.cluster.local:8081'
    assert service_url(address, 'standalone') == 'https://internet-getlinks.apps.example.test'
    assert address.base_url_property == 'operations.links.base-url'


def test_internal_profile_never_falls_back_to_external():
    address = ServiceAddress(base_url='https://external.example', base_url_property='operations.a.base-url')
    with pytest.raises(ValueError, match='microservice'):
        service_url(address, 'microservice')


def test_explicit_service_identity_and_port_override_environment():
    profile = PipelineConfiguration(deployment_environment='test', service_environments={'test': dict(namespace='bank')},
        deployment_values={'WEB/A': dict(service_name='custom-release', namespace='other', service_port=9090,
                                        external_base_url='https://custom.example')})
    address = operation_address(profile, 'WEB', 'A', 'operations.a.base-url')
    assert service_url(address, 'microservice') == 'http://custom-release.other.svc.cluster.local:9090'
    assert service_url(address, 'standalone') == 'https://custom.example'


def test_helm_roundtrip_preserves_service_urls_and_name():
    spec = MicroserviceDeployment(operation=dict(identity='WEB/A', database=None),
        http=dict(path='/operations/WEB/A', serviceName='web-a'),
        serviceUrls={'operations.b.base-url': 'http://web-b.bank.svc:8080'})
    assert deployment_from_values(deployment_values(spec)) == spec


def test_current_environment_overrides_previously_published_internal_address():
    profile = PipelineConfiguration(deployment_environment='production', service_environments={
        'production': dict(namespace='bank-production', service_port=9090,
                           external_url_pattern='https://{service_name}.production.example')},
        deployment_values={'WEB/A': dict(service_port=9090)})
    saved = ServiceAddress(base_url_property='operations.a.base-url', service_name='web-a', namespace='old-test',
                           port=8080, internal_base_url='http://web-a.old-test.svc:8080')
    address = operation_address(profile, 'WEB', 'A', saved.base_url_property, saved=saved)
    assert service_url(address, 'microservice') == 'http://web-a.bank-production.svc.cluster.local:9090'
    assert service_url(address, 'standalone') == 'https://web-a.production.example'


def test_publication_uses_approved_service_port_and_name(tmp_path):
    from runtime.service_addresses import published_operation_address
    from runtime.service_generation.deployment_configuration import write_deployment
    spec = MicroserviceDeployment(operation=dict(identity='WEB/A', database=None),
        http=dict(path='/operations/WEB/A', port=9091, serviceName='actual-release'),
        deployment=dict(namespace='actual-namespace'))
    write_deployment(tmp_path / 'values.yaml', spec)
    profile = PipelineConfiguration(deployment_environment='test', service_environments={'test': dict(namespace='default')})
    address = published_operation_address(profile, 'WEB', 'A', 'operations.a.base-url', tmp_path)
    assert service_url(address, 'microservice') == 'http://actual-release.actual-namespace.svc.cluster.local:9091'
