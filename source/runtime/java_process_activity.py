"""Capture scanner output while enforcing inactivity rather than total runtime."""

import codecs
import locale
import logging
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
from threading import Thread
from time import monotonic

from runtime.model_execution.error_details import sanitize_diagnostic


def run_with_activity_timeout(command, *, inactivity_timeout_seconds, activity_path=None,
                              capture_output=True, text=True, check=False, **kwargs):
    """Stream captured output and stop a child only after no observable progress.

    Output bytes and result-file size/mtime changes reset the timer. Console
    heartbeats and elapsed runtime do not. The child is reaped on every exit path.
    """
    if inactivity_timeout_seconds <= 0:
        raise ValueError("Scanner inactivity timeout must be positive")
    logger = logging.getLogger(__name__)
    events = Queue()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    buffers = {"stdout": [], "stderr": []}
    decoders = {name: codecs.getincrementaldecoder(locale.getpreferredencoding(False))(errors="replace")
                for name in buffers}
    pending = {name: "" for name in buffers}

    def read_output(name, pipe):
        try:
            while chunk := os.read(pipe.fileno(), 65536):
                events.put((name, chunk, monotonic()))
        finally:
            events.put((name, None, monotonic()))

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
                    buffers[name].append(chunk)
                    last_activity = max(last_activity, observed)
                    decoded = decoders[name].decode(chunk)
                pending[name] += decoded
                while "\n" in pending[name]:
                    line, pending[name] = pending[name].split("\n", 1)
                    logger.info("Java dependency scanner: %s", sanitize_diagnostic(line.rstrip("\r")))
                if name in closed and pending[name]:
                    logger.info("Java dependency scanner: %s", sanitize_diagnostic(pending[name]))
                    pending[name] = ""
            if activity_path is not None:
                try:
                    stat = Path(activity_path).stat()
                    state = (stat.st_size, stat.st_mtime_ns)
                except FileNotFoundError:
                    state = None
                if state is not None and state != last_file_state:
                    last_activity = monotonic()
                last_file_state = state
            if process.poll() is None and monotonic() - last_activity >= inactivity_timeout_seconds:
                raise subprocess.TimeoutExpired(command, inactivity_timeout_seconds)
        returncode = process.wait()
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for reader in readers:
            if reader.ident is not None:
                reader.join()
        process.stdout.close()
        process.stderr.close()
        logger.info('Java scanner maximum observed resident memory: %s bytes.', peak_memory)
    outputs = {name: b"".join(chunks) for name, chunks in buffers.items()}
    if text:
        outputs = {name: value.decode(locale.getpreferredencoding(False), errors="replace")
                   for name, value in outputs.items()}
    result = subprocess.CompletedProcess(command, returncode, outputs["stdout"], outputs["stderr"])
    if check:
        result.check_returncode()
    return result
