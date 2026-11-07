"""Keep workspace-wide base-class sharing independent of one configured format occurrence."""
import json
from types import SimpleNamespace

from tools.state_store_tools.db import get_connection, create_all_tables
from tools.state_store_tools.component_reuse import record_consumers


def test_single_selected_operation_counts_other_original_class_consumers(tmp_path):
    conn = get_connection(':memory:')
    create_all_tables(conn)
    original = dict(package_name='example', class_name='Base', source_hash='source-hash', source_path='Base.java')
    conn.execute('INSERT INTO source_implementations VALUES (?,?,?,?,?)',
                 ('run', 'base-original', 'bank', 'source-hash', json.dumps(original)))
    for number in range(6):
        conn.execute('INSERT INTO java_dependency_uses VALUES (?,?,?,?,?,?,?)',
            ('run', str(number), 'base-original', 'operation-' + str(number), 'Operation' + str(number), 'WEB', '{}'))
    node = SimpleNamespace(kind='java_implementation', label='example.Base',
        provenance=dict(source_hash='source-hash', source_file=str(tmp_path / 'Base.java')),
        operations=['WEB/Operation0'], unit_ids=['one-configured-format'])
    plan = SimpleNamespace(components={'base': node}, groups=[SimpleNamespace(group_id='group', members=['base'])])
    record_consumers(conn, 'run', plan, {'one-configured-format': dict(consumers=['WEB/Operation0'])}, source_root=str(tmp_path))
    consumers = json.loads(conn.execute('SELECT consumers_json FROM shared_component_consumers').fetchone()[0])
    assert consumers == ['WEB/Operation' + str(number) for number in range(6)]
    conn.close()
