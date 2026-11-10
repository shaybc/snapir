"""Stream analyzer stage messages while preserving its fixed total runtime limit."""

import logging
import subprocess
from threading import Event, Thread
from time import monotonic


def run_with_progress(command, progress_path, runner):
    """Capture stderr on disk, log live stages, and retain the last stage on timeout."""
    logger = logging.getLogger(__name__)
    stopped = Event()
    started = monotonic()
    last_progress = 'waiting for Java analyzer startup'

    def monitor():
        nonlocal last_progress
        heartbeat = started
        last_stage_time = started
        with progress_path.open(encoding='utf-8', errors='replace') as stream:
            while True:
                for line in stream:
                    if line.startswith('Boundary progress '):
                        last_progress = line.strip()
                        last_stage_time = monotonic()
                        logger.info('%s', last_progress)
                if stopped.is_set():
                    return
                if monotonic() - heartbeat >= 10:
                    logger.info('Boundary analyzer running: %.1fs elapsed; %.1fs since last stage; last progress: %s',
                                monotonic() - started, monotonic() - last_stage_time, last_progress)
                    heartbeat = monotonic()
                stopped.wait(0.2)

    logger.info('Starting boundary analyzer; total timeout: 300 seconds')
    with progress_path.open('wb') as output:
        watcher = Thread(target=monitor, daemon=True, name='boundary-analysis-progress')
        watcher.start()
        try:
            result = runner(command, stdout=subprocess.PIPE, stderr=output,
                            text=True, timeout=300, check=False)
        except subprocess.TimeoutExpired as error:
            stopped.set()
            watcher.join()
            raise ValueError('Converter boundary analysis timed out after 300 seconds; '
                             'last progress: ' + last_progress) from error
        finally:
            stopped.set()
            watcher.join()
    result.stderr = progress_path.read_text(encoding='utf-8', errors='replace')
    logger.info('Boundary analyzer exited after %.1fs; exit code: %s',
                monotonic() - started, result.returncode)
    return result
