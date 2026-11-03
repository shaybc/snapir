"""Scope explicit format-composition upgrades without replacing validated basic Java."""
import json
from contextlib import contextmanager
from pathlib import Path
from tools.behavior_verification.experimental_checkpoint import file_hash


def selected_composition(payload, labels):
    """Only complete configured formats can receive composition regeneration permission."""
    configured = payload.get('configured_format') or {}
    components = payload.get('components') or {}
    return bool(configured.get('logical_id') in labels and components and all(
        node['kind']=='format_composition' for node in components.values()))


def guarded_model_call(call, allowed):
    """Refuse implementation requests outside the explicit composition upgrade scope."""
    def execute(prompt, encoded):
        if not allowed and json.loads(encoded).get('schema',{}).get('title')=='NativeImplementation':
            raise ValueError('Implementation generation is outside the authorized format-composition scope')
        return call(prompt,encoded)
    return execute


def retained_java(conn, run_id, labels):
    """Record exact owned Java bytes of validated components outside the selected formats."""
    plan = json.loads(conn.execute('SELECT plan_json FROM conversion_component_plans WHERE run_id=?',(run_id,)).fetchone()[0])
    groups = {group['group_id']:group for group in plan['groups']}
    result = {}
    for row in conn.execute("SELECT r.group_id,r.record_json FROM conversion_component_records r JOIN conversion_component_heads h ON h.run_id=r.run_id AND h.group_id=r.group_id AND h.result_revision=r.revision WHERE r.run_id=? AND r.category='result' AND h.status='component_validated'",(run_id,)):
        if any(plan['components'][member]['label'] in labels for member in groups[row[0]]['members']):
            continue
        for component in json.loads(row[1])['results'].values():
            for name in component['files']:
                if name.startswith('src/main/java/'):
                    path = Path(component['artifact_root'])/name
                    result[str(path)] = file_hash(path)
    return result


@contextmanager
def composition_upgrade_requests(labels, baselines, feedback=None, *, automatic=False):
    """Create distinct audited upgrade tasks while retaining canonical scope and validators."""
    from runtime.component_conversion import runner
    original = runner.build_component_request
    def build(*args,**kwargs):
        request,instruction = original(*args,**kwargs)
        if selected_composition(request,labels):
            label = request['configured_format']['logical_id']
            request['authorized_composition_upgrade'] = dict(version='automatic-chain-replay-v1' if automatic else 'missing-format-chains-v1',
                saved_implementation_hash=baselines[label],reason='Generate missing configured chain classes and wire their calls')
            if automatic:request['authorized_composition_upgrade'].update(manual_overrides_allowed=False,clean_generation=True)
            if (feedback or {}).get(label):
                request['correction_feedback'] = feedback[label]
            instruction += '\nThis is an authorized replacement of an older frozen format composition. Generate all required format_chains classes and mapper invocations. Reuse the exact accepted prerequisite APIs without changing basic formats or decorators. Do not return internal-call metadata. All remaining enabled validators remain required.'
        return request,instruction
    runner.build_component_request = build
    try:
        yield
    finally:
        runner.build_component_request = original


def convert_selected_compositions(conn, config, profile, directory, labels, previous_outcome, *, saved_components=None):
    """Run canonical conversion only for selected roots and revalidate their prerequisites."""
    from runtime.java_toolchain import java_scope
    from runtime.managed_projects import create_build_context
    from runtime.component_conversion.scope import component_execution
    from runtime.component_conversion.runner import _convert_group
    from runtime.component_conversion.steps import default_step_mappings
    from runtime.workspace_paths import run_report_path, write_run_report
    from tools.behavior_verification.boundaries import build_boundary_report
    from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow
    from tools.conversion_tools.component_identity import checked_plan
    from tools.source_discovery_tools.classpath import discover_java_classpath
    from tools.state_store_tools.runs import update_run_status
    from tools.state_store_tools.component_configuration import configuration_group,verify_configuration,bind_configuration
    from runtime.component_conversion.saved_experiment import candidate_key
    path = run_report_path(directory,'component-generation.json')
    report = json.loads(path.read_text(encoding='utf-8'))
    result = {}
    with java_scope(profile):
        classpath = discover_java_classpath(config.source_root,profile.classpath_jars,profile.eclipse_classpath_variables)
        preparation = prepare_scoped_workflow(conn,config,profile,classpath_index=classpath)
        plan = checked_plan(preparation['component_plan'])
        if saved_components is not None:
            report['groups']={key:value for key,value in report['groups'].items() if key in {group.group_id for group in plan.groups}}
            report['total_groups']=len(plan.groups)
        targets = ([group for group in plan.groups if candidate_key({key:plan.components[key] for key in group.members}) in saved_components]
            if saved_components is not None else [group for group in plan.groups if any(plan.components[key].kind=='format_composition' and plan.components[key].label in labels for key in group.members)])
        if saved_components is None and len(targets)!=len(labels) or saved_components is not None and len(targets)!=len(saved_components):
            raise ValueError('Selected format composition roots are missing or ambiguous')
        old_blockers = {item['component_group']:item['detail'] for item in previous_outcome.get('blockers',[]) if 'component_group' in item}
        for group in plan.groups:
            if saved_components is not None and group in targets:
                from tools.state_store_tools.component_records import head
                current=head(conn,config.run_id,group.group_id)
                report['groups'][group.group_id]=dict(status='component_validated' if current and current['status']=='component_validated' else 'deferred',
                    members=group.members,reason='Current dependency-policy revalidation required')
            if saved_components is not None and configuration_group(plan,group):
                report['groups'][group.group_id]=dict(status='deferred',members=group.members,reason='Waiting for current native prerequisite revalidation')
            elif saved_components is not None and group not in targets:
                report['groups'][group.group_id]=dict(status='deferred',members=group.members,reason='No saved Java candidate; generation is disabled for dependency revalidation')
            if group.group_id not in report['groups']:
                if configuration_group(plan,group):
                    try:
                        verify_configuration(conn,config.run_id,plan,group)
                        report['groups'][group.group_id] = dict(status='configuration_bound',members=group.members)
                    except ValueError as error:
                        report['groups'][group.group_id] = dict(status='incomplete',members=group.members,reason=str(error))
                    continue
                report['groups'][group.group_id] = dict(status='incomplete' if group.group_id in old_blockers else 'deferred',
                    members=group.members,reason=old_blockers.get(group.group_id,'Outside selected format-composition upgrade scope'))
        if saved_components is not None:
            report['component_validated']=sum(len(item['members']) for item in report['groups'].values() if item['status']=='component_validated')
            report['reused_components']=0
            report['format_chain_status']='not_reached'
        boundaries = build_boundary_report(preparation,mappings=default_step_mappings(plan),collect_checklists=False)
        units = {unit['unit_id']:unit for item in preparation['operations'].values() for unit in item['units']}
        update_run_status(conn,config.run_id,'in_progress','conversion_components_upgrading')
        with component_execution(conn,config,profile,classpath,preparation,include_steps=True,include_formats=True):
            for group in (plan.groups if saved_components is not None else targets):
                if saved_components is not None and configuration_group(plan,group):
                    try:
                        bind_configuration(conn,config.run_id,plan,group,profile)
                        report['groups'][group.group_id]=dict(status='configuration_bound',members=group.members)
                    except ValueError as error:
                        report['groups'][group.group_id]=dict(status='incomplete',members=group.members,reason=str(error))
                    write_run_report(directory,'component-generation.json',json.dumps(report,indent=2))
                    continue
                if group not in targets:continue
                report['groups'][group.group_id] = dict(status='running',members=group.members)
                if any(plan.components[key].kind=='format_composition' for key in group.members):report['format_chain_status']='running'
                write_run_report(directory,'component-generation.json',json.dumps(report,indent=2))
                try:
                    value = _convert_group(conn,config,profile,plan,group,boundaries,Path(config.output_root)/'components',create_build_context,None,units=units)
                except (ValueError,OSError) as error:
                    from runtime.model_execution.error_details import sanitize_diagnostic
                    value = dict(status='incomplete',members=group.members,reason=sanitize_diagnostic(str(error)))
                report['groups'][group.group_id] = value
                result[plan.components[group.members[0]].label] = value
                report['component_validated'] = sum(len(item['members']) for item in report['groups'].values() if item['status']=='component_validated')
                report['reused_components'] = sum(len(item['members']) for item in report['groups'].values() if item.get('reused'))
                conn.commit()
                write_run_report(directory,'component-generation.json',json.dumps(report,indent=2))
    report['selected_format_chain_status']='validated' if all(item['status']=='component_validated' for item in result.values()) else 'blocked'
    format_groups=[group for group in plan.groups if any(plan.components[key].kind=='format_composition' for key in group.members)]
    report['format_chain_status']='validated' if all(report['groups'][group.group_id]['status']=='component_validated' for group in format_groups) else 'blocked'
    write_run_report(directory,'component-generation.json',json.dumps(report,indent=2))
    update_run_status(conn,config.run_id,'blocked','conversion_components_incomplete')
    return result


def automatic_java_provenance(conn, run_id, groups):
    """Confirm accepted automatic Java bytes are exactly a retained model response."""
    from models.native_implementation import NativeImplementation
    from runtime.managed_conversion_response import _remove_response_fence
    from runtime.behavior_conversion.response_json import clean_structural_escapes
    from tools.component_inventory_tools.identity import stable_id
    result={}
    for identity,entry in groups.items():
        revision=entry.get('new_task_revision')
        row=conn.execute("SELECT artifact_json FROM staged_conversion_tasks WHERE run_id=? AND identity=? AND revision=? AND stage='implementation'",(run_id,identity,revision)).fetchone()
        if not row or not row[0]:continue
        production=NativeImplementation.model_validate_json(row[0]);digest=stable_id(production.model_dump(mode='json'))
        responses=conn.execute("SELECT response FROM staged_conversion_attempts WHERE run_id=? AND identity=? AND revision=? AND stage='implementation' AND response IS NOT NULL",(run_id,identity,revision)).fetchall()
        matched=False
        for response in responses:
            try:matched=matched or stable_id(NativeImplementation.model_validate_json(clean_structural_escapes(_remove_response_fence(response[0]))).model_dump(mode='json'))==digest
            except ValueError:pass
        result[identity]=dict(implementation_hash=digest,exact_model_response=matched,manual_overrides_used=False)
    return result
