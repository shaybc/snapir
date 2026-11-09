"""Preserve Maven parent/BOM metadata required by a relocated retained repository."""

from xml.etree import ElementTree
from models.maven_dependency import MavenDependency
from tools.shared_artifact_store.manifests import contained_path


def metadata_dependencies(repository, pom_name, *, seen=None):
    """Return available parent and imported-BOM POMs without guessing unresolved properties."""
    seen = set() if seen is None else seen
    if pom_name in seen:
        return {}
    seen.add(pom_name)
    path = contained_path(repository, pom_name)
    if not path.is_file():
        raise ValueError('Required retained Maven metadata is missing: ' + pom_name)
    root = ElementTree.parse(path).getroot()
    properties = {node.tag.split('}')[-1]: node.text or '' for node in root.findall('{*}properties/*')}
    result = {}
    parent = root.find('{*}parent')
    nodes = ([parent] if parent is not None else []) + [node for node in root.findall('{*}dependencyManagement/{*}dependencies/{*}dependency')
        if node.findtext('{*}scope') == 'import' and node.findtext('{*}type') == 'pom']
    for node in nodes:
        values = []
        for key in ('groupId', 'artifactId', 'version'):
            value = node.findtext('{*}' + key) or ''
            for _ in range(len(properties) + 1):
                if value.startswith('${') and value.endswith('}'):
                    value = properties.get(value[2:-1], value)
            if not value or '${' in value:
                raise ValueError('Unresolved retained Maven parent/BOM coordinate: ' + pom_name)
            values.append(value)
        dependency = MavenDependency(group_id=values[0], artifact_id=values[1], version=values[2], reason='Retained Maven metadata')
        from runtime.retained_libraries.artifacts import archive_path
        name = archive_path(dependency, 'pom')
        result[name] = contained_path(repository, name)
        result.update(metadata_dependencies(repository, name, seen=seen))
    return result
