"""Load project profiles with paths relative to their configuration file."""

from pathlib import Path

import yaml

from models.pipeline_configuration import PipelineConfiguration


def load_configuration(path: str | Path) -> PipelineConfiguration:
    """Validate YAML and resolve project paths; reject missing source inputs."""
    profile_path = Path(path).resolve()
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    config = PipelineConfiguration.model_validate(data)
    for name in ("source_root", "mapper_jar", "output_root"):
        setattr(config, name, str((profile_path.parent / getattr(config, name)).resolve()))
    config.classpath_jars = [str((profile_path.parent / path).resolve()) for path in config.classpath_jars]
    for name in ("maven_settings_path", "maven_local_repository", "deployment_template_dir"):
        if getattr(config, name):
            setattr(config, name, str((profile_path.parent / getattr(config, name)).resolve()))
    config.eclipse_classpath_variables = {
        name: str((profile_path.parent / path).resolve())
        for name, path in config.eclipse_classpath_variables.items()
    }
    if not Path(config.source_root).is_dir():
        raise ValueError("source_root must identify an existing directory")
    if not Path(config.mapper_jar).is_file():
        raise ValueError("mapper_jar must identify an existing file")
    return config
