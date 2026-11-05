"""Exercise real process activity, idle termination, scanner errors, and per-run settings."""

import logging
import subprocess
import sys

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.java_process_activity import run_with_activity_timeout
from runtime.java_toolchain import java_scan_inactivity_timeout, java_scope
from tools.java_analysis_tools.source_dependencies import parser


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_active_process_can_exceed_timeout_even_without_newlines(stream, caplog):
    script = ("import sys,time; "
              f"[(getattr(sys,'{stream}').write('working'),getattr(sys,'{stream}').flush(),time.sleep(.2)) for _ in range(8)]")
    with caplog.at_level(logging.INFO, logger="runtime.java_process_activity"):
        result = run_with_activity_timeout([sys.executable, "-u", "-c", script], inactivity_timeout_seconds=1)
    assert result.returncode == 0
    assert getattr(result, stream) == "working" * 8
    assert "working" in caplog.text


def test_result_file_activity_resets_timeout(tmp_path):
    path = tmp_path / "references.xml"
    script = ("import pathlib,time; p=pathlib.Path(" + repr(str(path)) + "); "
              "[(p.write_text(str(i)),time.sleep(.2)) for i in range(8)]")
    result = run_with_activity_timeout([sys.executable, "-u", "-c", script],
        inactivity_timeout_seconds=1, activity_path=path)
    assert result.returncode == 0
    assert path.read_text() == "7"


def test_idle_process_is_killed_and_reaped(monkeypatch):
    real_popen = subprocess.Popen
    processes = []
    def launch(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(subprocess, "Popen", launch)
    with pytest.raises(subprocess.TimeoutExpired):
        run_with_activity_timeout([sys.executable, "-u", "-c", "import time; print('started'); time.sleep(60)"],
            inactivity_timeout_seconds=1)
    assert processes[0].poll() is not None
    assert processes[0].stdout.closed and processes[0].stderr.closed


def test_nonzero_exit_retains_diagnostics():
    result = run_with_activity_timeout([sys.executable, "-c", "import sys; sys.stderr.write('bad source'); sys.exit(7)"],
        inactivity_timeout_seconds=2)
    assert result.returncode == 7
    assert result.stderr == "bad source"


@pytest.mark.parametrize("failure, message", [
    (FileNotFoundError("java executable missing"), "Could not launch or access the JDK"),
    (PermissionError("java access denied"), "Could not launch or access the JDK"),
    (subprocess.TimeoutExpired("java", 900), "900 seconds without output or result-file activity"),
])
def test_scanner_distinguishes_launch_and_inactivity_errors(tmp_path, monkeypatch, failure, message):
    (tmp_path / "Example.java").write_text("public class Example {}")
    def fail(*args, **kwargs):
        assert "timeout" not in kwargs
        assert kwargs["inactivity_timeout_seconds"] == 900
        raise failure
    monkeypatch.setattr(parser, "run_java", fail)
    with pytest.raises(ValueError, match=message) as caught:
        parser.parse_source_references([tmp_path / "Example.java"])
    assert caught.value.__cause__ is failure


def test_scanner_setting_is_scoped_and_restored(tmp_path, monkeypatch):
    from tests.test_run_java_toolchain import jdk
    from runtime.java_toolchain import run_java
    home = jdk(tmp_path, 25)
    profile = PipelineConfiguration(java_home=home, java_scan_inactivity_timeout_seconds=1800)
    calls = []
    monkeypatch.setattr("runtime.java_process_activity.run_with_activity_timeout",
                        lambda command, **kwargs: calls.append((command, kwargs)))
    with java_scope(profile):
        assert java_scan_inactivity_timeout() == 1800
        run_java(["java", "Scanner.java"], inactivity_timeout_seconds=java_scan_inactivity_timeout())
    assert java_scan_inactivity_timeout() == 900
    assert calls[0][0][0].startswith(home)
    assert calls[0][1]["inactivity_timeout_seconds"] == 1800
    assert calls[0][1]["env"]["JAVA_HOME"] == home


def test_scanner_timeout_prompt_retries_invalid_values():
    from cli.java_configuration import collect_java_scan_timeout
    answers = iter(["0", "-1", "bad", "1.5", "1200"])
    assert collect_java_scan_timeout(lambda *_: next(answers)) == 1200
    assert collect_java_scan_timeout(lambda title, default: default) == 900
    with pytest.raises(ValueError):
        PipelineConfiguration(java_scan_inactivity_timeout_seconds=0)


def test_real_jdk_scanner_emits_progress_and_preserves_reference_output(tmp_path, caplog):
    from runtime.java_toolchain import resolve_java_home
    try:
        home = resolve_java_home(25)
    except ValueError:
        pytest.skip("JDK 25 is not installed")
    source = tmp_path / "Example.java"
    source.write_text("package sample; public class Example { String value; }")
    with java_scope(PipelineConfiguration(java_home=home)):
        with caplog.at_level(logging.INFO, logger="runtime.java_process_activity"):
            analysis = parser.parse_source_references([source])
    assert analysis.find("source").get("package") == "sample"
    assert analysis.find("source/reference") is not None
    assert "Parsed 1/1 Java files" in caplog.text
    assert "Scanned references in 1/1 Java files" in caplog.text
