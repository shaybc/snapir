"""Console summaries retain actionable identities while details remain in a persistent log."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library.discovery_reporting import missing_dependencies, print_summary, record_details, record_plan
from format_library.processes import run_process


def test_summary_deduplicates_dependencies_and_preserves_details(tmp_path, capsys):
    log = tmp_path / 'discovery.log'; log.write_text('')
    data = dict(detailed_log=str(log), classes={
        'example.String': dict(kind='format', abstract=False, framework=False, issues=['Type unresolved: Missing'],
            ancestry_status='resolved', dependency_status='analyzed', unresolved_dependencies=['vendor.Missing']),
        'example.Nil': dict(kind='decorator', abstract=False, framework=False, issues=[], unresolved_dependencies=['vendor.Missing']),
        'example.Unknown': dict(kind='support', abstract=False, framework=False, issues=['Ancestry unresolved: Base'],
            ancestry_status='unresolved', unresolved_dependencies=['vendor.Base']),
    }, projects=[dict(id='project', issues=['Missing JAR: absent.jar', 'Missing JAR: absent.jar'])],
        issues=[], groups=[])
    data['unresolved_dependencies'] = missing_dependencies(data)
    record_details(data)
    record_plan(data)
    print_summary(data)
    output = capsys.readouterr().out
    assert output.count('vendor.Missing') == 1
    assert output.count('Missing JAR: absent.jar') == 1
    assert 'format: example.String' in output and 'decorator: example.Nil' in output
    assert 'example.Unknown' not in output and 'Type unresolved' not in output
    assert str(log) in output
    assert 'example.Unknown' in log.read_text()


def test_scanner_output_goes_to_log_and_default_process_output_stays_visible(tmp_path, capsys):
    import os
    log = tmp_path / 'discovery.log'
    command = [sys.executable, '-c', 'print("Inspecting a class", flush=True)']
    run_process(command, os.environ.copy(), 10, log_path=log)
    assert capsys.readouterr().out == ''
    assert 'Inspecting a class' in log.read_text()
    run_process(command, os.environ.copy(), 10)
    assert 'Inspecting a class' in capsys.readouterr().out
