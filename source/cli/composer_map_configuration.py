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
        mode=select_option('New map analysis',[
            ('legacy','Current map format'),
            ('indexed-v1','Reusable AST index for large workspaces (scoped map)'),
        ])
        if mode=='indexed-v1':
            print('The mapper analyzes the full workspace once. Migration intake then loads the selected operations and Java dependencies.')
            return dict(mapper_analysis_format='indexed-v1',mapper_vault_layout='scoped')
        return {}
    while True:
        value = prompt_text("Existing Composer map folder")
        try:
            if not value.strip():
                raise ValueError("Enter an existing Composer map folder")
            check_existing_composer_map(str((configs / value).resolve()))
            print("Existing map selected. It will be validated once when migration imports it; no remapping.")
            from tools.composer_mapper_tools.indexed_analysis import is_indexed_map,bounded_json
            root=(configs/value).resolve()
            if is_indexed_map(root):
                descriptor=bounded_json((root/'vault-manifest.json').read_text(encoding='utf-8-sig'))
                return dict(existing_composer_map=value,mapper_analysis_format='indexed-v1',mapper_vault_layout='scoped',source_workspace_id=descriptor['workspace_id'])
            return dict(existing_composer_map=value)
        except (ValueError, OSError) as exc:
            print(sanitize_diagnostic(str(exc)))
