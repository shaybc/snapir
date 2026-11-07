"""Verify disk-backed waves and both portable indexed workbook entry points."""

import importlib.util
from copy import copy
import os
from pathlib import Path
import random
import shutil
import sqlite3
import subprocess
import sys
import pytest

from tests.indexed_mapper_fixture import indexed_mapper_jar,generate,workspace,ROOT
from tools.operation_call_tools.indexed_waves import index_waves
from tools.operation_call_tools.ordering import operation_waves
from tools.operation_call_tools.indexed_export import export_indexed_workbook


@pytest.mark.parametrize('seed',range(8))
def test_disk_waves_match_existing_cycles_issues_and_order(seed):
    rng=random.Random(seed);keys=['A/'+str(i) for i in range(25)]
    graph=dict(operations={key:{} for key in keys},calls=[],issues=[])
    conn=sqlite3.connect(':memory:')
    conn.executescript('CREATE TABLE operations(key TEXT PRIMARY KEY,channel TEXT,name TEXT);CREATE TABLE calls(caller TEXT,callee TEXT);CREATE TABLE issues(operation TEXT);')
    conn.executemany('INSERT INTO operations VALUES (?,?,?)',((key,*key.split('/')) for key in keys))
    for _ in range(55):
        caller,target=rng.choice(keys),rng.choice(keys)
        graph['calls'].append(dict(caller=caller,callee=target));conn.execute('INSERT INTO calls VALUES (?,?)',(caller,target))
    for key in rng.sample(keys,3):graph['issues'].append(dict(operation=key));conn.execute('INSERT INTO issues VALUES (?)',(key,))
    index_waves(conn);expected=operation_waves(graph)
    for key,wave,cycle,issue,calls,callers in conn.execute('SELECT key,wave,cycle,issue,calls_count,callers_count FROM wave_rows'):
        actual=dict(wave=wave,cycle_group=cycle,issue=issue,calls_count=calls,callers_count=callers,
                    prerequisites=[row[0] for row in conn.execute('SELECT target FROM links WHERE caller=? ORDER BY target',(key,))])
        assert actual==expected[key]
    conn.close()


def test_indexed_workbooks_match_portable_and_existing_rows(tmp_path,indexed_mapper_jar):
    pytest.importorskip('openpyxl')
    root=workspace(tmp_path/'source');vault=tmp_path/'map';generate(indexed_mapper_jar,root,vault)
    output=tmp_path/'streamed.xlsx';counts=export_indexed_workbook(vault,output,True)
    assert counts==dict(operations=3,calls=0,issues=0)
    from tools.operation_call_tools.discovery import discover_operation_calls
    spec=importlib.util.spec_from_file_location('portable_report',ROOT/'Excel Generator.py')
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    from tools.composer_mapper_tools.mapped_scope import source_xml
    assert source_xml.__module__=='tools.composer_mapper_tools.mapped_scope'
    graph=discover_operation_calls(vault);expected=tmp_path/'expected.xlsx'
    module.write_workbook(graph,operation_waves(graph),expected,True)
    from openpyxl import load_workbook
    with_output=load_workbook(output);with_expected=load_workbook(expected)
    try:
        assert with_output.sheetnames==with_expected.sheetnames
        for name in with_output.sheetnames:
            assert list(with_output[name].values)==list(with_expected[name].values)
            assert list(with_output[name].tables)==list(with_expected[name].tables)
            for cell in with_output[name][5]:
                expected_cell=with_expected[name][cell.coordinate]
                assert copy(cell.font)==copy(expected_cell.font)
                assert copy(cell.fill)==copy(expected_cell.fill)
                assert copy(cell.alignment)==copy(expected_cell.alignment)
    finally:with_output.close();with_expected.close()
    isolated=tmp_path/'portable';isolated.mkdir();script=isolated/'Excel Generator.py';shutil.copy2(ROOT/'Excel Generator.py',script)
    result=subprocess.run([sys.executable,'-B',str(script),str(vault),'--output',str(tmp_path/'portable.xlsx')],
        cwd=isolated,env=dict(os.environ,PYTHONPATH=''),capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    result=subprocess.run([sys.executable,'-B',str(ROOT/'source/export_operation_migration.py'),'--vault',str(vault),
        '--output',str(tmp_path/'builtin.xlsx')],cwd=isolated,env=dict(os.environ,PYTHONPATH=''),capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
