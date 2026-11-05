"""Check inventory liveness reporting and reporter cleanup without running intake."""

import logging
from threading import Event, enumerate as active_threads

import pytest

from runtime.intake_progress import component_inventory_progress


@pytest.mark.parametrize("fail", [False, True])
def test_inventory_reports_liveness_and_stops_on_exit(caplog, fail):
    heartbeat = Event()

    class HeartbeatHandler(logging.Handler):
        def emit(self, record):
            if "still running" in record.getMessage():
                heartbeat.set()

    logger = logging.getLogger("runtime.intake_progress")
    handler = HeartbeatHandler()
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.INFO, logger=logger.name):
            try:
                with component_inventory_progress(25000, interval_seconds=0.01):
                    assert heartbeat.wait(2), "Inventory heartbeat was not emitted"
                    if fail:
                        raise ValueError("inventory failed")
            except ValueError as exc:
                assert fail and str(exc) == "inventory failed"
        assert "25000 indexed Java source files in scope" in caplog.text
        assert "seconds elapsed" in caplog.text
        assert ("interrupted" if fail else "completed") in caplog.text
        assert not any(thread.name == "component-inventory-progress" for thread in active_threads())
    finally:
        logger.removeHandler(handler)
