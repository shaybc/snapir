"""Exercise nested format identity, pre-work diagnostics and completed-index recovery."""

import json
import sqlite3
import subprocess
import pytest

from tests.indexed_mapper_fixture import indexed_mapper_jar, generate, workspace


def nested_workspace(root):
    workspace(root)
    (root / 'src/Channel/A/formats.xml').write_text('''<XML>
      <fmtDef id="Outer"><PS10NewXMLFormat txnName="Example">
        <refFmt refid="Header"/>
        <fmtDef id="Choice"><SwitchCaseFormat>
          <caseRefFmt keyName="Option" keyValue="S"><refFmt refid="Join"/>
            <fmtDef id="Deep"><CCString dataName="Deep"/></fmtDef>
          </caseRefFmt>
          <caseRefFmt keyName="Option" keyValue="D"><refFmt refid="Remove"/></caseRefFmt>
          <caseRefFmt default="yes"><refFmt refid="Fallback"/></caseRefFmt>
        </SwitchCaseFormat></fmtDef>
        <fmtDef id="Sibling"><CCString dataName="Sibling"/></fmtDef>
        <refFmt refid="Session"/>
      </PS10NewXMLFormat></fmtDef>
      <fmtDef id="Header"><CCString dataName="Header"/></fmtDef>
      <fmtDef id="Join"><CCString dataName="Join"/></fmtDef>
      <fmtDef id="Remove"><CCString dataName="Remove"/></fmtDef>
      <fmtDef id="Fallback"><CCString dataName="Fallback"/></fmtDef>
      <fmtDef id="Session"><CCString dataName="Session"/></fmtDef>
    </XML>''')
    return root


def test_indexed_nested_inventory_keeps_parent_and_sibling_order(tmp_path, indexed_mapper_jar):
    root = nested_workspace(tmp_path / 'source')
    vault = tmp_path / 'map'
    generate(indexed_mapper_jar, root, vault)
    with sqlite3.connect(vault / 'analysis/analysis.sqlite') as conn:
        notes = dict(conn.execute("SELECT entity_id,path FROM notes WHERE entity_id IN ('Outer','Choice','Sibling','Deep')"))
    assert set(notes) == {'Outer', 'Choice', 'Sibling', 'Deep'}
    assert notes['Choice'] == notes['Outer'][:-3] + '/nested/1/Choice.md'
    assert notes['Sibling'] == notes['Outer'][:-3] + '/nested/2/Sibling.md'
    assert notes['Deep'] == notes['Choice'][:-3] + '/nested/1/Deep.md'
    text = (vault / notes['Choice']).read_text(encoding='utf-8')
    assert 'SwitchCaseFormat' in text
    assert all(value in text for value in ('Option', 'Join', 'Remove', 'Fallback', 'default'))


def test_nested_indexed_inventory_matches_nonindexed_mapping(tmp_path, indexed_mapper_jar):
    from tools.composer_mapper_tools.vault_manifest import read_vault_manifest
    root = nested_workspace(tmp_path / 'source')
    indexed, legacy = tmp_path / 'indexed', tmp_path / 'legacy'
    generate(indexed_mapper_jar, root, indexed)
    result = subprocess.run(['java', '-jar', str(indexed_mapper_jar), '--root', str(root), '--vault', str(legacy),
                             '--vault-layout', 'scoped', '--workspace-id', 'bank', '--md', 'true'],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(indexed / 'analysis/analysis.sqlite') as conn:
        actual = {name: (path, selector) for name, path, selector in conn.execute("SELECT entity_id,path,source_selector FROM notes WHERE kind='format'")}
    expected = {row['entity_id']: (row['note'], row['source_selector'])
                for row in read_vault_manifest(legacy, allow_shared=True)['entities'] if row['kind'] == 'format'}
    assert actual == expected
    for path, _ in actual.values():
        before = (legacy / path).read_text(encoding='utf-8')
        after = (indexed / path).read_text(encoding='utf-8')
        assert after.replace('vault_schema_version: 4', 'vault_schema_version: 3') == before


def test_inventory_failure_logs_exact_definition_before_crash(tmp_path, indexed_mapper_jar):
    root = nested_workspace(tmp_path / 'source')
    vault = tmp_path / 'map'
    # Case-insensitive filesystem note collision deliberately fails during rendering.
    path = root / 'src/Channel/A/formats.xml'
    path.write_text('<XML><fmtDef id="Clash"/><fmtDef id="clash"/></XML>')
    result, log = generate(indexed_mapper_jar, root, vault, check=False)
    assert result.returncode != 0
    for text in (log.read_text(encoding='utf-8'), (vault / 'composer-mapper.log').read_text(encoding='utf-8')):
        assert 'Starting inventory definition' in text
        assert str(path) in text
        assert 'selector=/XML[1]/fmtDef[2]' in text
        assert text.index('Starting inventory definition') < text.index('FAILED')
    original = (vault / 'analysis/analysis.sqlite').read_bytes()
    result, log = generate(indexed_mapper_jar, root, tmp_path / 'retry', '--resume-analysis', vault, check=False)
    assert result.returncode != 0  # Same invalid source still fails, after reusing its completed index.
    text = log.read_text(encoding='utf-8')
    assert 'Resuming completed source index' in text
    assert 'Starting source indexing' not in text
    assert 'Inventory definition failed: format clash' in text
    assert (vault / 'analysis/analysis.sqlite').read_bytes() == original


def test_completed_index_recovery_restarts_rendering_without_reindexing(tmp_path, indexed_mapper_jar):
    root = nested_workspace(tmp_path / 'source')
    first = tmp_path / 'first'
    generate(indexed_mapper_jar, root, first)
    assert (first / 'analysis/index-checkpoint.sqlite').is_file()
    # A checkpoint is captured before any rendered products: simulates a later crash.
    recovered = tmp_path / 'recovered'
    _, log = generate(indexed_mapper_jar, root, recovered, '--resume-analysis', first)
    text = log.read_text(encoding='utf-8')
    assert 'Resuming completed source index' in text
    assert 'Starting source capture' not in text
    assert 'Starting source indexing' not in text
    with sqlite3.connect(first / 'analysis/analysis.sqlite') as before, sqlite3.connect(recovered / 'analysis/analysis.sqlite') as after:
        assert before.execute('SELECT path,body FROM notes ORDER BY path').fetchall() == after.execute('SELECT path,body FROM notes ORDER BY path').fetchall()
    assert json.loads((recovered / 'vault-manifest.json').read_text())['complete'] is True


@pytest.mark.parametrize('change', ['edit', 'add', 'remove', 'corrupt', 'integrity', 'incomplete', 'policy', 'configuration'])
def test_checkpoint_rejects_stale_or_damaged_index(tmp_path, indexed_mapper_jar, change):
    root = workspace(tmp_path / 'source')
    first = tmp_path / 'first'
    generate(indexed_mapper_jar, root, first)
    extra = []
    if change == 'edit':
        path = root / 'src/pkg/Leaf.java'
        path.write_text(path.read_text().replace('return 1', 'return 3'))
    elif change == 'add':
        (root / 'src/pkg/Added.java').write_text('package pkg; public class Added {}')
    elif change == 'remove':
        (root / 'src/pkg/Unrelated.java').unlink()
    elif change in {'corrupt', 'integrity', 'incomplete', 'policy'}:
        import hashlib
        checkpoint = first / 'analysis/index-checkpoint.sqlite'
        if change in {'corrupt', 'integrity'}:
            checkpoint.write_bytes(b'not a database')
        else:
            with sqlite3.connect(checkpoint) as conn:
                conn.execute("UPDATE revision SET value=? WHERE key=?", ('old-mapper', 'index_stage_policy')
                             if change == 'policy' else ('false', 'index_stage_complete'))
        if change != 'corrupt':
            checkpoint.with_suffix('.sqlite.sha256').write_text(hashlib.sha256(checkpoint.read_bytes()).hexdigest())
    else:
        extra = ['--analysis-batch-files', '50']
    result, log = generate(indexed_mapper_jar, root, tmp_path / 'recovered', '--resume-analysis', first, *extra)
    assert result.returncode == 0
    text = log.read_text(encoding='utf-8')
    assert 'Completed source index not reusable; rebuilding source index' in text
    assert 'Starting source capture' in text
    assert 'Resuming completed source index' not in text


def test_indexed_inline_reference_counts_match_python_inventory(tmp_path, indexed_mapper_jar):
    from tests.test_component_inventory import inline_reference_workspace
    root = inline_reference_workspace(tmp_path)
    vault = tmp_path / 'map'
    generate(indexed_mapper_jar, root, vault)
    with sqlite3.connect(vault / 'analysis/analysis.sqlite') as conn:
        uses = conn.execute("SELECT cc.weight FROM configured_counts cc JOIN xml_nodes n ON n.id=cc.node WHERE n.name='CCString'").fetchall()
        assert uses == [(1,), (1,)]
        assert not conn.execute("SELECT data FROM records WHERE collection='component_issues' AND data LIKE '%refFmt%'").fetchall()
        assert conn.execute("SELECT cc.kind,cc.valid FROM configured_counts cc JOIN xml_attributes a ON a.node=cc.node WHERE a.name='id' AND a.value='Nested'").fetchall() == [('format', 1)]
