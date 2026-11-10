"""Verify analyzer progress survives failures and the five-minute limit stays fixed."""

import logging
import os
import subprocess
from threading import Event, enumerate as active_threads

import pytest

from tools.behavior_verification.analysis_progress import run_with_progress
from test_behavior_verification_boundaries import boundary_tool, prepared, unit
from tools.behavior_verification.boundaries import build_boundary_report
from runtime.java_toolchain import run_java


def test_progress_is_logged_before_analyzer_returns(tmp_path, caplog):
    observed = Event()
    class Handler(logging.Handler):
        def emit(self, record):
            if 'loading JAR driver.jar' in record.getMessage():
                observed.set()
    logger = logging.getLogger('tools.behavior_verification.analysis_progress')
    handler = Handler()
    logger.addHandler(handler)
    caplog.set_level(logging.INFO)
    def runner(command, **kwargs):
        assert kwargs['timeout'] == 300
        kwargs['stderr'].write(b'Boundary progress +1.0s: loading JAR driver.jar\n')
        kwargs['stderr'].flush()
        assert observed.wait(5), 'Progress was buffered until process exit'
        return subprocess.CompletedProcess(command, 0, '')
    try:
        result = run_with_progress(['java'], tmp_path / 'progress.log', runner)
    finally:
        logger.removeHandler(handler)
    assert 'loading JAR driver.jar' in result.stderr
    assert 'exit code: 0' in caplog.text


def test_timeout_retains_last_stage_without_waiting_five_minutes(tmp_path):
    def runner(command, **kwargs):
        kwargs['stderr'].write(b'Boundary progress +2.0s: traversing reachable calls\n')
        kwargs['stderr'].flush()
        raise subprocess.TimeoutExpired(command, kwargs['timeout'])
    with pytest.raises(ValueError, match='timed out after 300 seconds; last progress:.*traversing reachable calls'):
        run_with_progress(['java'], tmp_path / 'progress.log', runner)
    assert not any(thread.name == 'boundary-analysis-progress' for thread in active_threads())


def test_failure_preserves_java_stderr(tmp_path):
    def runner(command, **kwargs):
        kwargs['stderr'].write(b'Java failure details\n')
        kwargs['stderr'].flush()
        return subprocess.CompletedProcess(command, 1, '')
    assert run_with_progress(['java'], tmp_path / 'progress.log', runner).stderr == 'Java failure details\n'


def test_real_analyzer_reports_stages_without_changing_boundary_result(boundary_tool, caplog):
    caplog.set_level(logging.INFO)
    report = build_boundary_report(prepared(unit()), tool_jar=boundary_tool)
    assert report['counts']['identified'] == 1
    for stage in ('reading input manifest', 'parsing source work', 'indexing source catalog',
                  'traversing reachable calls', 'reachable node', 'extracting parser checklist',
                  'extracting basic checklist', 'entry complete', 'class=example.Work',
                  'method=example.Work.execute()', 'source=work', 'node complete',
                  'reachability traversal complete', 'writing reachable graph', 'reachable graph written'):
        assert stage in caplog.text


def test_slow_operation_reports_context_and_live_java_stack(boundary_tool, tmp_path):
    java = tmp_path / 'SlowOperation.java'
    java.write_text('''package il.co.dcd.verification;
public class SlowOperation {
    public static void main(String[] args) throws Exception {
        try (var node = NodeProcessingProgress.operation("class=example.Work; method=execute")) {
            try (var operation = NodeProcessingProgress.operation("explicit binding MethodCallExpr line=42")) {
                Thread.sleep(6500);
            }
        }
    }
}''')
    compilation = run_java(['javac', '-cp', str(boundary_tool), '-d', str(tmp_path), str(java)],
                           capture_output=True, text=True, timeout=60)
    assert compilation.returncode == 0, compilation.stderr
    result = run_java(['java', '-cp', str(tmp_path) + os.pathsep + str(boundary_tool),
                       'il.co.dcd.verification.SlowOperation'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    for detail in ('slow operation', 'class=example.Work; method=execute',
                   'explicit binding MethodCallExpr line=42', 'operation elapsed=',
                   'stack=', 'SlowOperation.main'):
        assert detail in result.stderr
