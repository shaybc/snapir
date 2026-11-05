"""Collect an existing Composer map location without generating or modifying it."""

from runtime.model_execution.error_details import sanitize_diagnostic

from tools.workspace_intake_tools.vault_validator import check_existing_composer_map


def collect_composer_map_configuration(configs, prompt_text, select_option):
    """Return optional reuse settings; an empty result keeps new-map generation."""
    choice = select_option("Composer map", [
        ("create", "Create a new map"),
        ("existing", "Use an existing map folder"),
    ])
    if choice != "existing":
        return {}
    while True:
        value = prompt_text("Existing Composer map folder")
        try:
            if not value.strip():
                raise ValueError("Enter an existing Composer map folder")
            check_existing_composer_map(str((configs / value).resolve()))
            print("Existing map selected. It will be validated once when migration imports it; no remapping.")
            return dict(existing_composer_map=value)
        except (ValueError, OSError) as exc:
            print(sanitize_diagnostic(str(exc)))
