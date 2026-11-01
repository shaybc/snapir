"""Convert bounded configured subtrees bottom up, then verify the unchanged whole format."""
import json
from pathlib import Path
from models.native_component_bundle import NativeComponentBundle
from models.native_format_component_bundle import NativeFormatComponentBundle
from runtime.behavior_conversion.generation import generate
from runtime.component_conversion.scope import partition_task
from runtime.component_conversion.partition_requests import partition_request, fits_partition, PART_INSTRUCTION
from runtime.component_conversion.partition_validation import SubtreeCandidateValidator
from tools.conversion_tools.component_partition import splittable_children, subtree_at
from tools.conversion_tools.scoped_reuse.fingerprints import digest

ROOT_INSTRUCTION = '''
The trusted whole format is represented by format_partition.tree plus frozen native_subtree
contracts at exact original child positions. Compose these actual APIs, with parent-dependent
inputs and side effects evaluated at their original positions. Do not reimplement their logic.
Use checklist_answers for the COMPLETE original parser checklist, citing any actual assembled
production source. The trusted checker retains the complete original XML/configuration and
compares the assembled whole-format API, never individual subtree claims, before publication.
'''


def convert_partitioned_format(conn, config, profile, plan, group, original, instruction, output,
                               factory, model_call, files, dependencies, *, units, boundaries):
    """Bound subdivision work and leave indivisible source/checklist overflow explicitly incomplete."""
    from runtime.component_conversion.validation import ComponentCandidateValidator
    tree = original['configured_format']['effective_configuration']
    children, generated, pins, events = {}, {}, list(dependencies), []
    folder = Path(output) / 'format-parts' / group.group_id
    folder.mkdir(parents=True, exist_ok=True)
    report_path = folder / 'partition-report.json'
    report = dict(version='configured-subtree-v1', unit_id=original['configured_format']['unit_id'],
        original_configuration_hash=digest(original['configured_format']), parts=events,
        accepted_units=0, accepted_operations=0, status='partitioning')
    visited = set()

    def persist():
        temporary = report_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2), encoding='utf-8')
        temporary.replace(report_path)

    def convert(selector):
        if selector in visited or len(visited) >= 128 or len(selector) > 32:
            raise ValueError('Format partition attempt/depth limit reached; no unit accepted')
        visited.add(selector)
        if selector:
            from agents.behavior_conversion.component_generation import component_instruction
            from agents.behavior_conversion.native_instructions import java_compatibility_instruction
            part_instruction = component_instruction(original.get('known_dependencies', [])) + PART_INSTRUCTION
            part_instruction += '\n' + java_compatibility_instruction(profile.java_version)
        else:
            part_instruction = instruction + ROOT_INSTRUCTION
        request = partition_request(original, tree, selector, children)
        if not fits_partition(request, part_instruction, profile):
            cuts = splittable_children(tree, selector)
            if not cuts:
                raise ValueError('Indivisible oversized format subtree at ' + str(list(selector)) +
                    '; source/checklist/reference evidence cannot be truncated')
            before = len(json.dumps(subtree_at(tree, selector)))
            for cut in cuts:
                if len(json.dumps(subtree_at(tree, cut))) >= before:
                    raise ValueError('Format subdivision made no structural progress')
                convert(cut)
            request = partition_request(original, tree, selector, children)
            if not fits_partition(request, part_instruction, profile):
                raise ValueError('Indivisible oversized composition after child extraction at ' + str(list(selector)))
        event = dict(selector=list(selector), identity=request['group_id'], status='generating',
            configuration_hash=request['format_partition']['configuration_hash'])
        events.append(event)
        persist()
        dependency_files = {**files, **generated}
        if selector:
            validator = SubtreeCandidateValidator(conn, config, profile, request, folder, factory, dependency_files, pins)
            schema = NativeComponentBundle
        else:
            complete_request = dict(original,format_partition_records=[children[path]['result_revision'] for path in sorted(children)])
            validator = ComponentCandidateValidator(conn, config, profile, plan, group, complete_request, output,
                factory, dependency_files, pins, units=units, boundaries=boundaries, owned_dependency_sources=tuple(generated))
            schema = NativeFormatComponentBundle
        with partition_task(request['group_id'], request, original):
            generate(conn, config, profile, 'component_generation', request['group_id'], part_instruction,
                request, schema, validator=validator, model_call=model_call,
                label='Configured format subtree: ' + str(list(selector)))
        if selector:
            for name, content in validator.generated_files.items():
                if name in dependency_files:
                    raise ValueError('Extracted subtree overwrote a prerequisite')
                generated[name] = content
            children[selector] = validator.descriptor
            pins.extend(validator.descriptor['dependencies'])
            event.update(status='component_validated', contract_revision=validator.descriptor['contract_revision'],
                result_revision=validator.descriptor['result_revision'])
        else:
            event['status'] = 'whole_format_compared'
        persist()

    try:
        convert(())
        report['status'] = 'whole_format_compared'
    except Exception as exc:
        report.update(status='incomplete', reason=str(exc))
        raise
    finally:
        persist()
    return dict(status='component_validated', members=group.members, reused=False,
        validation_scope='build_and_tests', partition_report=str(report_path), subtree_components=len(children))
