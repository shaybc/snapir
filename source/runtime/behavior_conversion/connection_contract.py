"""Propagate authoritative connector facts and verified drivers through model contracts."""

from runtime.behavior_conversion.service_connection_evidence import SERVICE_CONNECTION_INSTRUCTION


def attach_connections(payload, connections):
    """Add relevant resource records and reject inconsistent current dependency pins."""
    records = {item['connection_id']: item for item in connections}
    payload['service_connections'] = sorted(records.values(), key=lambda item: item['connection_id'])
    payload['service_connection_requirement'] = dict(version=1, description=SERVICE_CONNECTION_INSTRUCTION)
    known = [dict(item) for item in payload.get('known_dependencies', [])]
    payload['known_dependencies'] = known
    for record in records.values():
        dependency = record.get('driver_dependency')
        if not dependency:
            continue
        prior = next((item for item in known if (item['group_id'], item['artifact_id']) ==
                      (dependency['group_id'], dependency['artifact_id'])), None)
        if prior and prior['version'] != dependency['version']:
            raise ValueError('Discovered driver version conflicts with current target: ' + dependency['group_id'] + ':' +
                             dependency['artifact_id'] + ' requires ' + dependency['version'] + ', target uses ' + prior['version'])
        if prior:
            prior['required_classes'] = sorted(set(prior.get('required_classes', []) + dependency['required_classes']))
            if dependency['scope'] == 'compile':
                prior['scope'] = 'compile'
        else:
            known.append(dict(dependency))
