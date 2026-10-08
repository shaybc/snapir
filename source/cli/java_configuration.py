"""Collect a matching Java target and installed JDK for a migration configuration."""

from typing import get_args

import constants
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import resolve_java_home


def collect_java_configuration(configs, prompt_text):
    """Accept displayed defaults and retry invalid versions or JDK folders."""
    supported = get_args(PipelineConfiguration.model_fields["java_version"].annotation)
    while True:
        value = prompt_text("Java version (" + ", ".join(map(str, supported)) + ")", str(constants.JAVA_VERSION))
        try:
            version = int(value)
            if version not in supported:
                raise ValueError()
            break
        except ValueError:
            print("Choose a supported Java version: " + ", ".join(map(str, supported)))
    try:
        default = resolve_java_home(version, constants.JAVA_HOME if version == int(constants.JAVA_VERSION) else None)
    except (ValueError, OSError):
        default = ""
    while True:
        value = prompt_text("Java home (installed JDK folder)", default)
        try:
            if not value:
                raise ValueError(f"Supply an installed JDK {version} folder")
            home = resolve_java_home(version, (configs / value).resolve())
            return version, home
        except (ValueError, OSError) as exc:
            print(exc)
