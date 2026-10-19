"""Verify dependency APIs against actual configured JDK classes, not package prefixes."""

import json
from pathlib import Path
from zipfile import ZipFile

import pytest
import shutil

from models.maven_dependency import MavenDependency
from runtime.service_generation.response import parse_service_response
from tests.test_dependency_class_ownership import jar, mock_resolution
from tools.maven_dependency_tools.platform_classes import platform_class_owners


def test_latest_jdbc_proposals_accept_selected_jdk_and_resolved_spring_api(monkeypatch, tmp_path):
    responses = json.loads((Path(__file__).parent / 'runtime/fixtures/latest_service_generation_responses.json').read_text())
    home = tmp_path / 'jdk'
    (home / 'jmods').mkdir(parents=True)
    with ZipFile(home / 'jmods/java.sql.jmod', 'w') as archive:
        archive.writestr('classes/javax/sql/DataSource.class', b'fixture')
        archive.writestr('classes/java/sql/Connection.class', b'fixture')
    for response in responses[:2]:
        proposal = next(item for item in parse_service_response(response)['dependencies'] if item['artifact_id'] == 'spring-boot-starter-jdbc')
        dependency = MavenDependency.model_validate(proposal)
        jar(tmp_path, dependency.group_id, dependency.artifact_id, dependency.version, [])
        jar(tmp_path, 'org.springframework', 'spring-jdbc', '6.2.19', ['org.springframework.jdbc.datasource.DriverManagerDataSource'])
        verifier, calls = mock_resolution(monkeypatch, tmp_path, [dict(groupId='org.springframework', artifactId='spring-jdbc', version='6.2.19', type='jar')])
        verifier.environment = {'JAVA_HOME': str(home)}
        original = dependency.model_dump()
        verifier(dependency)
        assert dependency.model_dump() == original
        assert any(any('tree' in arg for arg in call) for call in calls)
        dependency.required_classes.append('javax.sql.DoesNotExist')
        with pytest.raises(ValueError, match='javax.sql.DoesNotExist'):
            verifier(dependency)


def test_platform_inventory_is_selected_by_home_and_detects_archive_changes(tmp_path):
    home = tmp_path / 'jdk'
    (home / 'jmods').mkdir(parents=True)
    archive = home / 'jmods/java.base.jmod'
    with ZipFile(archive, 'w') as file:
        file.writestr('classes/java/lang/String.class', b'fixture')
    names = ['java.lang.String', 'java.util.NewType', 'javax.external.Api']
    assert set(platform_class_owners(names, {'JAVA_HOME': str(home)})) == {'java.lang.String'}
    with ZipFile(archive, 'a') as file:
        file.writestr('classes/java/util/NewType.class', b'fixture')
    assert set(platform_class_owners(names, {'JAVA_HOME': str(home)})) == {'java.lang.String', 'java.util.NewType'}
    assert platform_class_owners(names, {'JAVA_HOME': str(tmp_path / 'different-jdk')}) == {}


def test_java25_actual_inventory_proves_standard_classes():
    home = Path('C:/Program Files/Java/jdk-25.0.3')
    if not home.is_dir():
        pytest.skip('Java 25 fixture unavailable')
    names = ['javax.sql.DataSource', 'java.sql.Connection', 'java.lang.String', 'javax.xml.parsers.DocumentBuilder', 'javax.sql.DoesNotExist']
    found = platform_class_owners(names, {'JAVA_HOME': str(home)})
    assert set(found) == set(names[:-1])
    assert any('java.sql.jmod' in path for path in found['javax.sql.DataSource'])


def test_latest_jdbc_proposals_verify_with_real_java25_and_offline_maven(monkeypatch):
    from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
    from runtime.java_toolchain import java_scope
    from tests.runtime.test_behavior_conversion import profile
    home = Path('C:/Program Files/Java/jdk-25.0.3')
    cache = Path.home() / '.m2/repository'
    starter = cache / 'org/springframework/boot/spring-boot-starter-jdbc/3.5.16/spring-boot-starter-jdbc-3.5.16.jar'
    if not home.is_dir() or not shutil.which('mvn') or not starter.is_file():
        pytest.skip('Offline Java25/Spring JDBC fixture unavailable')
    verifier = MavenRepositoryVerifier(None, [], str(cache))
    arguments = verifier._arguments
    monkeypatch.setattr(verifier, '_arguments', lambda: arguments() + ['--offline'])
    saved = json.loads((Path(__file__).parent / 'runtime/fixtures/latest_service_generation_responses.json').read_text())
    with java_scope(profile(java_version=25, java_home=str(home))):
        for response in saved[:2]:
            proposal = next(item for item in parse_service_response(response)['dependencies'] if item['artifact_id'] == 'spring-boot-starter-jdbc')
            verifier(MavenDependency.model_validate(proposal))
