"""Register and reuse revision-bound component progress without accepting configured units."""
import json
from copy import deepcopy
from models.native_component_contract import NativeComponentContract
from models.native_component_result import NativeComponentResult
from tools.conversion_tools.component_identity import checked_plan,component_target,input_revision,component_group,external_group
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.behavior_verification.component_artifacts import verify_component_artifacts,verify_original_sources
from tools.state_store_tools import component_records as records


def register_component_plan(conn,run_id,value,profile):
    """Persist passive CF1 metadata and invalidate changed/removed groups and their consumers."""
    plan=checked_plan(value);target=component_target(profile)
    desired={group.group_id:input_revision(plan,group,target) for group in plan.groups}
    with records.transaction(conn):
        old={row['group_id']:dict(row) for row in conn.execute('SELECT * FROM conversion_component_heads WHERE run_id=?',(run_id,))}
        changed={key for key,head in old.items() if key not in desired or head['input_revision']!=desired[key]}
        records.invalidate(conn,run_id,changed)
        conn.execute('DELETE FROM conversion_component_links WHERE run_id=?',(run_id,))
        for group in plan.groups:
            conn.executemany('INSERT INTO conversion_component_links VALUES (?,?,?)',
                [(run_id,group.group_id,dependency) for dependency in group.dependencies])
            if group.group_id not in old or group.group_id in changed:
                conn.execute('INSERT OR REPLACE INTO conversion_component_heads VALUES (?,?,?,?,?,?)',
                    (run_id,group.group_id,desired[group.group_id],'planned',None,None))
        conn.execute('INSERT OR REPLACE INTO conversion_component_plans VALUES (?,?,?,?)',
            (run_id,plan.fingerprint,plan.model_dump_json(),json.dumps(target,sort_keys=True)))
    return plan


def register_component_contracts(conn,run_id,value,group_id,contracts,profile):
    """Freeze all cycle-member interfaces atomically; new revisions invalidate existing consumers."""
    plan=register_component_plan(conn,run_id,value,profile)
    group=_group(plan,group_id)
    parsed={key:NativeComponentContract.model_validate(contract) for key,contract in contracts.items()}
    _members(group,parsed)
    for key,contract in parsed.items():
        node=plan.components[key]
        if contract.component_id!=key or set(contract.dependencies)!=set(node.dependencies):
            raise ValueError('Component contract dependency/identity does not match the plan')
        own=node.configuration.get('definition_id') or node.provenance.get('definition_id') or node.provenance.get('source_definition_id')
        if not own or own not in contract.evidence_ids:
            raise ValueError('Component contract must cite its original source/configuration evidence')
    verify_original_sources(plan,group)
    with records.transaction(conn):
        current=records.head(conn,run_id,group_id)
        data=dict(group_id=group_id,input_revision=current['input_revision'],
            contracts={key:contract.model_dump(mode='json') for key,contract in sorted(parsed.items())},
            dependencies=_dependencies(conn,run_id,plan,group,'contract'))
        revision=digest(data)
        if current['contract_revision']!=revision or current['status']=='stale':
            records.invalidate(conn,run_id,[group_id])
            records.write_record(conn,run_id,group_id,'contract',revision,data)
            conn.execute("UPDATE conversion_component_heads SET status='contract_registered',contract_revision=?,result_revision=NULL WHERE run_id=? AND group_id=?",
                         (revision,run_id,group_id))
        else: records.read_record(conn,run_id,group_id,'contract',revision)
    return dict(group_id=group_id,input_revision=data['input_revision'],contract_revision=revision)


def save_component_results(conn,run_id,value,group_id,results,profile,output_root,*,validator):
    """Save component_validated only after artifact checks and a trusted caller's validation."""
    plan=register_component_plan(conn,run_id,value,profile)
    group=_group(plan,group_id)
    parsed={key:NativeComponentResult.model_validate(result) for key,result in results.items()}
    _members(group,parsed)
    current=records.head(conn,run_id,group_id)
    if not current['contract_revision']: raise ValueError('Component interfaces must be registered before results')
    contract_data=records.read_record(conn,run_id,group_id,'contract',current['contract_revision'])
    contracts=_contracts(contract_data)
    if contract_data['input_revision']!=current['input_revision'] or contract_data['dependencies']!=_dependencies(conn,run_id,plan,group,'contract'):
        raise ValueError('Component contract has stale prerequisites')
    dependency_results=_dependencies(conn,run_id,plan,group,'result')
    groups={item.group_id:item for item in plan.groups}
    for dependency in group.dependencies:
        if not external_group(plan,groups[dependency]): _verify_results(conn,run_id,plan,dependency,profile,output_root,validator)
    for key,result in parsed.items():
        if result.component_id!=key or result.contract_revision!=current['contract_revision'] or result.input_revision!=current['input_revision']:
            raise ValueError('Component result does not match current source/configuration/contract')
    _validate_group(plan,group,contracts,parsed,profile,output_root,validator)
    data=dict(group_id=group_id,input_revision=current['input_revision'],contract_revision=current['contract_revision'],
        dependencies=dependency_results,results={key:result.model_dump(mode='json') for key,result in sorted(parsed.items())})
    revision=digest(data)
    with records.transaction(conn):
        latest=records.head(conn,run_id,group_id)
        if (latest['input_revision'],latest['contract_revision'])!=(current['input_revision'],current['contract_revision']) or dependency_results!=_dependencies(conn,run_id,plan,group,'result'):
            raise ValueError('Component prerequisites changed during validation')
        if latest['result_revision']!=revision: records.invalidate(conn,run_id,records.consumers(conn,run_id,group_id))
        records.write_record(conn,run_id,group_id,'result',revision,data)
        conn.execute("UPDATE conversion_component_heads SET status='component_validated',result_revision=? WHERE run_id=? AND group_id=?",
                     (revision,run_id,group_id))
    return revision


def reuse_component_result(conn,run_id,value,component_id,profile,output_root,*,validator):
    """Revalidate saved files, reports and transitive prerequisites; never call a model."""
    plan=register_component_plan(conn,run_id,value,profile)
    group=component_group(plan,component_id)
    if group is None: return None
    current=records.head(conn,run_id,group.group_id)
    if current['status']!='component_validated': return None
    try:
        results=_verify_results(conn,run_id,plan,group.group_id,profile,output_root,validator)
        return results[component_id]
    except (ValueError,OSError,KeyError,TypeError):
        with records.transaction(conn): records.invalidate(conn,run_id,[group.group_id])
        raise


def _group(plan,group_id):
    group=next((item for item in plan.groups if item.group_id==group_id),None)
    if group is None or group.wave is None: raise ValueError('Component group is missing or has unresolved prerequisites')
    if external_group(plan,group): raise ValueError('External policies are not native conversion results')
    from tools.state_store_tools.component_configuration import configuration_group
    if configuration_group(plan,group): raise ValueError('Format configuration is evidence, not a generated native result')
    return group


def _members(group,values):
    if set(values)!=set(group.members): raise ValueError('Supply every component in the coordinated group')


def _dependencies(conn,run_id,plan,group,category):
    result={}
    groups={item.group_id:item for item in plan.groups}
    for key in group.dependencies:
        current=records.head(conn,run_id,key)
        if current is None or current['status']=='stale': raise ValueError('Component prerequisite is stale or missing')
        if external_group(plan,groups[key]): result[key]='external:'+current['input_revision']
        else:
            revision=current[category+'_revision']
            from tools.state_store_tools.component_configuration import configuration_group
            expected='configuration_bound' if configuration_group(plan,groups[key]) else 'component_validated'
            if not revision or category=='result' and current['status']!=expected:
                raise ValueError('Component prerequisite lacks '+category+' evidence')
            result[key]=revision
    return result


def _contracts(record):
    return {key:NativeComponentContract.model_validate(value) for key,value in record['contracts'].items()}


def _validate_group(plan,group,contracts,results,profile,output_root,validator):
    if not callable(validator): raise ValueError('A trusted component validator is required')
    def check():
        verify_original_sources(plan,group)
        for key,result in results.items(): verify_component_artifacts(contracts[key],result,output_root,profile.allowed_ibm_classes)
    check()
    if validator(deepcopy(contracts),deepcopy(results)) is not True: raise ValueError('Component validator rejected the result')
    check()


def _verify_results(conn,run_id,plan,group_id,profile,output_root,validator):
    groups={item.group_id:item for item in plan.groups}
    pending,needed=[group_id],set()
    while pending:
        key=pending.pop()
        if key in needed: continue
        needed.add(key);pending.extend(groups[key].dependencies)
    primary=None
    for group in plan.groups:
        if group.group_id not in needed or external_group(plan,group): continue
        try:
            from tools.state_store_tools.component_configuration import configuration_group,verify_configuration
            results=verify_configuration(conn,run_id,plan,group) if configuration_group(plan,group) else _verified_group(conn,run_id,plan,group,profile,output_root,validator)
        except (ValueError,OSError,KeyError,TypeError):
            with records.transaction(conn): records.invalidate(conn,run_id,[group.group_id])
            raise
        if group.group_id==group_id: primary=results
    if primary is None: raise ValueError('Component result is unavailable')
    return primary


def _verified_group(conn,run_id,plan,group,profile,output_root,validator):
    """Validate one immutable result after its prerequisites; caller handles invalidation."""
    current=records.head(conn,run_id,group.group_id)
    if current['status']!='component_validated': raise ValueError('Component prerequisite is not validated')
    contracts=records.read_record(conn,run_id,group.group_id,'contract',current['contract_revision'])
    saved=records.read_record(conn,run_id,group.group_id,'result',current['result_revision'])
    if (saved['input_revision'],saved['contract_revision'])!=(current['input_revision'],current['contract_revision']):
        raise ValueError('Component result revision changed')
    if contracts['input_revision']!=current['input_revision'] or contracts['dependencies']!=_dependencies(conn,run_id,plan,group,'contract') or saved['dependencies']!=_dependencies(conn,run_id,plan,group,'result'):
        raise ValueError('Component dependency revision changed')
    results={key:NativeComponentResult.model_validate(value) for key,value in saved['results'].items()}
    _members(group,results)
    for key,result in results.items():
        if result.component_id!=key or result.input_revision!=current['input_revision'] or result.contract_revision!=current['contract_revision']:
            raise ValueError('Saved component result disagrees with current identity')
    _validate_group(plan,group,_contracts(contracts),results,profile,output_root,validator)
    latest=records.head(conn,run_id,group.group_id)
    if latest!=current: raise ValueError('Component revision changed during reuse validation')
    if contracts['dependencies']!=_dependencies(conn,run_id,plan,group,'contract') or saved['dependencies']!=_dependencies(conn,run_id,plan,group,'result'):
        raise ValueError('Component prerequisites changed during reuse validation')
    return results
