"""Find required Java classes in the exact JARs selected by Maven resolution."""

import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile


def discover_class_owners(dependency, class_names, repository, directory, arguments, run):
    """Resolve one proposal's dependency graph and return verified class owners.

    Uses the verifier's Maven arguments and runner, so mirrors, cache, timeout and
    Java environment stay unchanged. Only the resolved graph is searched, never
    unrelated cached JARs. Writes a disposable POM and graph in directory.
    """
    directory, repository = Path(directory), Path(repository)
    root = ElementTree.Element('project', xmlns='http://maven.apache.org/POM/4.0.0')
    for name, value in (('modelVersion', '4.0.0'), ('groupId', 'snapir.verification'),
                        ('artifactId', 'dependency-class-ownership'), ('version', '1.0.0')):
        ElementTree.SubElement(root, name).text = value
    declared = ElementTree.SubElement(ElementTree.SubElement(root, 'dependencies'), 'dependency')
    for name, value in (('groupId', dependency.group_id), ('artifactId', dependency.artifact_id),
                        ('version', dependency.version), ('scope', dependency.scope)):
        ElementTree.SubElement(declared, name).text = value
    pom, graph = directory / 'pom.xml', directory / 'class-ownership.json'
    pom.write_bytes(ElementTree.tostring(root, encoding='utf-8', xml_declaration=True))
    result = run(arguments + ['org.apache.maven.plugins:maven-dependency-plugin:3.8.1:tree',
                             '-DoutputType=json', f'-DoutputFile={graph}'], str(directory))
    if result.returncode or not graph.is_file():
        raise ValueError('Maven could not inspect the resolved dependency graph for ' + dependency.coordinates +
                         '. See logs/model_execution.log for Maven diagnostics.')
    pending = list(json.loads(graph.read_text(encoding='utf-8')).get('children', []))
    resolved, seen = [], set()
    while pending:
        node = pending.pop()
        pending.extend(node.get('children', []))
        kind, classifier = node.get('type', 'jar'), node.get('classifier') or ''
        if kind != 'jar':
            continue
        group, artifact, version = node['groupId'], node['artifactId'], node['version']
        identity = (group, artifact, version, classifier)
        if identity in seen:
            continue
        seen.add(identity)
        suffix = '-' + classifier if classifier else ''
        path = repository.joinpath(*group.split('.'), artifact, version, f'{artifact}-{version}{suffix}.jar')
        coordinates = f'{group}:{artifact}:{version}'
        download = f'{group}:{artifact}:{version}:jar:{classifier}' if classifier else coordinates
        if not path.is_file():
            fetched = run(arguments + ['org.apache.maven.plugins:maven-dependency-plugin:3.8.1:get',
                                      f'-Dartifact={download}', '-Dtransitive=false'], str(directory))
            if fetched.returncode or not path.is_file():
                raise ValueError('Maven could not inspect resolved JAR ' + download +
                                 '. See logs/model_execution.log for Maven diagnostics.')
        resolved.append((coordinates, classifier, node.get('scope') or dependency.scope, path))
    owners = {name: [] for name in class_names}
    for coordinates, classifier, scope, path in sorted(resolved):
        with ZipFile(path) as jar:
            entries = set(jar.namelist())
        for name in class_names:
            if name.replace('.', '/') + '.class' in entries:
                owners[name].append(dict(coordinates=coordinates, classifier=classifier,
                                         scope=scope, jar=path.name))
    return owners


def class_owner_feedback(dependency, owners):
    """Describe a verifiable metadata correction without choosing ambiguous owners."""
    messages = []
    for name, candidates in sorted(owners.items()):
        prefix = f'Required API missing from {dependency.coordinates}: {name}.'
        if len(candidates) == 1:
            owner = candidates[0]
            classifier = f" (classifier {owner['classifier']})" if owner['classifier'] else ''
            messages.append(prefix + f" Verified owner in the resolved dependency graph: {owner['coordinates']}" +
                classifier + f" ({owner['jar']}, scope {owner['scope']}). " +
                f"Remove {name} from required_classes on {dependency.coordinates}; declare that required class " +
                f"on {owner['coordinates']} at the resolved version and scope {owner['scope']}. " +
                'Keep the original dependency only if it is independently needed; do not change versions or guess another JAR.')
        elif candidates:
            choices = '; '.join(owner['coordinates'] + ' (' + owner['jar'] + ')' for owner in candidates)
            messages.append(prefix + ' Multiple resolved JARs contain this class: ' + choices +
                '. Ownership is ambiguous. Do not guess; resolve the duplicate dependency before declaring the class owner.')
        else:
            messages.append(prefix + ' No JAR in this resolved dependency graph contains the class. ' +
                'Check the class name and supply a verifiable pinned dependency; do not invent an artifact or version.')
    return '\n'.join(messages)
