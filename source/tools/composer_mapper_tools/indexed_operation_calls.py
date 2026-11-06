"""Discover calls from indexed context metadata; read call-step bodies on demand only."""

import hashlib
from pathlib import Path
from tools.composer_mapper_tools.operation_parser import parse_operation_note
from tools.composer_mapper_tools.opstep_parser import parse_opstep_note
from tools.composer_mapper_tools.mapped_scope import current_mapped


def iter_indexed_connections(root, analysis, progress=None):
    """Preserve the established call-graph API without opening unrelated operation notes."""
    clause=''
    active=current_mapped()
    if active is not None and active.analysis.root==Path(root).resolve():
        # A fresh reader has its own temp schema; copy only requested context IDs.
        analysis.conn.execute('CREATE TEMP TABLE IF NOT EXISTS requested_calls(identity TEXT PRIMARY KEY)')
        analysis.conn.executemany('INSERT OR IGNORE INTO requested_calls VALUES (?)',active.analysis.conn.execute('SELECT identity FROM selected_contexts'))
        clause=' WHERE identity IN (SELECT identity FROM requested_calls)'
    for number,(identity,data) in enumerate(analysis.conn.execute('SELECT identity,data FROM operation_context_index'+clause+' ORDER BY ordinal'),1):
        context=analysis._context((identity,data))
        entry=analysis.entry(context['note'])
        operation_note=analysis.safe_path(context['note'])
        if operation_note.stat().st_size>4*1024*1024:
            raise ValueError('Indexed operation exceeds the 4 MiB note budget')
        if hashlib.sha256(operation_note.read_bytes()).hexdigest()!=entry['note_hash']:
            raise ValueError('Indexed operation note changed: '+context['note'])
        operation=parse_operation_note(operation_note.read_text(encoding='utf-8-sig'),str(operation_note))
        key=context['channel']+'/'+context['operation_id']
        yield 'operation',(key,dict(operation_id=context['operation_id'],channel=context['channel'],note=context['note'],
            source_hash=entry['source_hash'],definition_id=context['definition_id'],ref_formats=operation.ref_formats))
        for call in context['calls']:
            note=analysis.safe_path(call['step_note'])
            if note.stat().st_size>4*1024*1024:
                raise ValueError('Indexed call step exceeds the 4 MiB note budget')
            text=note.read_text(encoding='utf-8-sig')
            if hashlib.sha256(note.read_bytes()).hexdigest()!=analysis.entry(call['step_note'])['note_hash']:
                raise ValueError('Indexed call step changed: '+call['step_note'])
            step=parse_opstep_note(text,str(note))
            if (step.parameters.get('opExecuteName') or '')!=call['target_name']:
                raise ValueError('Indexed call and source step disagree: '+call['step_note'])
            item=dict(caller=key,callee=call.get('target_context',context['channel']+'/'+call['target_name']),
                step=step.id,note=call['step_note'],parameters=step.parameters,transitions=step.transitions,
                evidence_hash=hashlib.sha256(text.encode()).hexdigest())
            if call.get('detail'):
                item['operation']=item.pop('caller');item['detail']=call['detail'];yield 'issue',item
            else:
                yield 'call',item
        if progress and (number==1 or number%250==0):
            progress(f'Read {number} indexed operation connections')
    for item in analysis['diagnostics']:
        if item.get('kind') in {'identity','source_parse'}:
            yield 'issue',dict(operation=item.get('operation',''),step=item.get('step',''),detail=item['detail'])


def discover_indexed_calls(root, analysis, progress=None):
    """Keep the explicit complete-graph API; large exporters consume the iterator."""
    operations,calls,issues={},[],[]
    for kind,value in iter_indexed_connections(root,analysis,progress):
        if kind=='operation':operations[value[0]]=value[1]
        elif kind=='call':calls.append(value)
        else:issues.append(value)
    return dict(operations=operations,calls=calls,issues=issues)
