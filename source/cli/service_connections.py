"""Collect grouped resource decisions after automatic discovery is exhausted."""

import json
import sqlite3
from runtime.workspace_paths import run_database_path
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.service_connections import pending_questions, save_decision


def answer_connection_questions(directory, *, reader=None, answers=None):
    """Offer one structured answer per unresolved resource, retaining earlier answers."""
    from cli.interactive import is_interactive
    interactive = reader is None and answers is None
    if interactive:
        if not is_interactive():
            return False
        from prompt_toolkit import prompt
        reader = prompt
    database = run_database_path(directory)
    if not database.is_file():
        return False
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as check:
        phase = check.execute('SELECT current_phase FROM runs WHERE run_id=?', (directory.name,)).fetchone()
        if not phase or phase[0] != 'conversion_service_connections_pending':
            return True
    conn = get_connection(str(database))
    try:
        questions = pending_questions(conn, directory.name)
        for item in questions:
            print('Connection decision: ' + item['channel'] + ' / ' + item['service_id'])
            print('Affected units: ' + ', '.join(item['consumers']))
            print('Unresolved evidence: ' + '; '.join(item['issues']))
            if item['driver_candidates']:
                print('Driver evidence: ' + json.dumps(item['driver_candidates'], indent=2))
            print('Supply JSON with driver_dependency (coordinates/version/scope/required_classes), '
                  'service_alias or transaction_scope. Blank leaves it unresolved. '
                  'Missing files should be supplied to the workspace and intake refreshed.')
            if answers is not None:
                matches = [answer for answer in answers if answer.get('channel') == item['channel'] and
                           (answer.get('service_id') == item['service_id'] or answer.get('connector_id') == item['connector_id'])]
                if len(matches) != 1:
                    return False
                answer = {key: value for key, value in matches[0].items() if key not in {'channel', 'service_id', 'connector_id'}}
                raw = json.dumps(answer)
            else:
                candidates = [candidate['dependency'] for candidate in item['driver_candidates'] if candidate.get('dependency')]
                chosen = None
                if interactive and candidates:
                    from cli.interactive import select_option
                    choice = select_option('Select a workspace driver candidate (will be verified)', [
                        (str(index), candidate['group_id'] + ':' + candidate['artifact_id'] + ':' + candidate['version'])
                        for index, candidate in enumerate(candidates)] + [('manual', 'Supply another version or decision'), ('skip', 'Leave unresolved')])
                    if choice == 'skip':
                        return False
                    if choice != 'manual':
                        chosen = {'driver_dependency': candidates[int(choice)]}
                try:
                    raw = json.dumps(chosen) if chosen else reader('Connection answer: ')
                except (EOFError, KeyboardInterrupt) as exc:
                    from cli.interactive import SelectionCancelled
                    raise SelectionCancelled from exc
            if not raw.strip():
                return False
            save_decision(conn, directory.name, item['connection_id'], item['fingerprint'], json.loads(raw))
        return True
    finally:
        conn.close()
