"""Run scanner infrastructure with activity-based timeouts and visible progress."""
import queue
import subprocess
import threading
import time
from pathlib import Path


def run_process(command, environment, inactivity, *, cwd=None, log_path=None):
    """Drain child output; terminate after inactivity, not after a fixed overall runtime."""
    process = subprocess.Popen(command, env=environment, cwd=cwd, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    messages = queue.Queue()
    def read():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)
    threading.Thread(target=read, daemon=True).start()
    last = time.monotonic()
    lines = []
    log = Path(log_path).open('a', encoding='utf-8') if log_path else None
    try:
        while True:
            try:
                line = messages.get(timeout=min(1, inactivity))
            except queue.Empty:
                if time.monotonic() - last >= inactivity:
                    raise ValueError('Scanner stopped after ' + str(inactivity) + ' seconds without activity')
                continue
            if line is None:
                break
            # Only emitted scanner work advances its own activity timer.
            last = time.monotonic()
            lines.append(line)
            if log:
                log.write(line)
                log.flush()
            else:
                print(line.rstrip(), flush=True)
        result = process.wait(timeout=inactivity)
        if result:
            details = 'see ' + str(log_path) if log else ''.join(lines)[-3000:]
            raise ValueError('Scanner command failed (' + str(result) + '): ' + details)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        if log:
            log.close()
