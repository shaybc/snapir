"""Copy a stopped checkpoint and verify immutable implementation provenance."""
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from models.native_implementation import NativeImplementation
from runtime.managed_conversion_response import _remove_response_fence
from runtime.behavior_conversion.response_json import clean_structural_escapes
from tools.component_inventory_tools.identity import stable_id


def file_hash(path):
    """Hash evidence without changing its bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_candidates(conn):
    """Select latest saved production and require exact model-response integrity."""
    saved = {}
    rows = conn.execute("SELECT identity,revision,artifact_json FROM staged_conversion_tasks WHERE stage='implementation' AND artifact_json IS NOT NULL ORDER BY updated_at").fetchall()
    for identity, revision, raw in rows:
        value = NativeImplementation.model_validate_json(raw)
        attempt = conn.execute("SELECT request_json,response FROM staged_conversion_attempts WHERE identity=? AND revision=? AND stage='implementation' AND response IS NOT NULL ORDER BY attempt DESC LIMIT 1",(identity,revision)).fetchone()
        if attempt is None:
            raise ValueError('Saved implementation has no response: '+identity)
        response = NativeImplementation.model_validate_json(clean_structural_escapes(_remove_response_fence(attempt[1])))
        digest = stable_id(value.model_dump(mode='json'))
        if stable_id(response.model_dump(mode='json')) != digest:
            raise ValueError('Saved implementation differs from model response: '+identity)
        request = json.loads(attempt[0])
        if not request.get('native_package'):
            raise ValueError('Saved implementation has no package provenance: '+identity)
        saved[identity] = (value, digest, request)
    return saved


def verify_saved_inputs(prior, current):
    """Allow the proven historical CRLF transport difference, never a source revision change."""
    old = {item['identity']:dict(item) for item in prior['sources']}
    new = {item['identity']:dict(item) for item in current['sources']}
    paths = {}
    for node in prior.get('components',{}).values():
        provenance = node['provenance']
        for evidence in [provenance,*provenance.get('supporting_sources',[])]:
            if evidence.get('definition_id') and evidence.get('source_file'):
                paths[evidence['definition_id']] = evidence['source_file']
    for identity in old:
        before = old[identity]
        if identity not in new:
            path = paths.get(identity)
            if not path or file_hash(path) != before['content_hash']:
                raise ValueError('Frozen candidate original supporting source changed: '+identity)
            continue
        after = new[identity]
        old_text, text = before.pop('content'), after.pop('content')
        if before['content_hash'] != after['content_hash']:
            raise ValueError('Frozen candidate source evidence changed: '+identity)
        if old_text != text:
            if hashlib.sha256(text.encode('utf-8')).hexdigest() != after['content_hash'] or old_text.replace('\r\n','\n') != text.replace('\r\n','\n'):
                raise ValueError('Frozen candidate source bytes changed: '+identity)
    for field in ('configured_unit','configured_format'):
        before = {key:value for key,value in (prior.get(field) or {}).items() if key not in {'fingerprint','unit_id'}}
        after = {key:value for key,value in (current.get(field) or {}).items() if key not in {'fingerprint','unit_id'}}
        if before != after:
            raise ValueError('Frozen candidate configuration changed: '+field)


def preflight_saved_inputs(conn, config, profile, saved):
    """Check every retained candidate against fresh preparation before any model call."""
    from runtime.java_toolchain import java_scope
    from runtime.component_conversion.saved_experiment import candidate_key
    from runtime.component_conversion.requests import build_component_request
    from runtime.component_conversion.steps import default_step_mappings
    from tools.behavior_verification.boundaries import build_boundary_report
    from tools.conversion_tools.scoped_workflow.preparation import prepare_scoped_workflow
    from tools.conversion_tools.component_identity import checked_plan
    by_origin = {candidate_key(item[2]['components']):item for item in saved.values()}
    checked = set()
    with java_scope(profile):
        preparation = prepare_scoped_workflow(conn,config,profile)
        plan = checked_plan(preparation['component_plan'])
        boundaries = build_boundary_report(preparation,mappings=default_step_mappings(plan),collect_checklists=False)
        (Path(config.output_root).parent/'experimental-preflight-boundaries.json').write_text(json.dumps(boundaries,indent=2),encoding='utf-8')
        units = {unit['unit_id']:unit for item in preparation['operations'].values() for unit in item['units']}
        for group in plan.groups:
            key = candidate_key({member:plan.components[member] for member in group.members})
            if key not in by_origin:
                continue
            request,_ = build_component_request(plan,group,boundaries,[],profile,check_budget=False,units=units)
            verify_saved_inputs(by_origin[key][2],request)
            checked.add(key)
    if checked != by_origin.keys():
        raise ValueError('Some saved candidates no longer match the prepared source/configuration plan')
    return len(checked)


def copy_checkpoint(source, destination, run_id, profile):
    """Preserve the original, all history and artifacts; change only copied run paths/profile."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or source in destination.parents or destination in source.parents or destination.exists():
        raise ValueError('Experimental destination must be fresh and separate')
    original = source/run_id/'state/migration.db'
    before = file_hash(original)
    shutil.copytree(source/run_id,destination/run_id)
    copied = destination/run_id/'state/migration.db'
    with sqlite3.connect('file:'+original.as_posix()+'?mode=ro',uri=True) as old, sqlite3.connect(copied) as new:
        old.backup(new)
        row = new.execute('SELECT run_config_json FROM runs WHERE run_id=?',(run_id,)).fetchone()
        config = json.loads(row[0])
        config['output_root'] = str(destination/Path(config['output_root']).resolve().relative_to(source))
        new.execute('UPDATE runs SET run_config_json=? WHERE run_id=?',(json.dumps(config),run_id))
        refresh_preparation(new,destination,run_id)
    (destination/run_id/'state/profile.json').write_text(profile.model_dump_json(indent=2),encoding='utf-8')
    if file_hash(original) != before:
        raise ValueError('Original checkpoint changed during copy')
    return dict(original_database=str(original),original_database_hash=before,checkpoint_database_hash=file_hash(copied))


def refresh_preparation(conn, destination, run_id):
    """Archive old preparation proofs, then require canonical discovery under the new policy."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    history = {}
    for name in ('scoped_checkpoints','scoped_reuse_consumers','scoped_stale_evidence'):
        if name not in tables:
            continue
        cursor = conn.execute('SELECT * FROM '+name+' WHERE run_id=?',(run_id,))
        columns = [item[0] for item in cursor.description]
        history[name] = [dict(zip(columns,row)) for row in cursor]
        conn.execute('DELETE FROM '+name+' WHERE run_id=?',(run_id,))
    path = Path(destination)/'original-preparation-checkpoints.json'
    if path.exists():
        raise ValueError('Preparation has already been refreshed')
    path.write_text(json.dumps(history,indent=2),encoding='utf-8')
