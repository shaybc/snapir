"""Check inventory liveness reporting and reporter cleanup without running intake."""

import logging
import json
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
        assert "workspace index=25000 Java files" in caplog.text
        assert "seconds elapsed" in caplog.text
        assert ("interrupted" if fail else "completed") in caplog.text
        assert not any(thread.name == "component-inventory-progress" for thread in active_threads())
    finally:
        logger.removeHandler(handler)


def test_inventory_progress_persists_real_phase_counts_and_log(tmp_path, caplog):
    with caplog.at_level(logging.INFO, logger='runtime'):
        with component_inventory_progress(5346, interval_seconds=0.01, log_directory=tmp_path) as work:
            work.stage('Selected dependency evidence', 10)
            work.advance(3, detail='CHANNEL/Operation')
            work.current('CHANNEL/NextOperation')
    snapshot = json.loads((tmp_path / 'intake-progress.json').read_text())
    assert snapshot['phase'] == 'Selected dependency evidence'
    assert snapshot['completed'] == 3 and snapshot['total'] == 10
    assert snapshot['detail'] == 'CHANNEL/NextOperation'
    assert snapshot['status'] == 'completed'
    assert 'Selected dependency evidence' in (tmp_path / 'intake.log').read_text()
    assert not any(isinstance(handler, logging.FileHandler) and handler.baseFilename.endswith('intake.log')
                   for handler in logging.getLogger('runtime').handlers)


def test_idle_work_captures_stack_evidence_without_aborting(tmp_path, monkeypatch):
    from runtime.inventory_work import InventoryWork
    work = InventoryWork(tmp_path)
    work.stage('Computing sharing counts', 10)
    work.last_work -= 121
    work.last_stack -= 121
    captured = []
    monkeypatch.setattr('runtime.inventory_work.faulthandler.dump_traceback', lambda **kwargs: captured.append(kwargs['all_threads']))
    work.persist()
    assert captured == [True]
    assert 'Computing sharing counts' in (tmp_path / 'intake-stacks.log').read_text()
