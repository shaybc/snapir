"""Verify boundary analyzer progress, inactivity failures, and buffered output."""

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
        assert kwargs['inactivity_timeout_seconds'] == 300
        assert 'timeout' not in kwargs
        line = 'Boundary progress +1.0s: project example loading JAR driver.jar'
        kwargs['output_log'].write_text(line + '\n', encoding='utf-8')
        kwargs['progress_filter'](line)
        kwargs['on_output'](line)
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
        line = 'Boundary progress +2.0s: entry example traversing reachable calls'
        kwargs['output_log'].write_text(line + '\n', encoding='utf-8')
        kwargs['progress_filter'](line)
        kwargs['on_output'](line)
        raise subprocess.TimeoutExpired(command, kwargs['inactivity_timeout_seconds'])
    with pytest.raises(ValueError, match='inactivity timeout after 300 seconds without meaningful progress; XML output bytes=0; last progress:.*traversing reachable calls'):
        run_with_progress(['java'], tmp_path / 'progress.log', runner)
    assert not any(thread.name == 'boundary-analysis-progress' for thread in active_threads())


def test_failure_preserves_java_stderr(tmp_path):
    def runner(command, **kwargs):
        kwargs['output_log'].write_text('Java failure details\n', encoding='utf-8')
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
                  'reachability traversal complete', 'writing reachable graph', 'reachable graph written',
                  'XML output bytes=', 'destination writes=', 'Boundary XML output final size:'):
        assert stage in caplog.text


def test_completed_output_size_is_measured_from_file(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    output = tmp_path / 'output.xml'
    def runner(command, **kwargs):
        kwargs['output_log'].write_text('', encoding='utf-8')
        output.write_bytes(b'<analysis/>')
        return subprocess.CompletedProcess(command, 0, '')
    run_with_progress(['java'], tmp_path / 'progress.log', runner, output_path=output)
    assert 'Boundary XML output final size: 11 bytes' in caplog.text


def test_heartbeat_reports_output_growth_while_analyzer_runs(tmp_path, caplog, monkeypatch):
    now = [0]
    monkeypatch.setattr('tools.behavior_verification.analysis_progress.monotonic', lambda: now[0])
    observed = Event()
    class Handler(logging.Handler):
        def emit(self, record):
            if 'growth since previous sample: 11 bytes' in record.getMessage():
                observed.set()
    logger = logging.getLogger('tools.behavior_verification.analysis_progress')
    handler = Handler()
    logger.addHandler(handler)
    caplog.set_level(logging.INFO)
    output = tmp_path / 'output.xml'
    def runner(command, **kwargs):
        assert kwargs['inactivity_timeout_seconds'] == 300
        assert 'timeout' not in kwargs
        kwargs['output_log'].write_text('', encoding='utf-8')
        output.write_bytes(b'<analysis/>')
        now[0] = 11
        assert observed.wait(5), 'Output growth was not logged during execution'
        return subprocess.CompletedProcess(command, 0, '')
    try:
        run_with_progress(['java'], tmp_path / 'progress.log', runner, output_path=output)
    finally:
        logger.removeHandler(handler)
    assert 'Boundary XML output: 11 bytes' in caplog.text


def test_buffer_batches_xml_writes_without_changing_bytes(boundary_tool, tmp_path):
    java = tmp_path / 'BufferedOutputCheck.java'
    java.write_text('''package il.co.dcd.verification;
import java.io.*;
import java.util.Arrays;
import javax.xml.stream.XMLOutputFactory;
public class BufferedOutputCheck {
    static class Destination extends ByteArrayOutputStream {
        int writes;
        public synchronized void write(int value) { writes++; super.write(value); }
        public synchronized void write(byte[] value, int offset, int length) {
            writes++; super.write(value, offset, length);
        }
    }
    static void render(OutputStream stream) throws Exception {
        var xml = XMLOutputFactory.newFactory().createXMLStreamWriter(stream, "UTF-8");
        xml.writeStartDocument(); xml.writeStartElement("analysis");
        for (int i = 0; i < 10000; i++) {
            xml.writeStartElement("node"); xml.writeAttribute("id", Integer.toString(i));
            xml.writeCharacters("text < & > " + Character.toString(0x03bb)); xml.writeEndElement();
        }
        xml.writeEndElement(); xml.writeEndDocument(); xml.close();
    }
    public static void main(String[] args) throws Exception {
        Destination direct = new Destination(), buffered = new Destination();
        render(direct);
        try (var stream = new BufferedAnalysisOutput(buffered)) { render(stream); }
        if (!Arrays.equals(direct.toByteArray(), buffered.toByteArray())) throw new AssertionError("XML changed");
        if (buffered.writes >= 20 || direct.writes <= buffered.writes * 100) throw new AssertionError("Writes not batched");
        System.out.println("identical XML; bytes=" + buffered.size() + "; direct writes=" + direct.writes + "; buffered writes=" + buffered.writes);
    }
}''')
    compilation = run_java(['javac', '-cp', str(boundary_tool), '-d', str(tmp_path), str(java)],
                           capture_output=True, text=True, timeout=60)
    assert compilation.returncode == 0, compilation.stderr
    result = run_java(['java', '-cp', str(tmp_path) + os.pathsep + str(boundary_tool),
                       'il.co.dcd.verification.BufferedOutputCheck'], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'identical XML; bytes=' in result.stdout
    assert 'XML output bytes=' in result.stderr


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
