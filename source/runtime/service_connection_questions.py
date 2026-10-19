"""Verify discovered resources before asking grouped last-resort connection questions."""

import json
from pathlib import Path
from models.service_connection import ServiceConnection
from tools.state_store_tools.service_connections import remember, pending_questions
from tools.state_store_tools.runs import update_run_status
from tools.component_inventory_tools.identity import stable_id


def resolve_pending_connections(conn, config, profile, directory, units, factory):
    """Verify actual drivers once per evidence version, then pause only unresolved resources."""
    affected = [unit for unit in units.values() if unit.service_connections]
    if not affected:
        return True
    from runtime.behavior_conversion.driver_resolution import verify_connections
    from tools.source_discovery_tools.classpath import discover_java_classpath
    from runtime.workspace_paths import write_run_report
    import logging
    logger = logging.getLogger(__name__)
    classpath = discover_java_classpath(config.source_root, profile.classpath_jars, profile.eclipse_classpath_variables)
    context = factory(profile, Path(directory) / 'connection-verification', 'connection-verification')
    conn.execute('''CREATE TABLE IF NOT EXISTS service_connection_verifications (
        run_id TEXT, fingerprint TEXT, record_json TEXT, PRIMARY KEY(run_id,fingerprint))''')
    for unit in affected:
        checked = []
        for data in unit.service_connections:
            record = ServiceConnection.model_validate(data)
            identity = stable_id(record.fingerprint, record.driver_dependency, profile.java_version, profile.java_home)
            row = conn.execute('SELECT record_json FROM service_connection_verifications WHERE run_id=? AND fingerprint=?',
                               (config.run_id, identity)).fetchone()
            if row:
                record = ServiceConnection.model_validate_json(row[0])
            elif not record.issues or all(issue.startswith('Driver coordinates/version') for issue in record.issues):
                logger.info('Verifying service %s / connector %s and driver %s for Java %s',
                    record.service_id, record.connector_id, record.driver_class, profile.java_version)
                verify_connections([record], profile, context.verifier, classpath)
                if not record.issues:
                    with conn:
                        conn.execute('INSERT OR REPLACE INTO service_connection_verifications VALUES (?,?,?)',
                            (config.run_id, identity, record.model_dump_json()))
            checked.append(record)
        unit.service_connections = [record.model_dump(mode='json', exclude={'supporting_sources'}) for record in checked]
        for consumer in unit.consumers:
            remember(conn, config.run_id, consumer, unit.logical_id, checked)
    # Keep the latest consumer bindings only; discovery may also have recorded preliminary keys.
    active = {(consumer, unit.logical_id) for unit in affected for consumer in unit.consumers}
    for row in conn.execute('SELECT DISTINCT consumer,unit_key FROM service_connection_evidence WHERE run_id=?', (config.run_id,)).fetchall():
        if (row[0], row[1]) not in active:
            conn.execute('DELETE FROM service_connection_evidence WHERE run_id=? AND consumer=? AND unit_key=?', (config.run_id, *row))
    conn.commit()
    questions = pending_questions(conn, config.run_id)
    write_run_report(directory, 'service_connections.json', json.dumps([unit.model_dump(mode='json', exclude={'sources'}) for unit in affected], indent=2))
    write_run_report(directory, 'service_connection_questions.json', json.dumps(questions, indent=2))
    if questions:
        update_run_status(conn, config.run_id, 'paused', 'conversion_service_connections_pending')
        logger.warning('Connection discovery needs %s resource decisions after workspace and driver inspection. '
                       'Resolve service connections, then Resume; accepted work is preserved.', len(questions))
        return False
    return True
