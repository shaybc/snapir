"""Expose current preparation activity without counting heartbeat messages as work."""

import logging
from threading import Event, enumerate as threads
import pytest
from runtime.preparation_progress import preparation_progress, report_preparation


@pytest.mark.parametrize('fail', [False, True])
def test_preparation_heartbeat_names_current_task_and_stops(caplog, fail):
    seen = Event()
    class Heartbeat(logging.Handler):
        def emit(self, record):
            if 'still running' in record.getMessage() and 'Reading selected project' in record.getMessage():
                seen.set()
    logger = logging.getLogger('runtime.preparation_progress')
    handler = Heartbeat()
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.INFO, logger=logger.name):
            try:
                with preparation_progress('Preparation', interval_seconds=0.01):
                    report_preparation('Reading selected project')
                    assert seen.wait(2)
                    if fail:
                        raise ValueError('fixture failure')
            except ValueError:
                assert fail
        assert ('interrupted' if fail else 'completed') in caplog.text
        assert not any(thread.name == 'preparation-progress' for thread in threads())
    finally:
        logger.removeHandler(handler)
