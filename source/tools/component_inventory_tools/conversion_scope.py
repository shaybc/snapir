"""Persist selected conversion roots and their required operation/source dependency closure."""

import json
from xml.etree import ElementTree

from tools.state_store_tools.inventory_graph import reachable_ids


def persist_conversion_scope(conn, config):
    """Keep global analysis separate from selected work without overriding operation policies."""
    available = {(row[0], row[1]) for row in conn.execute(
        'SELECT DISTINCT channel,operation_id FROM configured_component_uses WHERE run_id=?', (config.run_id,))}
    available.update((row[0], row[1]) for row in conn.execute('''SELECT json_extract(record_json,'$.channel'),
        json_extract(record_json,'$.logical_id') FROM configured_component_definitions WHERE run_id=? AND component_kind='operation' ''', (config.run_id,)))
    from tools.component_inventory_tools.operation_selection import operation_selection
    def read_uses(channel, name):
        return (json.loads(row[0]) for row in conn.execute('''SELECT record_json FROM configured_component_uses
            WHERE run_id=? AND channel=? AND operation_id=?''', (config.run_id, channel, name)))
    def class_name(identity):
        row = conn.execute('SELECT record_json FROM source_implementations WHERE run_id=? AND implementation_id=?', (config.run_id, identity)).fetchone()
        return json.loads(row[0])['class_name'] if row else None
    selected, required, reasons, unresolved = operation_selection(available, read_uses, class_name, config)
    conn.execute('CREATE TABLE IF NOT EXISTS conversion_scope (run_id TEXT,kind TEXT,identity TEXT,reason TEXT,PRIMARY KEY(run_id,kind,identity))')
    conn.execute('DELETE FROM conversion_scope WHERE run_id=?', (config.run_id,))
    roots = set()
    for channel, name in sorted(required):
        identity = channel + '/' + name
        conn.execute('INSERT INTO conversion_scope VALUES (?,?,?,?)', (config.run_id, 'operation', identity, reasons[(channel, name)]))
        roots.update(row[0] for row in conn.execute('''SELECT DISTINCT implementation_id FROM configured_component_uses
            WHERE run_id=? AND channel=? AND operation_id=? AND implementation_id IS NOT NULL''', (config.run_id, channel, name)))
    implementations = reachable_ids(conn, config.run_id, roots)
    for identity in implementations:
        conn.execute('INSERT INTO conversion_scope VALUES (?,?,?,?)',
            (config.run_id, 'implementation', identity, 'selected configured use' if identity in roots else 'transitive Java dependency'))
    conn.commit()
    totals = {name: conn.execute('SELECT count(*) FROM ' + table + ' WHERE run_id=?', (config.run_id,)).fetchone()[0]
              for name, table in (('implementations', 'source_implementations'), ('configured_definitions', 'configured_component_definitions'),
                                  ('configured_uses', 'configured_component_uses'), ('dependency_edges', 'java_dependency_edges'),
                                  ('dependency_uses', 'java_dependency_uses'))}
    totals['global_usage_root_groups'] = conn.execute('SELECT count(*) FROM java_usage_roots WHERE run_id=?', (config.run_id,)).fetchone()[0]
    totals['global_usage_target_factors'] = conn.execute('SELECT count(*) FROM java_usage_targets WHERE run_id=?', (config.run_id,)).fetchone()[0]
    return dict(selected_operations=sorted(channel + '/' + name for channel, name in selected),
        required_operations=sorted(channel + '/' + name for channel, name in required),
        required_implementations=len(implementations), unresolved_calls=unresolved,
        excluded_required_operations=sorted(channel + '/' + name for channel, name in required if name in (config.exclude_operations or [])),
        workspace_totals=totals,
        analysis_scope='Global usage counts; selected configured/static dependency closure; service bindings remain subject to conversion-time checks')
