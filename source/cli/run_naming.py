"""Collect a recognizable, unique run and folder name before creating resources."""

from datetime import datetime
from pathlib import Path
import re
import uuid

from cli.configuration_wizard import prompt_text
from runtime.workspace_paths import resolve_run_directory


def suggested_run_name(configuration):
    """Suggest a folder-safe configuration name, local start time and unique suffix."""
    name = re.sub(r'[^A-Za-z0-9_-]+', '-', Path(configuration).stem).strip('-_') or 'run'
    return f'{name[:70]}-{datetime.now().astimezone():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}'


def validate_run_name(output_root, name):
    """Reject unsafe Windows names and existing destinations without writing anything."""
    directory = resolve_run_directory(output_root, name)
    if name.upper() in {'CON', 'PRN', 'AUX', 'NUL',
                        *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('Run name is reserved by Windows')
    if directory.exists():
        raise ValueError(f'A run named {name} already exists in {output_root}; choose another name')
    return directory


def choose_run_name(configuration, output_root):
    """Keep prompting until a unique name is entered; cancellation creates no run."""
    default = suggested_run_name(configuration)
    while True:
        name = prompt_text('Name this run (letters, numbers, dashes and underscores; up to 100 characters)',
                           default, heading=f'New migration\nConfiguration: {Path(configuration).name}')
        try:
            validate_run_name(output_root, name)
            return name
        except ValueError as exc:
            print(str(exc), flush=True)
