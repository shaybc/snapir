"""Retain source for converter-owned Maven test helpers that public repositories cannot supply."""
from pathlib import Path
import shutil
from xml.etree import ElementTree


def write_standalone_test_support(project):
    """Copy the declared fixture test helper's sources, never its build output or runtime dependencies."""
    project = Path(project)
    pom = project / 'pom.xml'
    if not pom.is_file():
        return
    namespace = {'m': 'http://maven.apache.org/POM/4.0.0'}
    tree = ElementTree.parse(pom)
    dependencies = tree.findall('m:dependencies/m:dependency', namespace)
    helper = Path(__file__).resolve().parents[2] / 'behavior-verification-java'
    definition = ElementTree.parse(helper / 'pom.xml')
    identity = tuple(definition.findtext('m:' + name, namespaces=namespace)
                     for name in ('groupId', 'artifactId', 'version'))
    for dependency in dependencies:
        candidate = tuple(dependency.findtext('m:' + name, namespaces=namespace)
                          for name in ('groupId', 'artifactId', 'version'))
        if candidate[:2] != identity[:2]:
            continue
        if candidate != identity or dependency.findtext('m:scope', namespaces=namespace) != 'test':
            raise ValueError('Standalone fixture helper must match the converter-owned test-only Maven artifact')
        target = project / 'standalone/test-support/behavior-verification'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(helper / 'pom.xml', target / 'pom.xml')
        shutil.copytree(helper / 'src/main', target / 'src/main', dirs_exist_ok=True)
