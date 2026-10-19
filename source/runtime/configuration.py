"""Resolve explicit profile paths against YAML and default paths against the project."""

from pathlib import Path

from runtime.project_paths import project_root

import yaml

from models.pipeline_configuration import PipelineConfiguration


def load_configuration(path: str | Path) -> PipelineConfiguration:
    """Validate YAML and resolve project paths; reject missing source inputs."""
    profile_path = Path(path).resolve()
    data = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    config = PipelineConfiguration.model_validate(data)
    project_directory = project_root()
    for name in ("source_root", "mapper_jar", "output_root"):
        setattr(config, name, str(((profile_path.parent if name in config.model_fields_set else project_directory) / getattr(config, name)).resolve()))
    config.classpath_jars = [str(((profile_path.parent if "classpath_jars" in config.model_fields_set else project_directory) / path).resolve()) for path in config.classpath_jars]
    for name in ("maven_settings_path", "maven_local_repository", "deployment_template_dir", "java_home", "service_registry_path"):
        if getattr(config, name):
            setattr(config, name, str(((profile_path.parent if name in config.model_fields_set else project_directory) / getattr(config, name)).resolve()))
    config.eclipse_classpath_variables = {
        name: str(((profile_path.parent if "eclipse_classpath_variables" in config.model_fields_set else project_directory) / path).resolve())
        for name, path in config.eclipse_classpath_variables.items()
    }
    if not Path(config.source_root).is_dir():
        raise ValueError("source_root must identify an existing directory")
    if not Path(config.mapper_jar).is_file():
        raise ValueError("mapper_jar must identify an existing file")
    if config.conversion_strategy == "behavior_units" or config.service_registry_path:
        from tools.converted_service_registry_tools.location import resolve_registry_settings
        config.source_workspace_id, registry_path = resolve_registry_settings(config)
        config.service_registry_path = str(registry_path)
    return config
