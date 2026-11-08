"""Prepare selected scoped workflows using existing discovery and qualified closure analysis."""

import json
from pathlib import Path

from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess
from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
from tools.conversion_tools.closure_builder_tool import build_scoped_operation_closure
from tools.conversion_tools.scoped_workflow.calls import published_boundaries, bind_context_calls
from tools.conversion_tools.scoped_workflow.contracts import plan_context_contracts
from tools.conversion_tools.scoped_workflow.payloads import operation_payload
from tools.conversion_tools.scoped_workflow.units import build_scoped_units
from tools.conversion_tools.scoped_workflow.source_project import scoped_source_project
from tools.operation_call_tools.discovery import discover_operation_calls
from tools.source_discovery_tools.classpath import discover_java_classpath
from tools.state_store_tools.operation_calls import save_graph
from tools.conversion_tools.scoped_reuse.checkpoint import validate_checkpoints, observe_inputs, make_checkpoints
from tools.conversion_tools.scoped_reuse.artifacts import remember_prepared, reuse_prepared
from tools.conversion_tools.scoped_reuse.state import checkpoints
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.conversion_tools.component_graph import build_component_plan
from tools.conversion_tools.dependency_planning.operation_sources import operation_scope
from tools.conversion_tools.dependency_planning.reuse_sources import component_sources

GENERATION_GATE = 'Scoped generation remains disabled pending C6 end-to-end acceptance.'


def is_scoped_run(conn, run_id):
    """Detect schema three without creating tables or reinterpreting older runs."""
    table = conn.execute("SELECT 1 FROM sqlite_master WHERE name='scoped_vault_runs'").fetchone()
    row = conn.execute('SELECT schema_version FROM scoped_vault_runs WHERE run_id=?', (run_id,)).fetchone() if table else None
    return bool(row and row[0] in (3,4))


def prepare_scoped_workflow(conn, config, profile, *, selected=None, classpath_index=None):
    """Prepare requested roots and their required dependencies without changing user filters."""
    access = ScopedVaultAccess(conn, config.run_id)
    included = {row[0] + '/' + row[1]: row[2] for row in conn.execute('''SELECT channel,operation_id,operation_identity
        FROM scoped_operation_contexts WHERE run_id=? AND selected=1''', (config.run_id,))}
    selected = set(included) if selected is None else set(selected)
    if not selected:
        raise ValueError('Scoped preparation requires a nonempty subset of the imported selection')
    classpath = classpath_index if classpath_index is not None else discover_java_classpath(
        config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    if (Path(config.vault_root) / 'vault-generation.json').exists():
        validate_checkpoints(conn, config, profile, classpath, selected)
    graph = discover_operation_calls(config.vault_root)
    if not selected <= included.keys():
        authorized = operation_scope(conn, config, profile, graph, included)
        if not selected <= set(authorized.source_operations):
            raise ValueError('Scoped preparation requires imported selection roots or their resolved dependencies')
    scope = operation_scope(conn, config, profile, graph, selected)
    required = set(scope.source_operations)
    scope.source_projects = {key: scoped_source_project(profile, key.split('/', 1)[0], source_root=config.source_root)
                             for key in required}
    common = validate_checkpoints(conn, config, profile, classpath, required)
    cached = reuse_prepared(conn, config.run_id, checkpoints(conn, config.run_id), required) if not scope.blockers else None
    if cached is not None:
        report = _resolved_report(conn, config, profile, access, scope, cached, sorted(required))
        conn.execute('UPDATE scoped_workflow_preparations SET preparation_json=? WHERE run_id=?',
                     (json.dumps(report, sort_keys=True), config.run_id))
        return report
    expected = conn.execute('SELECT manifest_hash FROM scoped_vault_runs WHERE run_id=?', (config.run_id,)).fetchone()[0]
    manifest = Path(config.vault_root) / 'vault-manifest.json'
    if file_digest(manifest) != expected:
        raise ValueError('Vault manifest changed since intake; refresh the run')
    if file_digest(manifest) != expected:
        raise ValueError('Vault manifest changed during call discovery')
    if not selected <= graph['operations'].keys():
        raise ValueError('Selected contexts are absent from the mapped call graph')
    conn.execute('SAVEPOINT scoped_workflow_preparation')
    try:
        save_graph(conn, config.run_id, graph)
        closures = {}
        for key in scope.order:
            channel, name = key.split('/', 1)
            context = access.operation(channel, name)
            if context.definition_id != graph['operations'][key]['definition_id']:
                raise ValueError('Execution definition differs from call graph: ' + key)
            closure = build_scoped_operation_closure(conn, name, channel, config.run_id, config.source_root,
                java_project=scope.source_projects[key], classpath_index=classpath, profile=profile,
                included_contexts=set(), published_contexts=set(scope.reused_services))
            closures[key] = closure
        contracts = plan_context_contracts(conn, config.run_id, graph, closures)
        from runtime.intake_plan import has_intake_plan
        calls, issues, waves = bind_context_calls(graph, closures, contracts,
            published_boundaries(conn, config.run_id), profile, require_published=has_intake_plan(conn, config.run_id))
        operations, cache = {}, {}
        for key, closure in closures.items():
            blockers = [issue.detail for issue in closure.blocking_issues] + issues[key]
            blockers.extend(item['detail'] for item in scope.blockers if item['operation'] == key or item['path'][0] == key)
            payload = {}
            if not blockers:
                try:
                    units, bindings = build_scoped_units(conn, config, closure, calls=calls[key], source_cache=cache,
                        profile=profile, classpath_index=classpath)
                    payload = operation_payload(config, closure, contracts[key], calls[key], units, bindings)
                except (ValueError, OSError) as exc:
                    blockers.append(str(exc))
            operations[key] = dict(status='blocked' if blockers else 'prepared', blockers=blockers,
                contract=contracts[key], calls=calls[key], dependency_wave=waves[key], **payload)
        # A caller cannot look prepared while its selected callee is blocked by C4 evidence.
        changed = True
        while changed:
            changed = False
            for key, item in operations.items():
                if item['status'] == 'prepared' and any(
                    call['callee'] in operations and not call['service_contract'].get('published_api')
                    and operations[call['callee']]['status'] == 'blocked' for call in item['calls']):
                    item['status'] = 'blocked'
                    item['blockers'].append('Selected called operation has blocked preparation evidence')
                    changed = True
        report = _resolved_report(conn, config, profile, access, scope, operations, [])
        if digest(observe_inputs(conn, config, profile, classpath)) != digest(common):
            raise ValueError('Scoped input profile or layout changed during preparation; refresh/replan')
        for checkpoint in make_checkpoints(conn, config, report, closures, common):
            remember_prepared(conn, config.run_id, checkpoint, operations[checkpoint.operation_key],
                              closures[checkpoint.operation_key])
        conn.execute('''CREATE TABLE IF NOT EXISTS scoped_workflow_preparations (
            run_id TEXT PRIMARY KEY, preparation_json TEXT NOT NULL)''')
        conn.execute('INSERT OR REPLACE INTO scoped_workflow_preparations VALUES (?,?)',
                     (config.run_id, json.dumps(report, sort_keys=True)))
        conn.execute('RELEASE SAVEPOINT scoped_workflow_preparation')
        return report
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT scoped_workflow_preparation')
        conn.execute('RELEASE SAVEPOINT scoped_workflow_preparation')
        raise


def _resolved_report(conn, config, profile, access, scope, operations, reused):
    """Keep root/dependency reasons and source/artifact choices in the existing run snapshot."""
    plan = _component_plan(operations, access, conn, config.run_id, profile)
    scope.components = component_sources(plan, profile)
    return dict(run_id=config.run_id, schema_version='scoped-v3-c5', conversion_enabled=False,
        generation_gate=GENERATION_GATE, operations=operations, reused_contexts=reused,
        requested_operations=scope.requested_operations, required_operations=scope.required_operations,
        dependency_plan=scope.model_dump(mode='json'), component_plan=plan)


def _component_plan(operations,access,conn,run_id,profile):
    """Resolve default step implementations from the same qualified channel evidence as closure analysis."""
    from tools.composer_mapper_tools.channel_note_parser import parse_channel_note
    mappings={}
    for key,item in sorted(operations.items()):
        if item['status']!='prepared': continue
        channel,name=key.split('/',1)
        context=access.operation(channel,name)
        mappings[key]=dict((tag,fqcn) for tag,fqcn,_ in parse_channel_note(access.channel_evidence(context)['markdown'],context.channel)).get('opStep')
    plan=build_component_plan(operations,step_mappings=mappings)
    from tools.state_store_tools.conversion_components import register_component_plan
    register_component_plan(conn,run_id,plan,profile)
    return plan.model_dump(mode='json')
