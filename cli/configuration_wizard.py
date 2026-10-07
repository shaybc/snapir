"""Create a named migration configuration without starting a migration."""

import os
from pathlib import Path
import re
import tempfile
from typing import get_args

import yaml

from cli.configuration_discovery import discover_channel_directories, discover_operations
from cli.interactive import SelectionCancelled, select_option
from cli.multiselect import select_multiple
from models.pipeline_configuration import PipelineConfiguration
from runtime.configuration import load_configuration


def prompt_text(title: str, default: str = "") -> str:
    """Collect text with a displayed default, converting cancellation to wizard cancellation."""
    from prompt_toolkit import prompt
    from prompt_toolkit.key_binding import KeyBindings

    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def cancel(event):
        event.app.exit(exception=SelectionCancelled())

    try:
        value = prompt(f"{title}{f' [{default}]' if default else ''}: ", key_bindings=bindings).strip()
    except (KeyboardInterrupt, EOFError) as exc:
        raise SelectionCancelled from exc
    return value or default


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


def collect_path(configs: Path, field: str, default: str) -> str:
    """Prompt for a config-relative path and validate source/mapper inputs."""
    while True:
        value = prompt_text(field, default)
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


def create_configuration() -> Path:
    """Collect and save a migration profile, requiring confirmation before replacing one."""
    configs = Path(__file__).resolve().parent.parent / "configs"
    while True:
        name = prompt_text("Config name (for example bank_demo)")
        try:
            destination = configuration_path(configs, name)
            break
        except ValueError as exc:
            print(exc)
    overwrite = destination.exists()
    if overwrite and select_option(f"{destination.name} already exists. Replace it?", [
        ("cancel", "Cancel"), ("replace", "Replace existing config"),
    ]) != "replace":
        raise SelectionCancelled
    source_root = collect_path(configs, "source_root", "../bank-demo/composer/Workspace")
    mapper_jar = collect_path(configs, "mapper_jar", "../composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar")
    output_root = collect_path(configs, "output_root", "../work/migration_runs")
    channel_directories = discover_channel_directories((configs / source_root).resolve())
    channels = select_multiple("Select channels", [(name, name) for name in channel_directories], select_all=True)
    operations = discover_operations(channel_directories, channels)
    included = select_multiple("Select operations", [(name, name) for name in operations], select_all=True)
    supported_languages = get_args(get_args(PipelineConfiguration.model_fields["target_languages"].annotation)[0])
    languages = select_multiple("Select target languages", [(name, name.title()) for name in supported_languages], select_all=True)
    if not channels or not included or not languages:
        raise ValueError("Select at least one channel, operation, and target language")
    data = dict(source_root=source_root, mapper_jar=mapper_jar, output_root=output_root,
                channels=channels, include_operations=included, target_languages=languages)
    save_configuration(destination, data, overwrite=overwrite)
    print(f"Configuration saved: {destination}")
    return destination
