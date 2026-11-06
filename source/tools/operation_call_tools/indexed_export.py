"""Export indexed maps with SQL-backed ordering and streamed XLSX rows, without project JSON."""

from pathlib import Path
import sqlite3
import tempfile

from tools.composer_mapper_tools.indexed_analysis import IndexedAnalysis
from tools.composer_mapper_tools.indexed_operation_calls import iter_indexed_connections
from tools.operation_call_tools.indexed_waves import index_waves
from tools.operation_call_tools.streamed_workbook import streamed_sheet


def export_indexed_workbook(vault,output,relationships=False,progress=None):
    """Keep source map access readonly and bound traversal/workbook memory on large maps."""
    from openpyxl import Workbook
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='snapir-indexed-export-') as temporary,IndexedAnalysis(vault,progress=progress) as analysis:
        conn=sqlite3.connect(Path(temporary)/'report.sqlite')
        try:
            conn.executescript('''PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;
                CREATE TABLE operations(key TEXT PRIMARY KEY,channel TEXT,name TEXT);
                CREATE TABLE calls(ordinal INTEGER PRIMARY KEY,caller TEXT,callee TEXT,step TEXT,note TEXT);
                CREATE TABLE issues(ordinal INTEGER PRIMARY KEY,operation TEXT,step TEXT,detail TEXT);''')
            for kind,item in iter_indexed_connections(analysis.root,analysis,progress):
                if kind=='operation':conn.execute('INSERT INTO operations VALUES (?,?,?)',(item[0],item[1]['channel'],item[1]['operation_id']))
                elif kind=='call':conn.execute('INSERT INTO calls(caller,callee,step,note) VALUES (?,?,?,?)',tuple(item[key] for key in ('caller','callee','step','note')))
                else:conn.execute('INSERT INTO issues(operation,step,detail) VALUES (?,?,?)',tuple(item[key] for key in ('operation','step','detail')))
            if progress:progress('Calculating dependency waves with disk-backed traversal')
            index_waves(conn)
            counts={name:conn.execute('SELECT count(*) FROM '+name).fetchone()[0] for name in ('operations','calls','issues')}
            def plan_rows():
                for key,channel,name,wave,cycle,issue in conn.execute('SELECT key,channel,name,wave,cycle,issue FROM wave_rows ORDER BY wave IS NULL,wave,key'):
                    text=''
                    for (target,) in conn.execute('SELECT target FROM links WHERE caller=? ORDER BY target',(key,)):
                        if len(text)+len(target)+1>32000:
                            if not relationships:raise ValueError('Excel prerequisite list exceeds a cell limit; rerun with --include-relationships')
                            text+='\n... see Relationships';break
                        text+=('\n' if text else '')+target
                    yield [wave,channel,name,text or 'None',cycle or 'None',issue]
            workbook=Workbook(write_only=True)
            if progress:progress('Writing Excel workbook with bounded row buffers')
            streamed_sheet(workbook,'Migration Plan','Operation implementation order',
                'Dependencies first. Cycles require coordinated implementation; blank waves have unresolved dependencies.',
                ['Build wave','Channel','Operation','Implement after (direct)','Cycle group','Issue'],plan_rows(),[15,18,32,62,45,45],'MigrationPlanTable',counts['operations'],{1:'0'})
            streamed_sheet(workbook,'Operations','Operation inventory',
                'Counts are unique direct operation connections, not step counts or implementation effort.',
                ['Channel','Operation','Calls count','Callers count','Build wave','Cycle group'],
                conn.execute("SELECT channel,name,calls_count,callers_count,wave,CASE WHEN cycle='' THEN 'None' ELSE cycle END FROM wave_rows ORDER BY key"),
                [18,32,17,17,16,45],'OperationsTable',counts['operations'],{3:'#,##0',4:'#,##0',5:'#,##0'})
            if relationships:
                streamed_sheet(workbook,'Relationships','Operation call evidence','Filter Caller or Called operation. Multiple call sites are retained as evidence.',
                    ['Caller','Called operation','Invoking step','Mapper note'],conn.execute('SELECT caller,callee,step,note FROM calls ORDER BY ordinal'),[42,42,32,62],'RelationshipsTable',counts['calls'])
            if counts['issues']:
                streamed_sheet(workbook,'Issues','Unresolved operation relationships','Affected operations and their callers have no assigned build wave.',
                    ['Operation','Step','Issue'],conn.execute('SELECT operation,step,detail FROM issues ORDER BY ordinal'),[42,45,90],'IssuesTable',counts['issues'])
            staging=output.with_name(output.name+'.tmp')
            try:
                workbook.save(staging);staging.replace(output)
            finally:
                staging.unlink(missing_ok=True)
            return counts
        finally:
            conn.close()
