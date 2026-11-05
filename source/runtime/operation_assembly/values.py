"""Prepare editable operation values during assembly, independently of human approval."""
import json
from pathlib import Path
import yaml

from runtime.service_generation.deployment_configuration import load_deployment,write_deployment
from runtime.service_generation.composer_database_settings import discover_database_settings
from runtime.workspace_paths import run_report_path,write_run_report


def _fill_blanks(path, after, database, fields):
    """Patch only existing empty scalars; preserve comments, formatting and unrelated values."""
    text=path.read_bytes().decode('utf-8');tree=yaml.compose(text);changes=[]
    for field in fields:
        node=tree
        for key in ('databases',database,field):
            if not isinstance(node,yaml.MappingNode):break
            node=next((v for k,v in node.value if k.value==key),None)
        if not isinstance(node,yaml.ScalarNode):return False
        value=getattr(after.databases[database],field)
        changes.append((node.start_mark.index,node.end_mark.index,json.dumps(value,ensure_ascii=False)))
    for start,end,value in sorted(changes,reverse=True):text=text[:start]+value+text[end:]
    try:
        from runtime.service_generation.helm_values import deployment_from_values
        if deployment_from_values(yaml.safe_load(text))!=after:return False
    except (ValueError,yaml.YAMLError):return False
    path.write_bytes(text.encode('utf-8'))
    return True


def prepare_operation_values(conn, config, directory, record, *, profile=None, model_call=None, original_evidence=None):
    """Seed values before Gate 3, fill supported blanks and report unresolved runtime inputs."""
    project=Path(record['project']);path=project/'values.yaml';existed=path.exists()
    from runtime.behavior_conversion.standalone_packaging import write_standalone_packaging
    write_standalone_packaging(project)
    connections=record.get('service_connections',[])
    identity=record['channel']+'/'+record['operation_id']
    if not connections and conn.execute("SELECT 1 FROM sqlite_master WHERE name='service_connection_evidence'").fetchone():
        connections=[json.loads(row[0]) for row in conn.execute(
            'SELECT record_json FROM service_connection_evidence WHERE run_id=? AND consumer=?',(config.run_id,identity))]
    item=dict(project=str(project),channel=record['channel'],operation_id=record['operation_id'],
        payload=dict(contract=record.get('contract',dict(service_api=record.get('service_api',{}))),service_connections=connections))
    spec=load_deployment(item,persist=False);result=dict(operation=identity,filled_fields=[],preserved_fields=[],issues=[],sources=[])
    if spec.operation.database:
        found=discover_database_settings(config.source_root,record['channel'],connections)
        result.update(issues=found['issues'],sources=found['sources'])
        database=spec.operation.database;updated=spec.model_copy(deep=True)
        for field in ('jdbcUrl','driverClass'):
            if getattr(spec.databases[database],field):result['preserved_fields'].append(field)
            elif found[field]:
                setattr(updated.databases[database],field,found[field]);result['filled_fields'].append(field)
        if existed and result['filled_fields']:
            if not _fill_blanks(path,updated,database,result['filled_fields']):
                result['issues'].append('Edited YAML could not be updated without changing other values; existing content was preserved.')
                result['filled_fields']=[]
        spec=updated
    if not existed:write_deployment(path,spec)
    generation_issue=None
    if profile is not None:
        from runtime.fixture_demo.scenario_evidence import original_operation_evidence
        from runtime.fixture_demo.scenario_generation import generate_operation_scenarios
        try:
            original=original_operation_evidence(conn,config,identity,record)
            if original_evidence:
                indexed={source['identity']:source for source in original['sources']}
                for source in original_evidence.get('sources',[]):
                    previous=indexed.get(source['identity'])
                    if previous is not None and previous['content']!=source['content']:
                        raise ValueError('Assembly supplied conflicting original source evidence: '+source['identity'])
                    if previous is None:original['sources'].append(source);indexed[source['identity']]=source
                original['configuration'].update(original_evidence.get('configuration',{}))
            generated=generate_operation_scenarios(project,identity,profile,original=original,model_call=model_call)
            result['scenario_generation']=generated
            if generated['status']!='prepared':generation_issue='Whole-operation scenario preparation: '+'; '.join(generated['issues'])
        except (ValueError,OSError) as error:
            generation_issue='Whole-operation source evidence: '+str(error)
    from runtime.fixture_demo.preparation import prepare_operation_demo
    demo=prepare_operation_demo(project,config.output_root,identity,generation_issue=generation_issue)
    result['demo']=dict(status=demo['status'],issues=demo['issues'])
    report_path=run_report_path(directory,'operation_values_results.json')
    results=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    results[identity]=result
    write_run_report(directory,'operation_values_results.json',json.dumps(results,indent=2))
    return result
