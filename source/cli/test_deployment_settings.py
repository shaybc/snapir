"""Collect connection settings for manually deployed test services."""

from models.test_deployment_settings import TestDeploymentSettings


def collect_test_deployment_settings(prompt_text):
    """Prompt for every setting using central defaults and retry only invalid values."""
    values = TestDeploymentSettings().model_dump(mode="json")
    for name, field in TestDeploymentSettings.model_fields.items():
        current = values[name]
        default = "auto" if current is None else str(current)
        while True:
            try:
                raw = prompt_text(field.title, default)
                value = raw
                if name == "service_external_port":
                    value = None if raw.strip().lower() in {"", "auto"} else int(raw)
                validated = TestDeploymentSettings.model_validate({**values, name: value})
                values = validated.model_dump(mode="json")
                break
            except (ValueError, TypeError) as exc:
                print(exc)
    return dict(test_deployment=values)
