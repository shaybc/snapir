"""Import selected indexed notes and execution bindings in a rollback-safe transaction."""

import hashlib
import json

from tools.composer_mapper_tools.frontmatter_parser import parse_frontmatter
from tools.composer_mapper_tools.indexed_analysis import digest
from tools.composer_mapper_tools.scoped_vault_importer import SCOPED_SCHEMA
from tools.composer_mapper_tools.scoped_context_state import SCOPED_CONTEXT_SCHEMA
from tools.composer_mapper_tools.shared_vault_importer import _parsed_note
from tools.composer_mapper_tools.scoped_intake_evidence import intake_evidence
from tools.state_store_tools._json import utc_now
from tools.state_store_tools.map_snapshot import pin_map


def import_indexed_vault(conn, analysis, mapped, config, summary, *, progress=None):
    """Read no unrelated note bodies; retain all existing qualified conversion gates."""
    source, root = analysis.conn, analysis.root
    source.executescript('DROP TABLE IF EXISTS temp.selected_notes; CREATE TEMP TABLE selected_notes(path TEXT PRIMARY KEY);')
    source.execute('''INSERT OR IGNORE INTO selected_notes SELECT b.note FROM context_bindings b
        JOIN selected_contexts s ON s.identity=b.context''')
    source.execute('''INSERT OR IGNORE INTO selected_notes SELECT n.path FROM notes n JOIN files f ON f.relative_path=n.source_relative_path
        JOIN selected_java j ON j.file=f.path WHERE n.kind='java_class' ''')
    # Canonical excluded occurrences remain available for onlyFor/routing cross-checks.
    source.execute('''INSERT OR IGNORE INTO selected_notes SELECT n.path FROM notes n WHERE n.kind='opStep' AND n.operation_identity IN (
        SELECT canonical.operation_identity FROM notes canonical JOIN operation_context_index o ON o.definition=canonical.definition
        JOIN selected_contexts s ON s.identity=o.identity WHERE canonical.kind='operation')''')
    conn.execute('SAVEPOINT indexed_intake')
    try:
        for statement in (*SCOPED_SCHEMA,*SCOPED_CONTEXT_SCHEMA):
            conn.execute(statement)
        pin_map(conn,config,analysis)
        evidence = intake_evidence(root,analysis,config)
        snapshot = json.dumps(evidence,sort_keys=True)
        for number,(path,) in enumerate(source.execute('SELECT path FROM selected_notes ORDER BY path'),1):
            entry = analysis.entry(path)
            target = analysis.safe_path(path)
            if target.stat().st_size > 4 * 1024 * 1024 or digest(target) != entry['note_hash']:
                raise ValueError('Selected indexed note changed or exceeds 4 MiB: ' + path)
            text = target.read_text(encoding='utf-8-sig')
            metadata = parse_frontmatter(text)
            if metadata.get('qualified_entity_id') != entry['definition_id'] or str(metadata.get('entity_id')) != entry['entity_id']:
                raise ValueError('Selected note and indexed identity disagree: ' + path)
            record = json.dumps(dict(entry,metadata=metadata,parsed=_parsed_note(entry,text,target),markdown=text),sort_keys=True)
            conn.execute('INSERT OR IGNORE INTO scoped_source_definitions VALUES (?,?,?,?,?,?)',
                (config.run_id,entry['definition_id'],entry['kind'],entry['entity_id'],entry['source_hash'],record))
            conn.execute('INSERT OR REPLACE INTO scoped_entity_usages VALUES (?,?,?,?,?,?,?,?)',
                (config.run_id,entry['usage_id'],entry['definition_id'],entry.get('operation_identity',''),entry.get('operation_id',''),entry.get('channel',''),str(target),record))
            if progress and (number == 1 or number % 100 == 0):
                progress(f'Imported {number} selected indexed notes')
        for row in source.execute('''SELECT o.identity,o.data,s.selected FROM operation_context_index o
            JOIN selected_contexts s ON s.identity=o.identity ORDER BY o.ordinal'''):
            context, selected = analysis._context(row[:2]), row[2]
            identity = context['operation_identity']
            conn.execute('INSERT OR REPLACE INTO scoped_operation_contexts VALUES (?,?,?,?,?,?,?,?)',
                (config.run_id,identity,context['channel'],context['operation_id'],context['definition_id'],str(root/context['note']),selected,json.dumps(context,sort_keys=True)))
            for kind,key,note in source.execute('SELECT kind,key,note FROM context_bindings WHERE context=?', (identity,)):
                entry = analysis.entry(note)
                conn.execute('INSERT OR REPLACE INTO scoped_context_bindings VALUES (?,?,?,?,?,?)',
                    (config.run_id,identity,kind,key,entry['definition_id'],str(root/note)))
            relative = analysis.entry(context['note'])['source_relative_path']
            conn.execute('INSERT OR IGNORE INTO channel_operations VALUES (?,?,?,?)', (context['operation_id'],context['channel'],relative,config.run_id))
            summary.channel_operations += 1
            if selected:
                now=utc_now()
                conn.execute('''INSERT OR IGNORE INTO operations(operation_id,channel,run_id,xml_file_path,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?)''', (context['operation_id'],context['channel'],config.run_id,relative,'pending',now,now))
        for kind,field in {'operation':'operations','opStep':'opsteps','format':'formats','context':'contexts','java_class':'java_classes'}.items():
            count=conn.execute('SELECT count(*) FROM scoped_source_definitions WHERE run_id=? AND kind=?', (config.run_id,kind)).fetchone()[0]
            setattr(summary,field,count)
        for channel,item in evidence['channels'].items():
            conn.execute('INSERT OR REPLACE INTO scoped_channel_evidence VALUES (?,?,?,?,?)', (config.run_id,channel,item['note'],item['note_hash'],json.dumps(item,sort_keys=True)))
        conn.execute('INSERT OR REPLACE INTO scoped_intake_evidence VALUES (?,?,?,?)', (config.run_id,analysis['identity_version'],hashlib.sha256(snapshot.encode()).hexdigest(),snapshot))
        analysis.verify_sources(config.source_root,progress)
        if digest(root/'vault-manifest.json') != analysis.manifest_hash or digest(analysis.database) != analysis['analysis_hash'] or (root/'vault-generation.json').exists():
            raise ValueError('Indexed map changed during intake')
        conn.execute('INSERT OR REPLACE INTO scoped_vault_runs VALUES (?,?,?,?)', (config.run_id,4,analysis['workspace_id'],analysis.manifest_hash))
        conn.execute('RELEASE SAVEPOINT indexed_intake')
    except BaseException:
        conn.execute('ROLLBACK TO SAVEPOINT indexed_intake')
        conn.execute('RELEASE SAVEPOINT indexed_intake')
        raise
    return summary
