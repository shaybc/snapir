"""Reuse approved, build-verified native dependencies for isolated comparison snapshots."""
from pathlib import Path
from xml.etree import ElementTree as ET
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete


def native_runtime_classpath(project, context):
    """Only runtime POM dependencies, resolved through the existing policy-aware verifier."""
    pom = Path(project) / 'pom.xml'
    if not pom.is_file(): return []
    root = ET.parse(pom).getroot()
    namespace = {'m': root.tag.split('}')[0][1:]} if root.tag.startswith('{') else {}
    prefix = 'm:' if namespace else ''
    dependencies = root.findall(prefix + 'dependencies/' + prefix + 'dependency', namespace)
    paths = set()
    for node in dependencies:
        value = lambda key: node.findtext(prefix + key, default='', namespaces=namespace)
        if value('scope') in {'test', 'provided'}: continue
        if not value('version') or '${' in value('version'):
            raise VerificationIncomplete(dict(stage='classpath', errors=['Runtime dependency needs a resolved pinned version']))
        dependency = MavenDependency(group_id=value('groupId'), artifact_id=value('artifactId'), version=value('version'))
        if not hasattr(context.verifier, 'resolved_runtime_classpath'):
            raise VerificationIncomplete(dict(stage='classpath', errors=['Approved runtime dependency resolution is unavailable']))
        paths.update(context.verifier.resolved_runtime_classpath(dependency))
    return sorted(paths)
