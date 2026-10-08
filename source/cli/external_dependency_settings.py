"""Collect optional external library declarations during configuration creation."""

import json
from models.external_dependency import ExternalDependencyRule


def collect_external_dependencies(prompt_text):
    """Accept an editable JSON rule list, with an empty default for existing workflows."""
    while True:
        try:
            raw = json.loads(prompt_text("External dependency rules (JSON list; retain or replace)", "[]"))
            if not isinstance(raw, list):
                raise ValueError("External dependency rules must be a list")
            rules = [ExternalDependencyRule.model_validate(item).model_dump(mode="json") for item in raw]
            return dict(external_dependencies=rules)
        except (ValueError, TypeError) as exc:
            print(exc)
