"""Read Eclipse deployment resources without treating packaging as conversion scope."""

from pathlib import Path, PureWindowsPath
from tools.source_discovery_tools.eclipse_metadata_snapshot import read_metadata


def project_path(project, value):
    """Resolve an Eclipse project-relative resource, refusing escapes and drive paths."""
    if PureWindowsPath(value).drive or '\\' in value:
        raise ValueError('Unsupported Eclipse resource path: ' + value)
    base = Path(project).resolve()
    result = (base / value.lstrip('/')).resolve()
    if not result.is_relative_to(base):
        raise ValueError('Eclipse resource escapes project: ' + value)
    return result


def component_metadata(project, workspace, evidence):
    """Return declared resources and module identities; a valid empty list is meaningful."""
    path = Path(project) / '.settings/org.eclipse.wst.common.component'
    root = read_metadata(path, workspace, evidence)
    if root is None:
        raise ValueError('Missing Eclipse component metadata: ' + str(path))
    module = root.find('wb-module')
    if root.tag != 'project-modules' or module is None or len(root.findall('wb-module')) != 1:
        raise ValueError('Unsupported Eclipse component metadata: ' + str(path))
    resources = []
    for node in module.findall('wb-resource'):
        source, destination = node.get('source-path'), node.get('deploy-path')
        if source is None or destination is None:
            raise ValueError('Incomplete Eclipse resource: ' + str(path))
        resources.append((project_path(project, source), destination))
    references = []
    for node in module.findall('dependent-module'):
        handle = node.get('handle', '')
        parts = handle.removeprefix('module:/resource/').split('/') if handle.startswith('module:/resource/') else []
        if len(parts) != 2 or any(part in ('', '.', '..') or '\\' in part for part in parts):
            raise ValueError('Unsupported Eclipse module handle: ' + handle)
        references.append(parts[0])
    return resources, sorted(set(references))
