"""Distinguish absent intake evidence from duplicate exact records using real SQLite lookups."""
import json
import sqlite3
from types import SimpleNamespace
import pytest
from tools.composer_mapper_tools.scoped_vault_access import ScopedVaultAccess


@pytest.mark.parametrize('matches', [0, 1, 2])
def test_exact_intake_lookup_reports_missing_duplicate_or_returns_unique_record(matches):
    conn = sqlite3.connect(':memory:')
    try:
        conn.executescript('''CREATE TABLE scoped_vault_runs(run_id,schema_version);
            INSERT INTO scoped_vault_runs VALUES('run',3);
            CREATE TABLE scoped_operation_contexts(run_id,operation_identity,record_json);
            CREATE TABLE scoped_source_definitions(run_id,kind,logical_id,record_json);''')
        context = dict(channel='BANKADMIN', operation_id='Operation')
        conn.execute('INSERT INTO scoped_operation_contexts VALUES(?,?,?)', ('run','BANKADMIN/Operation',json.dumps(context)))
        record = dict(definition_id='definition', usage_id=None, kind='java_class', entity_id='example.ServiceException',
                      note='source.md', source_relative_path='XML/src/example/ServiceException.java')
        for _ in range(matches):
            conn.execute('INSERT INTO scoped_source_definitions VALUES(?,?,?,?)',
                         ('run','java_class',record['entity_id'],json.dumps(record)))
        # Nearby records must not count as exact matches.
        conn.execute('INSERT INTO scoped_source_definitions VALUES(?,?,?,?)',
                     ('other-run','java_class',record['entity_id'],json.dumps(record)))
        access = ScopedVaultAccess(conn, 'run')
        owner = SimpleNamespace(run_id='run',operation_identity='BANKADMIN/Operation',**context)
        if matches == 1:
            assert access.captured_java_dependency(owner,record['entity_id'],record['source_relative_path']).definition_id == 'definition'
        else:
            with pytest.raises(ValueError) as error:
                access.captured_java_dependency(owner,record['entity_id'],record['source_relative_path'])
            message = str(error.value)
            assert record['entity_id'] in message and record['source_relative_path'] in message
            assert ('no matching saved intake record' if matches == 0 else 'multiple matching saved intake records (2)') in message
            if matches == 0:
                assert 'not a filesystem existence check' in message
    finally:
        conn.close()
