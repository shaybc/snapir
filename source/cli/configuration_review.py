"""Render bounded configuration summaries without exposing credential values."""

import json
import textwrap
from pathlib import Path

from runtime.model_execution.error_details import sanitize_diagnostic
from cli.interactive import SelectionCancelled


def safe_value(value):
    """Sanitize display text, including URL credentials, query strings and control escapes."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=True)
    return sanitize_diagnostic(text).replace('\x1b', '?')


def summary_lines(data, *, directory=None):
    """Summarize every explicitly selected setting with bounded list previews."""
    lines = []
    paths = {'source_root', 'output_root', 'mapper_jar', 'existing_composer_map', 'java_home','mapper_analysis_reuse'}
    for name, value in data.items():
        if name.startswith('_'):
            continue
        if name == 'model_api_key_environment':
            lines.append(f'{name}: {safe_value(value)} (environment variable name; value not displayed)')
            continue
        if isinstance(value, list):
            preview = ', '.join(safe_value(item) for item in value[:5])
            lines.append(f'{name}: {len(value)} selected; {preview}' + (' ...' if len(value) > 5 else ''))
        else:
            lines.append(f'{name}: {safe_value(value)}')
        if directory and name in paths and value:
            lines.append('  Resolved: ' + safe_value(str((Path(directory) / value).resolve())))
    lines.append('Composer map: ' + ('Reuse existing map' if data.get('existing_composer_map') else
                                    'Create during migration; no mapping is running now'))
    return lines


def wrapped_summary(lines, width):
    """Wrap long paths without hiding the complete selected value."""
    return '\n'.join(part for line in lines for part in textwrap.wrap(line, width=max(20, width),
                     subsequent_indent='  ', replace_whitespace=False) or [''])


def review_configuration(draft, inputs, configs, names, *, settings_transform=None):
    """Offer explicit Save/Edit/Back/Cancel; an extra Enter initially chooses Edit."""
    data = draft.values()
    if settings_transform:
        data = settings_transform(data)
    destination = configs / (data['_name'] + '.yaml')
    while True:
        lines = [*([safe_value(inputs.feedback)] if inputs.feedback else []), f'Destination: {safe_value(str(destination))}',
                 'Existing file will require replacement confirmation.' if destination.exists() else 'New configuration file.',
                 *(['Full conversion: fixed workflow settings; edit sections change user inputs only.'] if settings_transform else []),
                 *summary_lines(data, directory=configs)]
        action = inputs.api.select_option('Review configuration', [
            ('edit', 'Edit a section'), ('save', 'Save configuration'),
            ('operations', 'View all selected operations'), ('back', 'Back'), ('cancel', 'Cancel')],
            heading='Review configuration: ' + safe_value(data['_name']), details=lines,
            clear_after_selection=False)
        if action == 'operations':
            operations = data.get('include_operations', [])
            try:
                inputs.api.select_option('Selected operations (type to filter; Enter to return)',
                    [(str(i), safe_value(name)) for i, name in enumerate(operations)], filterable=True,
                    heading='Review configuration: ' + safe_value(data['_name']), clear_after_selection=False)
            except SelectionCancelled as exc:
                if exc.input_closed:
                    raise
        elif action == 'edit':
            try:
                section = inputs.api.select_option('Edit a section', [(str(i), name) for i, name in enumerate(names)],
                    heading='Review configuration: ' + safe_value(data['_name']), clear_after_selection=False)
                return 'edit', int(section)
            except SelectionCancelled as exc:
                if exc.input_closed:
                    raise
        else:
            return action, None
