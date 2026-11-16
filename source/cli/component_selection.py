"""Collect explicit standalone class selections without discovering operations."""
from pathlib import Path


def collect_components(draft, inputs, configs, api):
    """List source-backed format or step candidates and remember multiple selections."""
    kind = inputs.menu('Component type', [('format', 'Formats'), ('op_step', 'OP steps')])
    root = str((Path(configs) / draft.values()['source_root']).resolve())
    key = ('component-catalog', root)
    if key not in draft.discovery:
        print('WORKING - Discovering component classes...', flush=True)
        from tools.conversion_tools.standalone_sources import component_catalog
        from runtime.java_toolchain import java_scope
        from models.pipeline_configuration import PipelineConfiguration
        with java_scope(PipelineConfiguration()):
            draft.discovery[key] = component_catalog(root)
    names = draft.discovery[key][kind]
    if not names:
        raise ValueError('No ' + kind + ' component candidates found in the source workspace')
    selected = inputs.multiple('Select ' + ('formats' if kind == 'format' else 'OP steps'),
        [(name, name) for name in names], select_all=False, filterable=True)
    if not selected:
        raise ValueError('Select at least one component')
    return dict(conversion_scope='components', component_type=kind, selected_components=selected,
                component_attributes={}, channels=[], include_operations=[], target_languages=['java'],
                format_comparison=dict(enabled=True, collect_facts=False),
                conversion_strategy='behavior_units', scoped_native_mode='component_first_v1')
