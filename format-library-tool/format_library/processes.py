"""Run scanner infrastructure with activity-based timeouts and visible progress."""
import queue
import subprocess
import threading
import time


def run_process(command, environment, inactivity, *, cwd=None):
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
            print(line.rstrip(), flush=True)
        result = process.wait(timeout=inactivity)
        if result:
            raise ValueError('Scanner command failed (' + str(result) + '): ' + ''.join(lines)[-3000:])
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
