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
    selected = {(channel, name) for channel, name in available if channel in config.target_channels
        and (not config.include_operations or name in config.include_operations) and name not in (config.exclude_operations or [])}
    reasons = {pair: 'selected operation' for pair in selected}
    pending = list(selected)
    required, unresolved = set(selected), []
    while pending:
        channel, name = pending.pop()
        for use_json, implementation_json in conn.execute('''SELECT u.record_json,s.record_json FROM configured_component_uses u
            LEFT JOIN source_implementations s ON s.run_id=u.run_id AND s.implementation_id=u.implementation_id
            WHERE u.run_id=? AND u.channel=? AND u.operation_id=? AND u.component_kind='opStep' ''', (config.run_id, channel, name)):
            use = json.loads(use_json)
            node = ElementTree.fromstring(use['configuration_xml'])
            implementation = node.get('implClass') or node.get('javaClass') or (
                json.loads(implementation_json)['class_name'] if implementation_json else
                (use.get('resolution_issue') or '').partition('Java source is missing: ')[2])
            implementation = implementation or node.tag.rsplit('}', 1)[-1]
            if not implementation.endswith('CCComplexOpStep'):
                continue
            target = node.get('opExecuteName')
            if not target:
                target = next((child.get('value') or child.text for child in node.iter()
                               if (child.get('id') or child.get('name')) == 'opExecuteName'), None)
            if not target:
                continue
            pair = (channel, target)
            if pair not in available:
                unresolved.append(dict(caller=channel + '/' + name, target=channel + '/' + target))
            elif pair not in required:
                required.add(pair)
                reasons[pair] = 'called by ' + channel + '/' + name
                pending.append(pair)
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
    return dict(selected_operations=sorted(channel + '/' + name for channel, name in selected),
        required_operations=sorted(channel + '/' + name for channel, name in required),
        required_implementations=len(implementations), unresolved_calls=unresolved,
        excluded_required_operations=sorted(channel + '/' + name for channel, name in required if name in (config.exclude_operations or [])),
        workspace_totals=totals,
        analysis_scope='Global usage counts; selected configured/static dependency closure; service bindings remain subject to conversion-time checks')
