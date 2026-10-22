"""Resolve CCComplexOpStep targets from Composer Mapper Markdown evidence."""

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote

from tools.composer_mapper_tools.frontmatter_parser import parse_section, parse_key_value_bullets
from tools.composer_mapper_tools.operation_parser import parse_operation_note
from tools.composer_mapper_tools.opstep_parser import parse_opstep_note
from tools.composer_mapper_tools.channel_registry_parser import parse_channel_operation_registry
from tools.composer_mapper_tools.vault_manifest import operation_note_paths, read_vault_manifest

COMPLEX_CLASS = "com.ibm.il.dse.cc.cut.CCComplexOpStep"


def _links(section):
    """Keep URI escapes until resolution; percent signs in wiki filenames are literal."""
    return [match[0] or match[1].split('|', 1)[0].replace('%', '%25') for match in
            re.findall(r'\[[^\]]*\]\(([^)]+)\)|\[\[([^\]]+)\]\]', section)]


def _note_path(root, owner, target):
    """Try literal hash filenames, then strip a URI fragment before decoding once."""
    for destination in (target, target.split('#', 1)[0]):
        note = unquote(destination)
        if not note.endswith('.md'):
            note += '.md'
        for candidate in (root / note, owner.parent / note):
            path = candidate.resolve()
            if path.is_relative_to(root) and path.is_file():
                return path
    raise ValueError("Missing linked step note: " + target)


def _missing_target_detail(channel, name, operations):
    """Explain a missing implicit-base view without redirecting to a different channel view."""
    callee = channel + '/' + name
    base = 'XML/' + name
    if channel.upper() != 'XML' and base in operations:
        return ('Missing inherited XML-base operation view: ' + callee + '; ' + base
                + ' exists, but its caller-channel view is absent. Regenerate the vault with a Mapper '
                  'that includes the implicit XML base and local overrides.')
    return ('Target is missing in caller channel: ' + callee
            + '; cross-channel targets require explicit resolution')


def discover_operation_calls(vault, *, progress=None):
    """Read a vault without mutation; return channel-qualified operations, calls and issues."""
    root = Path(vault).resolve()
    manifest = read_vault_manifest(root, retain_inventory=False, progress=progress, allow_shared=True)
    if manifest is not None and manifest.get('vault_schema_version') == 3:
        return _discover_context_calls(root, manifest, progress)
    note_paths = operation_note_paths(root, manifest)
    registry = parse_channel_operation_registry(str(root / 'analysis/channel-operation-registry.md'))
    operations, calls, issues = {}, [], []
    if manifest is not None:
        issues.extend(dict(operation=item.get('operation', ''), step=item.get('step', ''), detail=item['detail'])
                      for item in manifest.get('diagnostics', []) if item.get('kind') in {'identity', 'source_parse'})
    documents = []
    for number, path in enumerate(note_paths, 1):
        if progress:
            progress(f'Reading operation {number}/{len(note_paths)}: {path.relative_to(root)}')
        text = path.read_text(encoding='utf-8-sig')
        op = parse_operation_note(text, str(path))
        channels = {op.channel} if op.channel else {channel for name, channel, _ in registry if name == op.id}
        if not op.id or not channels:
            issues.append(dict(operation=str(path.relative_to(root)), step='', detail='Operation ID or channel is missing'))
            continue
        for channel in sorted(channels):
            key = channel + '/' + op.id
            if key in operations:
                issues.append(dict(operation=key, step='', detail='Duplicate operation identity'))
                continue
            operations[key] = dict(operation_id=op.id, channel=channel, note=str(path.relative_to(root)),
                source_hash=op.source_hash, ref_formats=op.ref_formats)
            documents.append((key, op, path, text))
    for number, (caller, op, path, text) in enumerate(documents, 1):
        if progress:
            progress(f'Resolving calls {number}/{len(documents)}: {caller}')
        targets = _links(parse_section(text, 'Steps'))
        if op.steps and not targets:
            issues.append(dict(operation=caller, step='', detail='Steps have no resolvable Markdown links'))
        for target in targets:
            try:
                step_path = _note_path(root, path, target)
                step_text = step_path.read_text(encoding='utf-8-sig')
                step = parse_opstep_note(step_text, str(step_path))
                raw = parse_key_value_bullets(parse_section(step_text, 'Raw Attributes'))
                impl = raw.get('implClass') or step.impl_class or ''
                if impl != COMPLEX_CLASS and not impl.endswith('|' + COMPLEX_CLASS + ']]'):
                    continue
                channel = caller.split('/', 1)[0]
                if step.only_for and channel.upper() not in re.split(r'[,;\s]+', step.only_for.strip().upper()):
                    continue
                if step.parent_operation_id and step.parent_operation_id != op.id:
                    raise ValueError('Linked step belongs to another operation; possible Mapper step-ID collision')
                name = step.parameters.get('opExecuteName') or raw.get('opExecuteName')
                if not name:
                    raise ValueError('CCComplexOpStep has no opExecuteName')
                callee = channel + '/' + name
                if callee not in operations:
                    issues.append(dict(operation=caller, step=step.id, callee=callee,
                        note=str(step_path.relative_to(root)), parameters=step.parameters,
                        transitions=step.transitions, evidence_hash=hashlib.sha256(step_text.encode()).hexdigest(),
                        detail=_missing_target_detail(channel, name, operations)))
                    continue
                calls.append(dict(caller=caller, callee=callee, step=step.id,
                    note=str(step_path.relative_to(root)), parameters=step.parameters,
                    transitions=step.transitions, evidence_hash=hashlib.sha256(step_text.encode()).hexdigest()))
            except (OSError, ValueError) as exc:
                issues.append(dict(operation=caller, step=target, detail=str(exc)))
    return dict(operations=operations, calls=calls, issues=issues)


def _discover_context_calls(root, manifest, progress):
    """Read reachable runtime connections while reusing their canonical source notes."""
    operations, calls = {}, []
    issues = [dict(operation=item.get('operation', ''), step=item.get('step', ''), detail=item['detail'])
              for item in manifest.get('diagnostics', []) if item.get('kind') in {'identity', 'source_parse'}]
    documents, steps = {}, {}
    for number, context in enumerate(manifest['operation_contexts'], 1):
        key = context['channel'] + '/' + context['operation_id']
        if progress:
            progress(f'Reading operation connections {number}: {key}')
        note = context['note']
        if note not in documents:
            documents[note] = parse_operation_note((root / note).read_text(encoding='utf-8-sig'), str(root / note))
        op = documents[note]
        operations[key] = dict(operation_id=op.id, channel=context['channel'], note=note,
            source_hash=op.source_hash, ref_formats=op.ref_formats, definition_id=context['definition_id'])
        for call in context['calls']:
            step_note = call['step_note']
            if step_note not in steps:
                text = (root / step_note).read_text(encoding='utf-8-sig')
                steps[step_note] = (parse_opstep_note(text, str(root / step_note)), hashlib.sha256(text.encode()).hexdigest())
            step, evidence = steps[step_note]
            if step.parent_operation_id and step.parent_operation_id != op.id:
                raise ValueError('Context call step belongs to another source operation: ' + step_note)
            if (step.parameters.get('opExecuteName') or '') != call['target_name']:
                raise ValueError('Context call target disagrees with source step: ' + step_note)
            item = dict(caller=key, callee=call.get('target_context', context['channel'] + '/' + call['target_name']),
                step=step.id, note=step_note, parameters=step.parameters, transitions=step.transitions, evidence_hash=evidence)
            if call.get('detail'):
                item['operation'] = item.pop('caller')
                item['detail'] = call['detail']
                issues.append(item)
            else:
                calls.append(item)
    return dict(operations=operations, calls=calls, issues=issues)
