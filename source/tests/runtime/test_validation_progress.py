"""Check numbered post-model progress and console warning separation."""

import json
import logging
import pytest
from cli.diagnostics import _ConsoleFormatter
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.generation import generate
from runtime.behavior_conversion.runner import _bundle_validator
from runtime.behavior_conversion.validation_progress import begin_progress, end_progress, progress_step
from runtime.behavior_conversion.validation import build_candidate
from tests.runtime.test_behavior_conversion import state, profile, bundle, factory, Verifier


def test_native_response_logs_validation_dependencies_compile_and_tests_in_order(tmp_path, caplog):
    conn, config = state()
    settings = profile()
    validator = _bundle_validator(conn, config, settings, tmp_path / "candidate", "step", (),
        {"calculation": "Calculate"}, ["original"], factory(Verifier()))
    caplog.set_level(logging.INFO)
    generate(conn, config, settings, "unit", "step", "Convert", {"requirements": {"calculation": "Calculate"}},
        NativeUnitBundle, validator=validator, model_call=lambda *_: bundle().model_dump_json(), label="Unit 1/17: Step")
    messages = [record.getMessage() for record in caplog.records if record.name.endswith("validation_progress")]
    assert len(messages) == 12
    assert [int(message.split(".", 1)[0]) for message in messages] == list(range(1, 13))
    for message in messages:
        assert "Unit 1/17: Step" in message and "step " in message and "elapsed " in message
    descriptions = [message for message in messages if "started." in message]
    assert "Validating JSON" in descriptions[0]
    assert "method contracts" in descriptions[1]
    assert "Preparing temporary Maven" in descriptions[2]
    assert "Resolving and verifying dependencies" in descriptions[3]
    assert "Compiling Java" in descriptions[4]
    assert "Running tests" in descriptions[5]
    assert all("completed." in message for message in messages[1::2])


def test_correction_restarts_numbering_and_reports_compile_failure(tmp_path, caplog):
    conn, config = state()
    settings = profile()
    verifier = Verifier(failing=True)
    validator = _bundle_validator(conn, config, settings, tmp_path / "candidate", "step", (),
        {"calculation": "Calculate"}, ["original"], factory(verifier))
    calls = []
    def model(instruction, encoded):
        calls.append(json.loads(encoded))
        if len(calls) == 2:
            verifier.failing = False
        return bundle().model_dump_json()
    caplog.set_level(logging.INFO)
    generate(conn, config, settings, "unit", "step", "Convert", {"requirements": {"calculation": "Calculate"}},
        NativeUnitBundle, validator=validator, model_call=model, label="Unit 7/17: Step")
    messages = [record.getMessage() for record in caplog.records if record.name.endswith("validation_progress")]
    assert sum(message.startswith("1. ") for message in messages) == 2
    assert any("Compiling Java sources failed." in message for message in messages)
    assert "correction_feedback" in calls[1]
    count = len(messages)
    with progress_step("Outside the unit"):
        pass
    assert len([record for record in caplog.records if record.name.endswith("validation_progress")]) == count


def test_elapsed_time_and_exception_cleanup(monkeypatch, caplog):
    clock = iter(range(30))
    monkeypatch.setattr("runtime.behavior_conversion.validation_progress.monotonic", lambda: next(clock))
    caplog.set_level(logging.INFO)
    token = begin_progress("Unit 2/17: Format")
    try:
        with pytest.raises(ValueError, match="invalid"):
            with progress_step("Validating JSON"):
                raise ValueError("invalid")
    finally:
        end_progress(token)
    messages = [record.getMessage() for record in caplog.records]
    assert "1. Validating JSON started." in messages[0]
    assert "2. Validating JSON failed." in messages[1]
    assert "step 3.0s; elapsed 5.0s" in messages[1]


def test_missing_test_execution_is_logged_as_failure(tmp_path, caplog):
    settings = profile()
    context = factory(Verifier(skipped=True))(settings, tmp_path, "candidate")
    caplog.set_level(logging.INFO)
    token = begin_progress("Unit 10/17: Step")
    try:
        result = build_candidate(tmp_path, context)
    finally:
        end_progress(token)
    assert result.build_passed and not result.tests_passed
    assert any("Running tests and checking execution reports failed." in record.getMessage() for record in caplog.records)


@pytest.mark.parametrize("verbose", [False, True])
def test_warning_is_visually_separated_without_changing_record(verbose):
    formatter = _ConsoleFormatter(verbose)
    record = logging.LogRecord("runtime", logging.WARNING, __file__, 1, "Retry %s", ("Step",), None)
    assert formatter.format(record) == "\n!! WARNING: Retry Step\n"
    assert record.getMessage() == "Retry Step"
    info = logging.LogRecord("runtime", logging.INFO, __file__, 1, "Progress", (), None)
    assert formatter.format(info) == "INFO: Progress"
