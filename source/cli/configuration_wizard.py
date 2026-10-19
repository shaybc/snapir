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
from cli.java_configuration import collect_java_configuration
from cli.external_dependency_settings import collect_external_dependencies


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
    finally:
        clear_screen()
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
    configs = project_root() / "configs"
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
    source_root = collect_path(configs, "source_root", Path(os.path.relpath((configs.parent / constants.COMPOSER_ROOT).resolve(), configs)).as_posix())
    mapper_jar = collect_path(configs, "mapper_jar", Path(os.path.relpath((configs.parent / constants.COMPOSER_MAPPER_JAR).resolve(), configs)).as_posix())
    output_root = collect_path(configs, "output_root", Path(os.path.relpath((configs.parent / constants.OUTPUT_ROOT).resolve(), configs)).as_posix())
    channel_directories = discover_channel_directories((configs / source_root).resolve())
    channels = select_multiple("Select channels", [(name, name) for name in channel_directories], select_all=True)
    operations = discover_operations(channel_directories, channels)
    included = select_multiple("Select operations", [(name, name) for name in operations], select_all=True)
    supported_languages = get_args(get_args(PipelineConfiguration.model_fields["target_languages"].annotation)[0])
    languages = select_multiple("Select target languages", [(name, name.title()) for name in supported_languages], select_all=True)
    if not channels or not included or not languages:
        raise ValueError("Select at least one channel, operation, and target language")
    java_version, java_home = collect_java_configuration(configs, prompt_text)
    external_settings = collect_external_dependencies(prompt_text)
    strategy = prompt_text("conversion_strategy (legacy_components or behavior_units)", "legacy_components")
    while strategy not in {"legacy_components", "behavior_units"}:
        print("Choose legacy_components or behavior_units")
        strategy = prompt_text("conversion_strategy (legacy_components or behavior_units)", "legacy_components")
    data = dict(source_root=source_root, mapper_jar=mapper_jar, output_root=output_root,
                channels=channels, include_operations=included, target_languages=languages,
                java_version=java_version, java_home=java_home, conversion_strategy=strategy)
    data.update(external_settings)
    save_configuration(destination, data, overwrite=overwrite)
    print(f"Configuration saved: {destination}")
    return destination
