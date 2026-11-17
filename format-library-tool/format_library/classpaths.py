"""Collect source projects and explicit Eclipse/local Maven dependency evidence."""
import os
from pathlib import Path
from xml.etree import ElementTree as ET


def inventory(config):
    """Return project-owned sources and ordered libraries; report unavailable dependency evidence."""
    root = Path(config['source_root'])
    if not root.is_dir():
        raise ValueError('source_root is not an existing directory: ' + str(root))
    files = []
    excluded = [Path(config[key]).resolve() for key in ('output_root', 'approved_library_root')]
    for folder, directories, names in os.walk(root):
        directories[:] = sorted(item for item in directories if item not in config['source_excludes']
            and not any((Path(folder) / item).resolve().is_relative_to(path) for path in excluded))
        files.extend(Path(folder) / name for name in sorted(names) if name.endswith('.java') or name in {'.classpath', 'pom.xml', '.project'})
    descriptors = sorted({path.parent for path in files if path.name in {'.classpath', 'pom.xml', '.project'}},
                         key=lambda path: len(path.parts), reverse=True)
    sources = [path.resolve() for path in files if path.suffix == '.java']
    owners = {path: next((project for project in descriptors if path.is_relative_to(project)), root) for path in sources}
    projects = {str(path): dict(id=str(path), roots=[], libraries=[], references=[], issues=[], source_files=[],
                               exported_libraries=[], exported_references=[])
                for path in sorted(set(owners.values()) | set(descriptors))}
    names = {}
    for project in projects:
        path = Path(project)
        descriptor = path / '.project'
        name = ET.parse(descriptor).findtext('name') if descriptor.is_file() else path.name
        names.setdefault(name, []).append(project)
    for path, owner in owners.items():
        projects[str(owner)]['source_files'].append(str(path))
    for identity, project in projects.items():
        path = Path(identity)
        descriptor = path / '.classpath'
        if descriptor.is_file():
            for entry in ET.parse(descriptor).getroot().findall('classpathentry'):
                kind, value = entry.get('kind'), entry.get('path', '')
                previous_libraries = len(project['libraries'])
                if kind == 'src':
                    if value.startswith('/'):
                        peers = names.get(value[1:], [])
                        if len(peers) == 1:
                            project['references'].extend(peers)
                            if entry.get('exported') == 'true':
                                project['exported_references'].extend(peers)
                        else:
                            project['issues'].append('Unresolved Eclipse project reference: ' + value)
                    else:
                        project['roots'].append(str((path / value).resolve()))
                elif kind == 'lib':
                    absolute = Path(value)
                    if value.startswith('/') and os.name == 'nt':
                        project_name, _, remaining = value[1:].partition('/')
                        peers = names.get(project_name, [])
                        if len(peers) == 1:
                            absolute = Path(peers[0]) / remaining
                    project['libraries'].append(str((path / absolute).resolve()))
                elif kind == 'var':
                    variable, _, remaining = value.partition('/')
                    base = config['eclipse_classpath_variables'].get(variable)
                    if base:
                        project['libraries'].append(str((Path(base) / remaining).resolve()))
                    else:
                        project['issues'].append('Unresolved Eclipse variable: ' + value)
                elif kind == 'con' and 'JRE_CONTAINER' not in value:
                    bindings = config['eclipse_project_classpath_containers'].get(path.name, {})
                    resolved = bindings.get(value, config['eclipse_classpath_containers'].get(value))
                    if resolved is None:
                        project['issues'].append('Unresolved Eclipse container: ' + value)
                    else:
                        project['libraries'].extend(resolved)
                if entry.get('exported') == 'true':
                    project['exported_libraries'].extend(project['libraries'][previous_libraries:])
        if not project['roots']:
            defaults = [path / 'src/main/java', path / 'src']
            project['roots'] = [str(next((item for item in defaults if item.is_dir()), path).resolve())]
        # Maven-only projects need an effective classpath, not guessed versions/transitive dependencies.
        if (path / 'pom.xml').is_file() and not descriptor.is_file():
            pom = ET.parse(path / 'pom.xml').getroot()
            if pom.findall('.//{*}dependency') and not config['classpath_jars']:
                project['issues'].append('Maven dependencies require classpath_jars with the effective dependency JARs')
        project['libraries'].extend(config['classpath_jars'])
        project['libraries'].extend(config['framework_jars'])
        project['libraries'] = list(dict.fromkeys(project['libraries']))
        for library in project['libraries']:
            if not Path(library).is_file():
                project['issues'].append('Missing JAR: ' + library)
    # Direct project sources are visible; only explicitly exported transitive entries propagate.
    for project in projects.values():
        pending, seen = list(project['references']), set()
        while pending:
            reference = pending.pop(0)
            if reference in seen:
                continue
            seen.add(reference)
            target = projects[reference]
            project['libraries'].extend(item for item in target['exported_libraries'] if item not in project['libraries'])
            pending.extend(target['exported_references'])
        project['visible_projects'] = [project['id'], *sorted(seen)]
    return dict(projects=list(projects.values()), sources=[dict(file=str(path), project=str(owner)) for path, owner in owners.items()])
