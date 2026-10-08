from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import constants

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from models.deployment_models import DeploymentDefaults, DeploymentSpec, RenderedManifest


DEFAULT_DEPLOYMENT_DEFAULTS = DeploymentDefaults(**deepcopy(constants.DEPLOYMENT_DEFAULTS))


def render_manifest(
    template_dir: str,
    spec: DeploymentSpec,
    *,
    defaults: DeploymentDefaults | None = None,
) -> RenderedManifest:
    """Render deployment templates and validate each rendered YAML document."""
    template_root = Path(template_dir)
    environment = Environment(
        loader=FileSystemLoader(str(template_root)),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )
    files = {}
    for template_path in sorted(template_root.glob("*.yaml.j2")):
        template = environment.get_template(template_path.name)
        rendered = template.render(spec=spec, defaults=defaults if defaults is not None else DEFAULT_DEPLOYMENT_DEFAULTS)
        _validate_yaml(rendered, template_path.name)
        files[template_path.name.removesuffix(".j2")] = rendered
    if not files:
        raise ValueError(f"No deployment templates found in {template_dir}")
    return RenderedManifest(
        operation_id=spec.operation_id,
        platform=spec.platform,
        files=files,
        validated=True,
    )


def _validate_yaml(rendered: str, template_name: str) -> None:
    try:
        documents = list(yaml.safe_load_all(rendered))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid rendered YAML from {template_name}: {exc}") from exc
    if not documents or any(document is None for document in documents):
        raise ValueError(f"Rendered YAML is empty: {template_name}")
