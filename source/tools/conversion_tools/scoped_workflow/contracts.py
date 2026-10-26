"""Plan HTTP contracts from the consuming context's effective canonical formats."""

import hashlib
import json
from urllib.parse import quote

from tools.state_store_tools.operation_calls import initialize, get_contract


def _referenced_definitions(root, formats):
    """Carry selected transitive format bodies, including cyclic references by identity."""
    result, visited, pending = {}, {root.definition_id}, [root]
    while pending:
        node = pending.pop()
        pending.extend(node.children)
        identity = node.reference_definition_id
        if identity and identity not in visited:
            visited.add(identity)
            target = formats.get(identity)
            if target:
                result[identity] = target.model_dump(mode='json')
                pending.append(target)
            else:
                result[identity] = dict(unresolved=True)
    return result


def plan_context_contracts(conn, run_id, graph, closures):
    """Persist planned contracts, preserving readiness only for identical evidence.

    No contract becomes assembled, validated, deployed, or published here.
    """
    initialize(conn)
    result = {}
    for key, closure in closures.items():
        if key != closure.channel + '/' + closure.operation_id:
            raise ValueError('Contract key disagrees with consuming context: ' + key)
        formats = {}
        for role, identity in closure.format_roles.items():
            node = closure.formats.get(identity)
            formats[role] = dict(definition_id=identity, effective_format=node.model_dump(mode='json'),
                referenced_definitions=_referenced_definitions(node, closure.formats)) if node else dict(
                definition_id=identity, unresolved=True)
        contract = dict(operation=key, method='POST',
            path='/operations/' + '/'.join(quote(part, safe='') for part in key.split('/')),
            media_type='application/xml',
            base_url_property='operations.' + hashlib.sha256(key.encode()).hexdigest()[:12] + '.base-url',
            formats=formats, source_hash=graph['operations'][key]['source_hash'],
            return_body_switches=closure.return_body_switches,
            return_body_formats={identity: dict(effective_format=closure.formats[identity].model_dump(mode='json'),
                referenced_definitions=_referenced_definitions(closure.formats[identity], closure.formats))
                for identity in sorted({identity for switches in closure.return_body_switches.values()
                                        for identity in switches.values()}) if identity in closure.formats},
            definition_id=closure.definition_id, contextual_evidence_hash=closure.evidence_hash,
            call_evidence=[call for call in graph['calls'] if call['caller'] == key],
            error_policy='Preserve target error XML and map evidenced return outcomes; report unknown mappings.')
        digest = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
        prior = conn.execute('SELECT fingerprint,status FROM operation_service_contracts WHERE run_id=? AND operation_key=?',
                             (run_id, key)).fetchone()
        status = prior[1] if prior and prior[0] == digest else 'planned'
        conn.execute('INSERT OR REPLACE INTO operation_service_contracts VALUES (?,?,?,?,?)',
                     (run_id, key, digest, status, json.dumps(contract, sort_keys=True)))
        result[key] = get_contract(conn, run_id, key)
    return result
