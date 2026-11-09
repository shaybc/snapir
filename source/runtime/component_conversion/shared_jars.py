"""Package only a neutral group's owned classes, excluding compiled prerequisite copies."""
import io
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

from tools.shared_artifact_store.manifests import content_hash


def component_package(candidate, bundle, key):
    """Retain executed evidence, source and an immutable JAR for one validated group."""
    if not candidate.results:
        raise ValueError('A shared component requires current component validation')
    root = Path(next(iter(candidate.results.values())).artifact_root)
    files = {'bundle.json': bundle.model_dump_json().encode()}
    owned = [file.path for file in bundle.files if file.path.startswith('src/main/java/')]
    from tools.shared_artifact_store.jars import owned_class_entries
    classes = {name: root / 'target/classes' / name for name in owned_class_entries(root / 'target/classes', bundle.files)}
    if not classes:
        raise ValueError('Shared JAR requires retained compiled owned classes')
    for file in bundle.files:
        if file.path.startswith('src/main/resources/'):
            name = file.path.removeprefix('src/main/resources/')
            compiled = root / 'target/classes' / name
            if not compiled.is_file():
                raise ValueError('Shared component resource was not retained by its build')
            classes[name] = compiled
    from tools.shared_artifact_store.jars import compiled_jar
    from runtime.component_conversion.shared_bindings import request_bindings
    binary = compiled_jar(root / 'target/classes', classes)
    artifact = 'native-component-' + key[:20]
    version = '1.0.0-' + content_hash(dict(key=key, binary=hashlib.sha256(binary).hexdigest()))[:20]
    coordinates = dict(group_id='il.co.dcd.converted', artifact_id=artifact, version=version)
    pom = ElementTree.Element('project', xmlns='http://maven.apache.org/POM/4.0.0')
    for name, value in [('modelVersion', '4.0.0'), ('groupId', coordinates['group_id']), ('artifactId', artifact), ('version', version)]:
        ElementTree.SubElement(pom, name).text = value
    dependencies = ElementTree.SubElement(pom, 'dependencies')
    pins = [item.model_dump(mode='json') if hasattr(item, 'model_dump') else item
            for item in [*candidate.dependencies, *bundle.dependencies]]
    from tools.state_store_tools.component_reuse import group_uses
    uses = group_uses(candidate.conn, candidate.config.run_id)
    generated = [uses[identity] for identity in candidate.group.dependencies if identity in uses]
    pins.extend(dict(item['metadata']['coordinates'], scope='compile') for item in generated)
    for pin in pins:
        if pin.get('scope', 'compile') == 'test':
            continue
        dependency = ElementTree.SubElement(dependencies, 'dependency')
        for name, field in [('groupId', 'group_id'), ('artifactId', 'artifact_id'), ('version', 'version'), ('scope', 'scope')]:
            ElementTree.SubElement(dependency, name).text = pin.get(field, 'compile')
    files['artifacts/' + artifact + '.jar'] = binary
    pom_bytes = ElementTree.tostring(pom, encoding='utf-8', xml_declaration=True)
    files['artifacts/' + artifact + '.pom'] = pom_bytes
    for path in root.rglob('*'):
        if path.is_file() and not path.is_symlink():
            relative = path.relative_to(root).as_posix()
            if relative == 'pom.xml' or relative.startswith(('src/', 'target/surefire-reports/')) or relative.startswith('component-'):
                files['evidence/' + relative] = path
    from tools.conversion_tools.dependency_planning.reuse_sources import component_input_identity
    retained = root / 'retained-dependencies'
    if retained.exists():
        from runtime.retained_libraries.artifacts import verify_portable
        verify_portable(retained)
        for path in retained.rglob('*'):
            if path.is_file():
                files['artifacts/retained-dependencies/' + path.relative_to(retained).as_posix()] = path
    return files, dict(validated=True, validation_scope='component_build_and_tests', behavioral_equivalence='not_established',
                       input_identity=component_input_identity(candidate.plan, candidate.group, candidate.profile),
                       bindings=request_bindings(candidate.request),
                       coordinates=coordinates, owned_sources=owned, classes=sorted(classes),
                       logical_components=sorted(candidate.plan.components[member].label for member in candidate.group.members),
                       pom_content=pom_bytes.decode('utf-8'),
                       generated_dependencies=[dict(key=item['lookup_key'], revision=item['revision']) for item in generated],
                       retained_dependencies='artifacts/retained-dependencies' if retained.exists() else None,
                       jar='artifacts/' + artifact + '.jar', pom='artifacts/' + artifact + '.pom')
