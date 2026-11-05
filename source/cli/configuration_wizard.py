"""Create a named migration configuration without starting a migration."""

import os
from pathlib import Path

from runtime.project_paths import project_root
import re
import tempfile
from typing import get_args

import yaml

import constants

from cli.configuration_discovery import discover_channel_directories, discover_operations
from cli.interactive import SelectionCancelled, select_option
from cli.multiselect import select_multiple
from cli.terminal_display import clear_screen
from models.pipeline_configuration import PipelineConfiguration
from runtime.configuration import load_configuration
from cli.java_configuration import collect_java_configuration, collect_java_scan_timeout
from cli.external_dependency_settings import collect_external_dependencies
from cli.test_deployment_settings import collect_test_deployment_settings
from cli.model_configuration import collect_model_configuration
from cli.composer_map_configuration import collect_composer_map_configuration
from cli.gate_configuration import collect_gate_configuration


def prompt_text(title: str, default: str = "", *, heading=None, allow_back=False) -> str:
    """Collect text with a displayed default, converting cancellation to wizard cancellation."""
    from prompt_toolkit import prompt
    from prompt_toolkit.key_binding import KeyBindings

    bindings = KeyBindings()
    cleared = False

    if heading:
        @bindings.add('c-u', eager=True)
        def clear_value(event):
            nonlocal cleared
            cleared = True
            event.current_buffer.text = ''

    if allow_back:
        @bindings.add('c-b', eager=True)
        def back(event):
            from cli.configuration_inputs import WizardBack
            event.app.exit(exception=WizardBack())

    @bindings.add("escape", eager=True)
    def cancel(event):
        event.app.exit(exception=SelectionCancelled())

    try:
        if heading:
            from cli.configuration_review import safe_value
            message = (heading + '\nINPUT REQUIRED\n\n' + title + '\nDefault:\n  ' + safe_value(default) +
                       '\n\nEnter: keep default or accept answer   Ctrl+U: clear saved value\n' +
                       ('Back: Ctrl+B (discard unfinished section edits)   ' if allow_back else '') +
                       'Cancel: Esc\nValue > ')
        else:
            message = f"{title}{f' [{default}]' if default else ''}: "
        value = prompt(message, key_bindings=bindings).strip()
    except EOFError as exc:
        raise SelectionCancelled(input_closed=True) from exc
    except KeyboardInterrupt as exc:
        raise SelectionCancelled from exc
    finally:
        if not heading:
            clear_screen()
    return value if cleared else value or default


def configuration_path(configs: Path, name: str) -> Path:
    """Require a plain config name so the destination remains inside configs/."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", name):
        raise ValueError("Config name must contain only letters, numbers, underscores, or hyphens")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                                        *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("Config name is reserved by Windows")
    destination = configs / f"{name}.yaml"
    if not destination.resolve().is_relative_to(configs.resolve()):
        raise ValueError("Config must stay inside configs/")
    return destination


def collect_path(configs: Path, field: str, default: str, *, prompt=None) -> str:
    """Prompt for a config-relative path and validate source/mapper inputs."""
    while True:
        value = (prompt or prompt_text)(field, default)
        resolved = (configs / value).resolve()
        if field == "source_root" and not resolved.is_dir():
            print(f"source_root must identify an existing directory: {resolved}")
        elif field == "mapper_jar" and not resolved.is_file():
            print(f"mapper_jar must identify an existing file: {resolved}")
        else:
            return value


def save_configuration(destination: Path, data: dict, *, overwrite: bool) -> None:
    """Validate a temporary YAML beside its destination, then save a complete file."""
    PipelineConfiguration.model_validate(data)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".yaml",
                                         dir=destination.parent, delete=False) as output:
            yaml.safe_dump(data, output, sort_keys=False)
            temporary = Path(output.name)
        load_configuration(temporary)
        if overwrite:
            os.replace(temporary, destination)
        else:
            # Linking a fully written file refuses a name created since the wizard began.
            os.link(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def create_configuration() -> Path | None:
    """Edit and review a draft; cancellation returns to the menu without saving."""
    import sys
    from cli.configuration_flow import run_configuration_wizard
    return run_configuration_wizard(project_root() / "configs", sys.modules[__name__])
