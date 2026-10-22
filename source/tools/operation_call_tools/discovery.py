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
    """Read both standard Markdown links and Obsidian links."""
    return [unquote(match[0] or match[1].split('|', 1)[0]) for match in
            re.findall(r'\[[^\]]*\]\(([^)]+)\)|\[\[([^\]]+)\]\]', section)]


def _note_path(root, owner, target):
    """Resolve Mapper vault-root links or ordinary relative note links safely."""
    target = target.split('#', 1)[0]
    if not target.endswith('.md'):
        target += '.md'
    for candidate in (root / target, owner.parent / target):
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
    manifest = read_vault_manifest(root, retain_inventory=False, progress=progress)
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
