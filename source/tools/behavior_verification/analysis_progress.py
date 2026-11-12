"""Monitor boundary-analysis inactivity while retaining progress and failure context."""
import logging
import subprocess
from threading import Event, Thread
from time import monotonic
from runtime.java_toolchain import boundary_analysis_inactivity_timeout
from tools.behavior_verification.analysis_activity import AnalysisActivity
from tools.behavior_verification.analysis_failure import BoundaryAnalysisFailure


def run_with_progress(command, progress_path, runner, *, output_path=None, inactivity_timeout_seconds=None):
    """Run without a total deadline; only advancing work or output growth resets inactivity."""
    logger = logging.getLogger(__name__)
    limit = boundary_analysis_inactivity_timeout() if inactivity_timeout_seconds is None else inactivity_timeout_seconds
    if limit <= 0: raise ValueError('Boundary analysis inactivity timeout must be positive')
    stopped = Event()
    started = monotonic()
    activity = AnalysisActivity()

    def output_size():
        try: return output_path.stat().st_size if output_path is not None else 0
        except OSError: return 0

    def output(line):
        logger.info('%s', line)

    def monitor():
        heartbeat = started
        previous_size = 0
        while not stopped.wait(0.2):
            if monotonic() - heartbeat >= 10:
                size = output_size()
                if size > previous_size: activity.last_activity = monotonic()
                logger.info('Boundary analyzer running: %.1fs elapsed; %.1fs since observable progress; last progress: %s',
                    monotonic() - started, monotonic() - activity.last_activity, activity.last_progress)
                logger.info('Boundary XML output: %s bytes; growth since previous sample: %s bytes', size, size - previous_size)
                previous_size = max(previous_size, size)
                heartbeat = monotonic()

    logger.info('Starting boundary analyzer; inactivity timeout: %s seconds; no total runtime limit', limit)
    progress_path.write_bytes(b'')
    watcher = Thread(target=monitor, daemon=True, name='boundary-analysis-progress')
    watcher.start()
    try:
        result = runner(command, capture_output=True, text=True, check=False,
            inactivity_timeout_seconds=limit, progress_filter=activity.observe, activity_path=output_path,
            activity_growth_only=True, output_log=progress_path, on_output=output, log_output=False)
    except subprocess.TimeoutExpired as error:
        elapsed = monotonic() - started
        message = ('Converter boundary analysis inactivity timeout after ' + format(limit, 'g') +
            ' seconds without meaningful progress; XML output bytes=' + str(output_size()) +
            '; last progress: ' + activity.last_progress)
        raise BoundaryAnalysisFailure(message, inactivity_timeout_seconds=limit,
            inactive_seconds=getattr(error, 'inactive_seconds', limit), elapsed_seconds=elapsed,
            output_bytes=output_size(), last_progress=activity.last_progress,
            last_diagnostic=activity.last_diagnostic) from error
    finally:
        stopped.set()
        watcher.join()
    result.stderr = progress_path.read_text(encoding='utf-8', errors='replace')
    logger.info('Boundary analyzer exited after %.1fs; exit code: %s', monotonic() - started, result.returncode)
    logger.info('Boundary XML output final size: %s bytes', output_size())
    return result
