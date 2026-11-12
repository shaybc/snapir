"""Capture scanner output while enforcing inactivity rather than total runtime."""

import codecs
import locale
import logging
import os
from pathlib import Path
from queue import Empty, Full, Queue
import subprocess
from threading import Event, Thread
from time import monotonic

from runtime.model_execution.error_details import sanitize_diagnostic


def run_with_activity_timeout(command, *, inactivity_timeout_seconds, activity_path=None,
                              capture_output=True, text=True, check=False, output_log=None, on_output=None,
                              progress_filter=None, activity_growth_only=False, log_output=True, **kwargs):
    """Stream captured output and stop a child only after no observable progress.

    By default, output bytes and result-file size/mtime changes reset the timer.
    A progress filter can restrict output to meaningful lines; growth-only mode
    ignores file touches. The child is reaped on every exit path.
    """
    if inactivity_timeout_seconds <= 0:
        raise ValueError("Scanner inactivity timeout must be positive")
    logger = logging.getLogger(__name__)
    events = Queue(maxsize=64)
    stopped = Event()
    output = Path(output_log).open('wb') if output_log is not None else None
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    except BaseException:
        if output is not None:
            output.close()
        raise
    buffers = {"stdout": [], "stderr": []}
    decoders = {name: codecs.getincrementaldecoder(locale.getpreferredencoding(False))(errors="replace")
                for name in buffers}
    pending = {name: "" for name in buffers}

    def read_output(name, pipe):
        def emit(chunk):
            while not stopped.is_set():
                try:
                    events.put((name, chunk, monotonic()), timeout=0.2)
                    return
                except Full:
                    continue
        try:
            while chunk := os.read(pipe.fileno(), 65536):
                emit(chunk)
        finally:
            emit(None)

    readers = [Thread(target=read_output, args=(name, getattr(process, name)), daemon=True,
                      name="java-scanner-" + name) for name in buffers]
    last_activity = monotonic()
    last_file_state = None
    closed = set()
    peak_memory = 0
    try:
        for reader in readers:
            reader.start()
        while len(closed) < 2 or process.poll() is None:
            from runtime.resource_usage import memory_usage
            peak_memory = max(peak_memory, memory_usage(process.pid).get('python_peak_rss_bytes', 0))
            try:
                name, chunk, observed = events.get(timeout=min(0.2, inactivity_timeout_seconds))
            except Empty:
                chunk = None
                name = None
            if name is not None:
                if chunk is None:
                    closed.add(name)
                    decoded = decoders[name].decode(b"", final=True)
                else:
                    if capture_output:
                        buffers[name].append(chunk)
                    if output is not None:
                        output.write(chunk)
                        output.flush()
                    if progress_filter is None:
                        last_activity = max(last_activity, observed)
                    decoded = decoders[name].decode(chunk)
                pending[name] += decoded
                while "\n" in pending[name]:
                    line, pending[name] = pending[name].split("\n", 1)
                    line = line.rstrip('\r')
                    if progress_filter is not None and progress_filter(line):
                        last_activity = max(last_activity, observed)
                    if log_output: logger.info("Java dependency scanner: %s", sanitize_diagnostic(line))
                    if on_output is not None:
                        on_output(line)
                if name in closed and pending[name]:
                    if progress_filter is not None and progress_filter(pending[name]):
                        last_activity = max(last_activity, observed)
                    if log_output: logger.info("Java dependency scanner: %s", sanitize_diagnostic(pending[name]))
                    if on_output is not None and progress_filter is not None: on_output(pending[name])
                    pending[name] = ""
                if len(pending[name]) > 16384:
                    if log_output: logger.info('Java dependency scanner: %s', sanitize_diagnostic(pending[name][:16384]))
                    pending[name] = pending[name][16384:]
            if activity_path is not None:
                try:
                    stat = Path(activity_path).stat()
                    state = (stat.st_size, stat.st_mtime_ns)
                except FileNotFoundError:
                    state = None
                if state is not None and (state[0] > (last_file_state[0] if last_file_state else 0)
                        if activity_growth_only else state != last_file_state):
                    last_activity = monotonic()
                if not activity_growth_only or state is not None and (last_file_state is None or state[0] > last_file_state[0]):
                    last_file_state = state
            if process.poll() is None and monotonic() - last_activity >= inactivity_timeout_seconds:
                error = subprocess.TimeoutExpired(command, inactivity_timeout_seconds)
                error.inactive_seconds = monotonic() - last_activity
                raise error
        returncode = process.wait()
    finally:
        stopped.set()
        if process.poll() is None:
            process.kill()
        process.wait()
        for reader in readers:
            if reader.ident is not None:
                reader.join()
        process.stdout.close()
        process.stderr.close()
        if output is not None:
            output.close()
        logger.info('Java scanner maximum observed resident memory: %s bytes.', peak_memory)
    outputs = {name: b"".join(chunks) for name, chunks in buffers.items()}
    if text:
        outputs = {name: value.decode(locale.getpreferredencoding(False), errors="replace")
                   for name, value in outputs.items()}
    result = subprocess.CompletedProcess(command, returncode, outputs["stdout"], outputs["stderr"])
    if check:
        result.check_returncode()
    return result
