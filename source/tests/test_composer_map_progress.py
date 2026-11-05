"""Verify visible map validation before intake and progress cleanup on errors."""

import logging
import json
from threading import Event, enumerate as active_threads

import pytest

from runtime.composer_map_progress import composer_map_validation_progress
from tools.workspace_intake_tools.vault_validator import validate_existing_composer_map
from runtime.composer_map_estimate import ComposerMapEstimate, format_duration


@pytest.mark.parametrize("fail", [False, True])
def test_map_validation_reports_while_busy_and_cleans_up(caplog, fail):
    heartbeat = Event()
    logger = logging.getLogger("runtime.composer_map_progress")

    class HeartbeatHandler(logging.Handler):
        def emit(self, record):
            if "still running" in record.getMessage():
                heartbeat.set()

    handler = HeartbeatHandler()
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.INFO, logger=logger.name):
            try:
                with composer_map_validation_progress("external-map", interval_seconds=0.01) as report:
                    report("Validated 250 notes")
                    assert heartbeat.wait(2)
                    if fail:
                        raise ValueError("invalid map")
            except ValueError as exc:
                assert fail and str(exc) == "invalid map"
        assert "Validating existing Composer map: external-map" in caplog.text
        assert "before a migration workspace is created" in caplog.text
        assert "Validated 250 notes" in caplog.text
        assert ("interrupted" if fail else "completed") in caplog.text
        assert not any(thread.name == "composer-map-validation-progress" for thread in active_threads())
    finally:
        logger.removeHandler(handler)


@pytest.mark.parametrize("channel", ["WEB", "MISSING"])
def test_existing_map_forwards_note_progress_and_keeps_channel_validation(tmp_path, monkeypatch, caplog, channel):
    def read(root, *, retain_inventory, allow_shared, progress):
        assert retain_inventory is False and allow_shared is True
        progress("Validated 250 notes: channels/WEB/example.md")
        return dict(entities=[dict(channel="WEB", operation_id="Example")])
    monkeypatch.setattr("tools.composer_mapper_tools.vault_manifest.read_vault_manifest", read)
    with caplog.at_level(logging.INFO, logger="runtime.composer_map_progress"):
        if channel == "MISSING":
            with pytest.raises(ValueError, match="missing selected channels"):
                validate_existing_composer_map(str(tmp_path), [channel])
        else:
            validate_existing_composer_map(str(tmp_path), [channel])
    assert "Validated 250 notes" in caplog.text
    assert list(tmp_path.iterdir()) == []


def test_estimate_waits_then_uses_recent_batch_speed():
    estimate = ComposerMapEstimate(2000, started=0)
    assert "after 250 notes" in estimate.update(1, now=1)
    assert "~1m 10s" in estimate.update(250, now=10)
    assert "~1m 30s" in estimate.update(500, now=30)
    for count, time in [(750, 40), (1000, 50), (1250, 60), (1500, 70), (1750, 80)]:
        message = estimate.update(count, now=time)
    assert "~0m 10s" in message
    assert "Finalizing validation" in estimate.update(2000, now=90)
    assert "Estimated remaining" not in estimate.update(2000, now=100)


@pytest.mark.parametrize("total", [0, 1, 249])
def test_small_maps_finish_without_division_or_false_eta(total):
    message = ComposerMapEstimate(total, started=0).update(total, now=1)
    assert "Finalizing validation" in message
    assert "Estimated remaining" not in message


def test_manifest_count_and_estimate_are_visible_without_modifying_map(tmp_path, caplog):
    manifest = tmp_path / "vault-manifest.json"
    manifest.write_text(json.dumps(dict(entities=[{} for _ in range(1000)])))
    before = manifest.read_bytes()
    with caplog.at_level(logging.INFO, logger="runtime.composer_map_progress"):
        with composer_map_validation_progress(tmp_path) as report:
            report("Validated 250 notes: example.md")
            report("Finalizing validation after checking 1000 notes")
    assert "Counting manifest notes: 250 found" in caplog.text
    assert "Manifest count complete: 1,000 notes" in caplog.text
    assert "Validated 250 / 1,000 notes (25%)" in caplog.text
    assert "Estimated remaining: ~" in caplog.text
    assert "Finalizing validation after checking 1000 notes" in caplog.text
    assert manifest.read_bytes() == before


def test_invalid_manifest_count_stops_reporter(tmp_path):
    (tmp_path / "vault-manifest.json").write_text('{"entities": [')
    with pytest.raises(ValueError):
        with composer_map_validation_progress(tmp_path):
            pytest.fail("Invalid manifest must not start note validation")
    assert not any(thread.name == "composer-map-validation-progress" for thread in active_threads())


def test_duration_format_and_changed_manifest_count():
    assert format_duration(3661) == "1h 1m"
    assert "remaining time unavailable" in ComposerMapEstimate(1).update(2)
