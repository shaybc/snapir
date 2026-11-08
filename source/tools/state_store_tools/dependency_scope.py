"""Persist automatically required legacy operation work without changing root filters."""
from tools.state_store_tools.channel_operations import upsert_operation


def requested_operations(conn, config):
    """Select requested roots using the unchanged run configuration, excluding added work rows."""
    included = getattr(config, 'include_operations', None)
    excluded = getattr(config, 'exclude_operations', None) or ()
    channels = getattr(config, 'target_channels', None)
    return sorted(channel + '/' + operation for channel, operation in conn.execute(
        'SELECT channel,operation_id FROM operations WHERE run_id=?', (config.run_id,))
        if (not channels or channel in channels) and (not included or operation in included)
        and operation not in excluded and channel + '/' + operation not in excluded)


def include_required_operations(conn, config, graph, identities):
    """Add only discovered source dependencies to the existing execution queue."""
    existing = {row[0] + '/' + row[1] for row in conn.execute(
        'SELECT channel,operation_id FROM operations WHERE run_id=?', (config.run_id,))}
    for identity in identities:
        if identity in existing:
            continue
        channel, name = identity.split('/', 1)
        source = graph['operations'][identity].get('note')
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='channel_operations'").fetchone():
            row = conn.execute('SELECT xml_file_path FROM channel_operations WHERE run_id=? AND channel=? AND operation_name=?',
                (config.run_id, channel, name)).fetchone()
            if row:
                source = row[0]
        upsert_operation(conn, operation_id=name, channel=channel, run_id=config.run_id, xml_file_path=source)
