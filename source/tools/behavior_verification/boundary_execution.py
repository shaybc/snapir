"""Compile disposable snapshots and execute each boundary case in a fresh JVM."""
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from xml.etree import ElementTree as ET
from runtime.java_toolchain import run_java, java_version
from models.boundary_observation import BoundaryObservation
from tools.behavior_verification.java_tool import default_tool_path
from tools.behavior_verification.boundary_protocol import value_element, read_value, configuration_element
from tools.behavior_verification.boundary_contracts import boundary_contract


def compile_boundary_side(unit, boundary, binding, directory, side, tool=None, *, settings=()):
    """Return classes and hashes only after control instrumentation and compilation succeed."""
    directory.mkdir(parents=True)
    tool = Path(tool or default_tool_path()).resolve()
    if not tool.is_file(): raise ValueError('Build the Java behavior-verification tool before boundary execution')
    hashes = {'tool': _digest(tool)}
    hashes['binding'] = hashlib.sha256(json.dumps(binding.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    manifest = ET.Element('scope', side=side, context_class=binding.context_class,
        context_writer=binding.context_writer, context_remover=binding.context_remover)
    manifest.set('typed_native', str(side == 'native' and binding.native_entry is not None).lower())
    manifest.set('context_reader', binding.context_reader)
    manifest.set('context_snapshot', binding.context_snapshot)
    for setting in _settings(settings, binding):
        ET.SubElement(manifest, 'setting_method', implementation=setting['class'], method=setting['method'])
    if side == 'legacy':
        current = boundary_contract(unit, {'opStep': boundary.implementation_class})
        if current.source_manifest_hash != boundary.source_manifest_hash or current.configuration_hash != boundary.configuration_hash:
            raise ValueError('Boundary source/configuration revision changed before compilation')
        sources = unit['sources']
    else:
        sources = [dict(identity=item.path, content=item.content,
                        content_hash=hashlib.sha256(item.content.encode()).hexdigest()) for item in binding.sources]
    if not sources: raise ValueError('No supplied source for ' + side + ' boundary')
    for source in sources:
        text_hash = hashlib.sha256(source['content'].encode()).hexdigest()
        if side != 'legacy' and text_hash != source['content_hash']:
            raise ValueError('Boundary source content changed: ' + source['identity'])
        ET.SubElement(manifest, 'source', identity=source['identity'], hash=source['content_hash']).text = source['content']
        hashes['source:' + source['identity']] = source['content_hash']
        hashes['compiled_text:' + source['identity']] = text_hash
    for target, canonical in sorted(binding.external_bindings.items()):
        ET.SubElement(manifest, 'external_binding', target=target, canonical=canonical)
    if side == 'legacy':
        for node in boundary.reachable_slice.nodes:
            ET.SubElement(manifest, 'reachable', **{key: str(getattr(node, key)) for key in
                ('source_identity', 'start_line', 'end_line', 'start_column', 'end_column')})
        for node in boundary.reachable_slice.nodes:
            if node.kind not in {'method', 'constructor', 'static_initializer', 'instance_initializer'}: continue
            ET.SubElement(manifest, 'probe', id=node.id, kind='method', syntax_type={
                'method': 'MethodDeclaration', 'constructor': 'ConstructorDeclaration',
                'static_initializer': 'InitializerDeclaration', 'instance_initializer': 'InitializerDeclaration'}[node.kind],
                **{key: str(getattr(node, key)) for key in ('source_identity', 'start_line', 'end_line', 'start_column', 'end_column')})
        for item in boundary.parser_checklist.items if boundary.parser_checklist is not None else ():
            if item.kind != 'branch': continue
            ET.SubElement(manifest, 'probe', id=item.id, kind=item.kind, detail=item.detail, syntax_type=item.syntax_type,
                **{key: str(getattr(item, key)) for key in ('source_identity', 'start_line', 'end_line', 'start_column', 'end_column')})
    classpath = [str(tool)]
    for name in binding.classpath:
        path = Path(name).resolve()
        if not path.is_file() or path.suffix.lower() != '.jar': raise ValueError('Boundary dependencies must be explicit existing JARs')
        hashes['dependency:' + str(path)] = _digest(path); classpath.append(str(path))
    (directory / 'sources.xml').write_bytes(ET.tostring(manifest, encoding='utf-8').replace(b'\r', b'&#13;'))
    _run(['java', '-cp', os.pathsep.join(classpath), 'il.co.dcd.verification.HarnessInstrumentation',
          str(directory / 'sources.xml'), str(directory / 'instrumented'), str(directory / 'instrumentation.xml')], 120)
    issues = [item.get('message') for item in ET.parse(directory / 'instrumentation.xml').getroot().findall('issue')]
    if issues: raise ValueError('; '.join(issues[:12]))
    classes = directory / 'classes'; classes.mkdir()
    files = sorted((directory / 'instrumented').rglob('*.java'))
    _run(['javac', '--release', java_version(), '-encoding', 'UTF-8', '-cp', os.pathsep.join(classpath),
          '-d', str(classes), *map(str, files)], 120)
    if _digest(tool) != hashes['tool']: raise ValueError('Harness tool changed during compilation')
    for path in sorted(classes.rglob('*.class')): hashes['class:' + str(path.relative_to(classes))] = _digest(path)
    return dict(directory=directory, classes=classes, classpath=[str(classes), *classpath], hashes=hashes)


def verify_compiled_artifacts(compiled):
    if _digest(Path(compiled['classpath'][1])) != compiled['hashes']['tool']:
        raise ValueError('Harness tool changed during boundary execution')
    for name, digest in compiled['hashes'].items():
        if name.startswith('dependency:') and _digest(Path(name[len('dependency:'):])) != digest:
            raise ValueError('Boundary dependency changed during execution')
        if name.startswith('class:') and _digest(compiled['classes'] / name[len('class:'):]) != digest:
            raise ValueError('Boundary bytecode changed during execution')


def execute_boundary_case(compiled, unit, boundary, binding, case, timeout=15,deadline=None):
    """Any startup, timeout, instrumentation or protocol failure remains incomplete."""
    directory = compiled['directory'] / 'cases' / case.case_id
    directory.mkdir(parents=True, exist_ok=False)
    job = ET.Element('job', adapter_class=binding.adapter_class, kind=unit['kind'], implementation=boundary.implementation_class,
        **{name: getattr(binding, name) for name in ('context_class', 'tag_class', 'context_writer', 'context_remover', 'context_snapshot', 'step_context_setter')})
    values = case.model_dump(mode='json')
    values['settings'] = _settings(values['settings'], binding)
    job.append(value_element(values, 'case'))
    configuration = ET.SubElement(job, 'configuration')
    if unit['kind'] == 'configured_step':
        component = ET.SubElement(configuration, 'component', implementation=boundary.implementation_class)
        component.append(value_element(unit['effective_configuration']['attributes'], 'attributes'))
    else:
        definitions = {item['definition_id']: item for item in unit.get('referenced_definitions', [])}
        configuration.append(configuration_element(unit['effective_configuration'], definitions))
    if binding.native_entry is not None:
        from runtime.behavior_conversion.java_api_types import public_api_types
        entry = binding.native_entry.model_dump(mode='json')
        entry['native_types'] = sorted({name for source in binding.sources for name in public_api_types(source.content)})
        configuration[0].append(value_element(entry, 'native_entry'))
    ET.ElementTree(job).write(directory / 'job.xml', encoding='utf-8')
    try:
        if deadline is not None:
            timeout=min(timeout,deadline-time.monotonic())
            if timeout<=0:raise subprocess.TimeoutExpired('boundary expansion deadline',0)
        execution = _run(['java', '-ea', '-cp', os.pathsep.join(compiled['classpath']), 'il.co.dcd.verification.harness.BoundaryHarness',
              str(directory / 'job.xml'), str(directory / 'observation.xml')], timeout)
        (directory / 'stdout.txt').write_text(execution.stdout, encoding='utf-8')
        (directory / 'stderr.txt').write_text(execution.stderr, encoding='utf-8')
        result = read_value(ET.parse(directory / 'observation.xml').getroot())
        return BoundaryObservation.model_validate(result)
    except (OSError, ValueError, ET.ParseError, subprocess.TimeoutExpired) as error:
        return BoundaryObservation(case_id=case.case_id, status='verification_incomplete', issues=[str(error)])


def _run(command, timeout):
    result = run_java(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode: raise ValueError('Boundary JVM command failed: ' + (result.stderr + result.stdout)[-6000:])
    return result


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _settings(settings, binding):
    result = []
    for setting in settings:
        target = setting['class'] + '.' + setting['method']
        destination = binding.settings_bindings.get(target, {})
        result.append({**setting, 'class': destination.get('class', setting['class']),
                       'method': destination.get('method', setting['method'])})
    return result

