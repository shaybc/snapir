"""Convert eligible Java dependency groups without composing or accepting configured units."""
import json
import logging
from pathlib import Path
from models.native_component_bundle import NativeComponentBundle
from runtime.behavior_conversion.generation import generate
from runtime.component_conversion.scope import component_execution, require_component_task
from runtime.component_conversion.requests import basic_group, build_component_request, prerequisite_sources
from runtime.component_conversion.steps import step_group, default_step_mappings
from runtime.component_conversion.formats import format_group,native_format_prerequisites
from tools.state_store_tools.component_configuration import configuration_group,bind_configuration,verify_configuration
from runtime.component_conversion.validation import ComponentCandidateValidator, revalidate_components
from tools.conversion_tools.component_identity import checked_plan, external_group
from tools.state_store_tools import component_records as records
from tools.state_store_tools.conversion_components import register_component_plan, reuse_component_result
from tools.behavior_verification.boundaries import build_boundary_report
from runtime.workspace_paths import write_run_report


def convert_basic_components(conn, config, profile, directory, preparation, classpath, *, model_call=None, context_factory=None, include_steps=False, include_formats=False):
    """Run CF3 after the scoped plan/gate checks; component progress never accepts units."""
    from runtime.managed_projects import create_build_context
    from tools.state_store_tools.behavior_units import initialize
    factory = context_factory or create_build_context
    initialize(conn)
    plan = checked_plan(preparation['component_plan'])
    register_component_plan(conn, config.run_id, plan, profile)
    output = Path(config.output_root).resolve() / 'components'
    if not output.resolve().is_relative_to(Path(config.output_root).resolve()):
        raise ValueError('Component output is outside the run root')
    boundaries = build_boundary_report(preparation, mappings=default_step_mappings(plan))
    units = {unit['unit_id']: unit for item in preparation['operations'].values() for unit in item.get('units', [])}
    report = dict(capability='component-first-cf6' if include_formats else 'component-first-cf4' if include_steps else 'component-first-cf3', configured_units=len(plan.unit_roots), accepted_units=0,
        accepted_operations=0, behavioral_acceptance=False, groups={}, component_validated=0, reused_components=0)
    with component_execution(conn, config, profile, classpath, preparation, include_steps=include_steps,include_formats=include_formats):
        try:
            for position, group in enumerate(plan.groups, 1):
                if external_group(plan, group):
                    report['groups'][group.group_id] = dict(status='external_policy', members=group.members)
                    continue
                if include_formats and configuration_group(plan,group):
                    try:
                        bind_configuration(conn,config.run_id,plan,group,profile)
                        report['groups'][group.group_id]=dict(status='configuration_bound',members=group.members)
                    except ValueError as exc:
                        report['groups'][group.group_id]=dict(status='incomplete',members=group.members,reason=str(exc))
                    continue
                if not (basic_group(plan, group) or include_steps and step_group(plan, group) or include_formats and format_group(plan,group)):
                    report['groups'][group.group_id] = dict(status='deferred', members=group.members,
                        reason='Format wrappers and composition remain later milestones')
                    continue
                if group.wave is None:
                    report['groups'][group.group_id] = dict(status='incomplete', members=group.members, reason='Unresolved prerequisite evidence')
                    continue
                logging.getLogger(__name__).info('Basic component group %s/%s: %s', position, len(plan.groups), group.members)
                try:
                    result = _convert_group(conn, config, profile, plan, group, boundaries, output, factory, model_call, units=units)
                    report['groups'][group.group_id] = result
                    report['component_validated'] += len(group.members)
                    if result['reused']: report['reused_components'] += len(group.members)
                except (ValueError, OSError) as exc:
                    report['groups'][group.group_id] = dict(status='incomplete', members=group.members, reason=str(exc))
                    logging.getLogger(__name__).warning('Basic component group incomplete: %s: %s', group.group_id, exc)
                conn.commit()
                write_run_report(directory, 'component-generation.json', json.dumps(report, indent=2))
        except Exception as exc:
            report['fatal_error'] = str(exc)
            from tools.state_store_tools.runs import update_run_status
            update_run_status(conn, config.run_id, 'failed', 'conversion_components_failed')
            raise
        finally:
            write_run_report(directory, 'component-generation.json', json.dumps(report, indent=2))
    from tools.state_store_tools.runs import update_run_status
    update_run_status(conn, config.run_id, 'blocked', 'conversion_components_incomplete' if any(
        item['status'] == 'incomplete' for item in report['groups'].values()) else 'conversion_components_ready_for_composition')
    return Path(directory)


def _convert_group(conn, config, profile, plan, group, boundaries, output, factory, model_call, *, units=None):
    require_component_task(conn, config, profile, group.group_id)
    validator = revalidate_components(profile, factory,config=config,units=units,boundaries=boundaries,conn=conn)
    obligations, _ = build_component_request(plan, group, boundaries, [], profile, check_budget=False, units=units)
    from tools.state_store_tools.behavior_units import snapshot
    feedback = snapshot(conn,config.run_id,'component_unit_feedback',group.group_id)
    feedback = json.loads(feedback['data_json']) if feedback else None
    def validate_cached(contracts, results):
        for key, result in results.items():
            if key not in group.members: continue
            saved = json.loads((Path(result.artifact_root) / result.validation_report).read_text(encoding='utf-8'))
            changed = [name for name in ('parser_checklist', 'source_entry_points', 'analysis_tool_hash', 'component_generation_policy')
                       if saved.get(name) != obligations[name]]
            if changed:
                raise ValueError('Component parser obligations or validation policy changed: '+', '.join(changed))
            if saved.get('configured_unit') != obligations.get('configured_unit'):
                raise ValueError('Configured step receipt no longer matches this occurrence')
            if saved.get('configured_format')!=obligations.get('configured_format'):
                raise ValueError('Configured format receipt no longer matches this direction/structure')
            if saved.get('configured_format') is not None and 'format_partition_records' not in saved:
                raise ValueError('Format receipt needs current transitive partition metadata')
            if saved.get('whole_unit_feedback') != feedback:
                raise ValueError('Component needs the current whole-unit correction')
            if saved.get('requirements') is not None and saved['requirements'] != obligations['requirements']:
                raise ValueError('Component whole-unit requirements changed')
        return validator(contracts, results)
    try:
        reused = reuse_component_result(conn, config.run_id, plan, group.members[0], profile, output, validator=validate_cached)
    except (ValueError, OSError) as exc:
        logging.getLogger(__name__).info('Component reuse requires correction for %s: %s',group.group_id,exc)
        reused = None
    if reused is not None:
        require_component_task(conn, config, profile, group.group_id)
        return dict(status='component_validated', members=group.members, reused=True, validation_scope='build_and_tests')
    direct_groups=native_format_prerequisites(plan,group)
    direct, results, pending, seen = [], {}, list(group.dependencies), set()
    groups = {item.group_id: item for item in plan.groups}
    while pending:
        key = pending.pop()
        if key in seen: continue
        seen.add(key)
        dependency = groups[key]
        if configuration_group(plan,dependency):
            verify_configuration(conn,config.run_id,plan,dependency)
            pending.extend(dependency.dependencies)
            continue
        if external_group(plan, dependency):
            if key in direct_groups:
                direct.append(dict(group_id=key, policy=[plan.components[member].model_dump(mode='json') for member in dependency.members]))
            continue
        result = reuse_component_result(conn, config.run_id, plan, dependency.members[0], profile, output, validator=validator)
        if result is None: raise ValueError('Required native prerequisite is not component_validated: ' + key)
        head = records.head(conn, config.run_id, key)
        contracts = records.read_record(conn, config.run_id, key, 'contract', head['contract_revision'])['contracts']
        saved = records.read_record(conn, config.run_id, key, 'result', head['result_revision'])['results']
        from models.native_component_result import NativeComponentResult
        parsed = {member: NativeComponentResult.model_validate(value) for member, value in saved.items()}
        results.update(parsed)
        if key in direct_groups:
            sources, pins = prerequisite_sources(parsed)
            direct.append(dict(group_id=key, contract_revision=head['contract_revision'], result_revision=head['result_revision'],
                contracts=contracts, evidence_ids=sorted({item for contract in contracts.values() for item in contract['evidence_ids']}),
                sources=sources, dependencies=pins))
        pending.extend(dependency.dependencies)
    dependency_files, dependencies = prerequisite_sources(results)
    request, instruction = build_component_request(plan, group, boundaries, sorted(direct, key=lambda item:item['group_id']), profile, check_budget=False, units=units)
    if feedback is not None:
        request['whole_unit_feedback'] = feedback
        instruction += '\nCorrect whole_unit_feedback from the assembled unit checks. Preserve frozen prerequisite APIs; use the exact failing inputs and source behavior without weakening verification.'
    if request['kind']=='format_composition':
        from runtime.component_conversion.partition_requests import fits_partition
        if not fits_partition(request,instruction,profile):
            from runtime.component_conversion.partition_runner import convert_partitioned_format
            return convert_partitioned_format(conn,config,profile,plan,group,request,instruction,output,
                factory,model_call,dependency_files,dependencies,units=units,boundaries=boundaries)
    candidate = ComponentCandidateValidator(conn, config, profile, plan, group, request, output, factory, dependency_files, dependencies,
        units=units,boundaries=boundaries)
    schema=NativeComponentBundle
    if request['kind']=='format_composition':
        from models.native_format_component_bundle import NativeFormatComponentBundle
        schema=NativeFormatComponentBundle
    generate(conn, config, profile, 'component_generation', group.group_id, instruction, request,
             schema, validator=candidate, model_call=model_call, label='Basic native group: ' + ', '.join(plan.components[key].label for key in group.members))
    return dict(status='component_validated', members=group.members, reused=False, validation_scope='build_and_tests')
