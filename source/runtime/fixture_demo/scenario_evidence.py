"""Collect exact saved source/fixture evidence for whole-operation preparation."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree
from runtime.fixture_jdbc_tools.releases import digest
from runtime.test_assets.store import load


def original_operation_evidence(conn,config,identity,record):
    """Read only this operation's recorded sources, verifying original byte hashes."""
    result=dict(sources=[],configuration={})
    if conn is None:return result
    exists=lambda table:conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone()
    source_root=Path(config.source_root).resolve();seen={}
    configurations=set()
    def add_configuration(definition_id):
        if not definition_id or definition_id in configurations or not exists('scoped_source_definitions'):return
        row=conn.execute('SELECT record_json FROM scoped_source_definitions WHERE run_id=? AND definition_id=?',
            (config.run_id,definition_id)).fetchone()
        if not row:return
        definition=json.loads(row[0])
        if definition['kind'] not in ('format','operation','opstep','step'):return
        from tools.conversion_tools.scoped_closure.source_evidence import SourceEvidence
        reader=SourceEvidence(source_root)
        node=reader.xml(SimpleNamespace(evidence=definition,entity_id=definition['entity_id']))
        content=ElementTree.tostring(node,encoding='unicode')
        seen[definition_id]=dict(identity=definition_id,content=content,
            content_hash=hashlib.sha256(content.encode('utf-8')).hexdigest())
        configurations.add(definition_id)
    def add(origin):
        if not origin.get('source_file'):return
        path=Path(origin['source_file']).resolve()
        if not path.is_relative_to(source_root):raise ValueError('Original operation evidence escaped source root')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=origin['source_hash']:raise ValueError('Original operation source changed: '+path.name)
        key=origin.get('definition_id') or origin.get('fqcn') or str(path)
        item=dict(identity=key,content_hash=origin['source_hash'],content=raw.decode('utf-8'),source_path=str(path))
        if key in seen and seen[key]!=item:raise ValueError('Conflicting original source evidence')
        seen[key]=item
        for child in origin.get('supporting_sources',[]):add(child)
    if exists('conversion_component_plans'):
        row=conn.execute('SELECT plan_json FROM conversion_component_plans WHERE run_id=?',(config.run_id,)).fetchone()
        if row:
            for key,component in json.loads(row[0])['components'].items():
                if identity in component.get('operations',[]):
                    add(component.get('provenance',{}))
                    add_configuration(component.get('provenance',{}).get('source_definition_id'))
                    if component.get('configuration'):result['configuration'][key]=component['configuration']
    workflow=record.get('closure',{}).get('scoped_workflow')
    if workflow:
        from tools.conversion_tools.scoped_closure.source_evidence import SourceEvidence
        node=SourceEvidence(source_root).xml(SimpleNamespace(evidence=workflow['operation_source'],
            entity_id=workflow['operation_attributes']['id']))
        result['configuration']['operation_xml']=ElementTree.tostring(node,encoding='unicode')
        result['configuration']['workflow_requirements']=workflow.get('requirements',{})
    result['sources']=list(seen.values())
    return result


def collect_scenario_evidence(project,identity,original=None):
    """Verify immutable banks and include full saved code without truncating evidence."""
    project=Path(project).resolve();banks={};locations={}
    for manifest in sorted(project.joinpath('src/test/resources/shared-test-assets').rglob('manifest.json')):
        raw=json.loads(manifest.read_text(encoding='utf-8'));expected=digest(raw)
        _,documents=load(manifest.parent,expected)
        if expected not in banks:
            banks[expected]=dict(boundary_identity=raw['boundary_identity'],fixtures=documents['fixtures.json'],
                comparison_scenarios=documents['comparison-scenarios.json'])
            locations[expected]=dict(asset_root=manifest.parent.relative_to(project).as_posix(),manifest_hash=expected)
    if not banks:raise ValueError('No saved shared fixture banks are available for whole-operation preparation')
    native=[dict(identity='native:'+p.relative_to(project).as_posix(),content=p.read_bytes().decode('utf-8'),
                 content_hash=hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(project.joinpath('src/main').rglob('*')) if p.is_file() and p.suffix in ('.java','.xml','.json','.properties')]
    if not native:raise ValueError('Saved operation Java is missing')
    original=original or dict(sources=[],configuration={})
    for source in original.get('sources',[]):
        expected=source.get('content_hash')
        if expected and hashlib.sha256(source['content'].encode('utf-8')).hexdigest()!=expected:
            raise ValueError('Original source content differs from its saved byte hash')
        if source.get('source_path') and hashlib.sha256(Path(source['source_path']).read_bytes()).hexdigest()!=expected:
            raise ValueError('Original source changed during preparation')
    return dict(operation=identity,native_sources=native,original_evidence=original,saved_banks=banks),locations


def read_saved_operation(database,identity,source_root,run_id=None):
    """Open a saved conversion read-only; this command never resumes or mutates it."""
    import sqlite3
    connection=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        sql="SELECT run_id,data_json FROM behavior_snapshots WHERE category='operation' AND identity=?"
        args=[identity]
        if run_id is not None:sql+=' AND run_id=?';args.append(run_id)
        rows=connection.execute(sql,args).fetchall()
        if len(rows)!=1:raise ValueError('Select one saved operation and run for scenario preparation')
        record=json.loads(rows[0][1]);config=SimpleNamespace(run_id=rows[0][0],source_root=source_root)
        return original_operation_evidence(connection,config,identity,record)
    finally:connection.close()
