"""Confirm interactive migration starts before any run resources are created."""

from cli.configuration_review import safe_value, summary_lines
from cli.interactive import SelectionCancelled, select_option


def confirm_migration_start(configuration, profile):
    """Return start/back/cancel without mapping, scanning or creating a run directory."""
    fields = ('source_root', 'existing_composer_map', 'mapper_jar', 'output_root', 'channels',
              'include_operations', 'exclude_operations', 'target_languages', 'java_version',
              'java_home', 'java_scan_inactivity_timeout_seconds', 'conversion_strategy',
              'model_provider', 'model_name')
    data = {name: getattr(profile, name) for name in fields if hasattr(profile, name)}
    details = ['Configuration: ' + safe_value(str(configuration)), *summary_lines(data),
               'Start begins workspace intake. A new map is generated during the run when selected.']
    try:
        return select_option('Ready to start migration?', [
            ('back', 'Back to configuration selection'), ('start', 'Start migration'), ('cancel', 'Cancel')],
            heading='Review new migration', details=details, clear_after_selection=False)
    except SelectionCancelled:
        return 'cancel'
