"""Verify classpath-only driver metadata and explicit unknown-version handling."""

from zipfile import ZipFile
from models.java_classpath_index import JavaClasspathIndex
from tools.maven_dependency_tools.driver_metadata import driver_candidates


def test_filename_does_not_establish_coordinates_or_version(tmp_path):
    jar = tmp_path / 'vendor-driver-99.99.jar'
    with ZipFile(jar, 'w') as output:
        output.writestr('example/Driver.class', b'fixture')
        output.writestr('META-INF/MANIFEST.MF', 'Implementation-Version: 4.5\n')
    index = JavaClasspathIndex(classes={'example.Driver': ['jar:' + str(jar)]})
    candidate, = driver_candidates('example.Driver', index)
    assert candidate['manifest_version'] == '4.5'
    assert 'dependency' not in candidate
    assert driver_candidates('unrelated.Driver', index) == []


def test_multiple_embedded_coordinates_are_not_arbitrarily_selected(tmp_path):
    jar = tmp_path / 'shaded.jar'
    with ZipFile(jar, 'w') as output:
        for artifact in ['one', 'two']:
            output.writestr('META-INF/maven/example/' + artifact + '/pom.properties',
                            'groupId=example\nartifactId=' + artifact + '\nversion=1\n')
    candidate, = driver_candidates('example.Driver', JavaClasspathIndex(classes={'example.Driver': ['jar:' + str(jar)]}))
    assert 'dependency' not in candidate and 'ambiguous' in candidate['issue']


def test_sidecar_pom_uses_artifact_coordinates_and_parent_version(tmp_path):
    jar = tmp_path / 'driver.jar'
    with ZipFile(jar, 'w') as output:
        output.writestr('example/Driver.class', b'fixture')
    jar.with_suffix('.pom').write_text('<project><parent><groupId>example</groupId>'
        '<artifactId>parent</artifactId><version>2.3</version></parent>'
        '<artifactId>driver</artifactId></project>')
    candidate, = driver_candidates('example.Driver', JavaClasspathIndex(
        classes={'example.Driver': ['jar:' + str(jar)]}))
    assert candidate['dependency']['artifact_id'] == 'driver'
    assert candidate['dependency']['version'] == '2.3'
