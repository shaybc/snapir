"""Navigate configuration sections and commit the reviewed draft through existing validation."""

import os
from pathlib import Path
from typing import get_args

from models.configuration_draft import ConfigurationDraft
from cli.configuration_inputs import WizardInputs, WizardBack
from cli.configuration_review import review_configuration, safe_value
from cli.interactive import SelectionCancelled

SECTION_NAMES = ('Name and source workspace', 'Composer map', 'Output folder',
                 'Channels, operations and languages', 'Java and scanner timeout',
                 'External dependencies and conversion strategy', 'Gate settings',
                 'AI model connection', 'Test deployment')


def _default_path(configs, path):
    return Path(os.path.relpath((configs.parent / path).resolve(), configs)).as_posix()


def collect_section(draft, inputs, configs, api):
    """Invoke canonical collectors, using remembered prompt answers as defaults."""
    section, values = draft.section, draft.values()
    if section == 0:
        name = inputs.text('Config name (for example bank_demo)')
        api.configuration_path(configs, name)
        return dict(_name=name, source_root=api.collect_path(configs, 'source_root',
                    _default_path(configs, api.constants.COMPOSER_ROOT), prompt=inputs.text))
    if section == 1:
        result = api.collect_composer_map_configuration(configs, inputs.text, inputs.menu)
        if not result:
            result['mapper_jar'] = api.collect_path(configs, 'mapper_jar',
                _default_path(configs, api.constants.COMPOSER_MAPPER_JAR), prompt=inputs.text)
        return result
    if section == 2:
        return dict(output_root=api.collect_path(configs, 'output_root',
                    _default_path(configs, api.constants.OUTPUT_ROOT), prompt=inputs.text))
    if section == 3:
        root = str((configs / values['source_root']).resolve())
        channel_key = ('channels', root)
        if channel_key not in draft.discovery:
            print('WORKING - Discovering available channels...', flush=True)
            draft.discovery[channel_key] = api.discover_channel_directories(Path(root))
        directories = draft.discovery[channel_key]
        removed_channels = set(inputs.pending.get('@multiple:Select channels', [])) - set(directories)
        if removed_channels:
            inputs.feedback = f'{len(removed_channels)} unavailable channel selections removed; review the new scope.'
        channels = inputs.multiple('Select channels', [(name, name) for name in directories], select_all=True)
        operation_key = ('operations', root, tuple(sorted(channels)))
        if operation_key not in draft.discovery:
            print('WORKING - Discovering operation names for selected channels...', flush=True)
            draft.discovery[operation_key] = api.discover_operations(directories, channels)
        operations = draft.discovery[operation_key]
        old = inputs.pending.get('@multiple:Select operations', [])
        removed = set(old) - set(operations)
        if removed:
            inputs.feedback = f'{len(removed)} unavailable operation selections removed; review the new scope.'
        included = inputs.multiple('Select operations', [(name, name) for name in operations], select_all=True, filterable=True)
        supported = get_args(get_args(api.PipelineConfiguration.model_fields['target_languages'].annotation)[0])
        languages = inputs.multiple('Select target languages', [(name, name.title()) for name in supported], select_all=True)
        if not channels or not included or not languages:
            raise ValueError('Select at least one channel, operation, and target language')
        return dict(channels=channels, include_operations=included, target_languages=languages)
    if section == 4:
        version, home = api.collect_java_configuration(configs, inputs.text)
        return dict(java_version=version, java_home=home,
                    java_scan_inactivity_timeout_seconds=api.collect_java_scan_timeout(inputs.text))
    if section == 5:
        result = api.collect_external_dependencies(inputs.text)
        strategy = inputs.text('conversion_strategy (legacy_components or behavior_units)', 'legacy_components')
        if strategy not in {'legacy_components', 'behavior_units'}:
            raise ValueError('Choose legacy_components or behavior_units')
        return dict(**result, conversion_strategy=strategy)
    if section == 6:
        return api.collect_gate_configuration(inputs.text)
    if section == 7:
        return api.collect_model_configuration(inputs.text)
    return api.collect_test_deployment_settings(inputs.text)


def _commit(draft, inputs, result):
    previous = draft.sections.get(draft.section, {})
    if draft.section == 0 and previous.get('source_root') != result.get('source_root') and 3 in draft.sections:
        draft.dirty.add(3)
    draft.sections[draft.section] = result
    draft.answers[draft.section] = inputs.pending.copy()
    draft.dirty.discard(draft.section)


def _error_section(error):
    text = str(error)
    for index, keys in ((0, ('source_root', 'Config name')), (1, ('mapper_jar', 'existing_composer_map')),
                        (2, ('output_root',)), (3, ('channels', 'include_operations', 'target_languages')),
                        (4, ('java_',)), (5, ('external_dependencies', 'conversion_strategy')),
                        (6, ('gate_', 'plan_approval_policy')), (7, ('model_',)), (8, ('test_deployment',))):
        if any(key in text for key in keys):
            return index
    return 0


def run_configuration_wizard(configs, api):
    """Collect an editable draft and save only after explicit review and replacement approval."""
    draft = ConfigurationDraft()
    inputs = WizardInputs(draft, api, SECTION_NAMES)
    reviewing = False
    retry = False
    while True:
        try:
            if not reviewing:
                inputs.begin(retain=retry)
                retry = False
                result = collect_section(draft, inputs, configs, api)
                inputs.next()
                _commit(draft, inputs, result)
                inputs.feedback = ''
                if draft.review_return or draft.section == len(SECTION_NAMES) - 1:
                    if draft.dirty:
                        draft.section = min(draft.dirty)
                        inputs.feedback = 'Source changed. Review channels and operations before saving.'
                        continue
                    reviewing = True
                else:
                    draft.section += 1
                    continue
            action, section = review_configuration(draft, inputs, configs, SECTION_NAMES)
            if action == 'cancel':
                raise SelectionCancelled
            if action in {'back', 'edit'}:
                draft.section = len(SECTION_NAMES) - 1 if action == 'back' else section
                draft.review_return = True
                reviewing = False
                continue
            if action != 'save':
                continue
            data = draft.values()
            destination = api.configuration_path(configs, data.pop('_name'))
            # Validate before asking to replace an existing file; saving retains loader checks.
            api.PipelineConfiguration.model_validate(data)
            overwrite = destination.exists()
            if overwrite:
                choice = api.select_option(f'{destination.name} already exists. Replace it?',
                    [('cancel', 'Back to review'), ('replace', 'Replace existing config')],
                    heading='Confirm configuration replacement', details=[safe_value(str(destination))],
                    clear_after_selection=False)
                if choice != 'replace':
                    continue
            print('WORKING - Validating and saving configuration...', flush=True)
            try:
                api.save_configuration(destination, data, overwrite=overwrite)
            except FileExistsError:
                inputs.feedback = 'Destination appeared while saving. Review the name or explicitly confirm replacement.'
                continue
            api.clear_screen()
            print(f'Configuration saved: {safe_value(str(destination))}')
            print('No mapping or migration has started. Choose Start a new migration from the main menu when ready.')
            return destination
        except WizardBack:
            draft.section = max(0, draft.section - 1)
            reviewing = False
            retry = False
        except SelectionCancelled as exc:
            if exc.input_closed or inputs.discard():
                return None
            retry = not reviewing
        except (ValueError, OSError) as exc:
            inputs.feedback = 'Please correct: ' + safe_value(str(exc))
            print(inputs.feedback)
            if reviewing:
                draft.section = _error_section(exc)
                draft.review_return = True
                reviewing = False
            else:
                retry = True
