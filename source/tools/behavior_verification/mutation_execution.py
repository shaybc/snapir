"""Bounded Maven/PIT process execution with child-process cleanup on timeout."""
import os
import signal
import subprocess


def run_mutations(command, directory, timeout, environment):
    """Capture diagnostics and terminate the entire measurement process tree on timeout."""
    options = dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == 'nt' else dict(start_new_session=True)
    with subprocess.Popen(command, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding='utf-8', errors='replace', env=environment, **options) as process:
        try:
            output, _ = process.communicate(timeout=timeout)
            return process.returncode, output, False
        except subprocess.TimeoutExpired:
            if os.name == 'nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], capture_output=True, check=False)
            else:
                os.killpg(process.pid, signal.SIGKILL)
            process.kill()
            output, _ = process.communicate()
            return process.returncode, output, True
