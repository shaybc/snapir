"""Supply current target dependency coordinates without guessing or changing POMs."""

import re
from pathlib import Path
from xml.etree import ElementTree
from models.maven_dependency import MavenDependency


def known_dependencies(projects, planned):
    """Read pinned direct target dependencies and planned native-library dependencies."""
    known = {}
    for project in projects:
        pom = Path(project) / "pom.xml"
        if not pom.exists():
            continue
        root = ElementTree.parse(pom).getroot()
        properties = {node.tag.split("}")[-1]: node.text or "" for node in root.findall("{*}properties/*")}
        def resolved(value):
            for _ in range(len(properties) + 1):
                replaced = re.sub(r"\$\{([^}]+)\}", lambda match: properties.get(match[1], match[0]), value or "")
                if replaced == value:
                    break
                value = replaced
            return value
        managed = {(resolved(node.findtext("{*}groupId")), resolved(node.findtext("{*}artifactId"))): node
                   for node in root.findall("{*}dependencyManagement/{*}dependencies/{*}dependency")}
        for node in root.findall("{*}dependencies/{*}dependency"):
            group, artifact = resolved(node.findtext("{*}groupId")), resolved(node.findtext("{*}artifactId"))
            default = managed.get((group, artifact))
            version = resolved(node.findtext("{*}version") or (default.findtext("{*}version") if default is not None else ""))
            scope = resolved(node.findtext("{*}scope") or (default.findtext("{*}scope") if default is not None else "compile")) or "compile"
            if not version or "${" in version:
                raise ValueError(f"Cannot supply current dependency version for {group}:{artifact} from {pom}: unresolved version {version!r}")
            dependency = MavenDependency(group_id=group, artifact_id=artifact, version=version, scope=scope,
                reason="Current target POM dependency", required_classes=[])
            _remember(known, dependency)
    for dependency in planned:
        _remember(known, dependency)
    return [dependency.model_dump(mode="json") for dependency in known.values()]


def _remember(known, dependency):
    key = (dependency.group_id, dependency.artifact_id)
    previous = known.get(key)
    if previous and (previous.version, previous.scope) != (dependency.version, dependency.scope):
        raise ValueError(f"Conflicting target dependency requirements for {dependency.group_id}:{dependency.artifact_id}: "
                         f"{previous.version} scope {previous.scope} versus {dependency.version} scope {dependency.scope}")
    known[key] = dependency
