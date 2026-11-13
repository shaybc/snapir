"""Prepare PowerShell commands without running diagnostic extraction."""
import hashlib
from pathlib import Path


def _literal(value):
    """Quote a PowerShell literal, including spaces, apostrophes and shell syntax."""
    return "'" + str(value).replace("'", "''") + "'"


def trace_command(directory, project, destination, identity):
    """Select one exact diagnostic target; extraction runs only in the user's terminal."""
    project = Path(project)
    interpreter = project / '.venv/Scripts/python.exe'
    python = str(interpreter) if interpreter.is_file() else 'python'
    filename = 'conversion-trace-' + hashlib.sha256(identity.encode()).hexdigest()[:12] + '.json'
    return ('$env:PYTHONPATH = ' + _literal(project / 'source') + '\n& ' + _literal(python) +
            ' -m tools.run_diagnostics.trace_format_flow --run ' + _literal(directory) +
            ' --diagnostics ' + _literal(destination) + ' --group ' + _literal(identity) +
            ' | Set-Content -LiteralPath ' + _literal(Path(destination) / filename) + ' -Encoding UTF8')
