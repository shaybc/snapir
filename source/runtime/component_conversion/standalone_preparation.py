"""Build standalone class units and component plans without a containing operation."""
from models.component_conversion_plan import ComponentConversionPlan
from copy import deepcopy
from models.planned_conversion_component import PlannedConversionComponent
from tools.conversion_tools.component_order import order_component_groups
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.conversion_tools.standalone_sources import source_catalog, component_catalog, component_sources
from tools.behavior_verification.boundaries import build_boundary_report


def prepare_components(profile):
    """Resolve selected classes and each directional boundary using the existing analyzer."""
    catalog = source_catalog(profile.source_root)
    available = component_catalog(profile.source_root, catalog=catalog)[profile.component_type]
    if set(profile.selected_components) - set(available):
        raise ValueError('Selected classes are no longer available as ' + profile.component_type + ' components')
    origins = []
    plan, units = ComponentConversionPlan(), []
    for name in profile.selected_components:
        sources, dependencies = component_sources(profile, catalog, [name])
        origins.extend(item for item in dependencies if item not in origins)
        origin = next((item for item in dependencies if item['fqcn'] == name), None)
        if origin is None:
            raise ValueError('Selected component has no unique original source: ' + name)
        key = 'component-java-' + digest([name, origin['source_project']])
        kinds = ['response_format', 'request_unformat'] if profile.component_type == 'format' else ['configured_step']
        identities = []
        for kind in kinds:
            identity = 'component-unit-' + digest([key, kind])
            attributes = profile.component_attributes.get(name, {})
            configuration = (dict(attributes={**attributes, 'implClass': name}) if kind == 'configured_step' else
                dict(tag=name.rsplit('.', 1)[-1], java_class=name, attributes=attributes, children=[]))
            unit = dict(unit_id=identity, fingerprint=digest([name, kind, sources, configuration]),
                operation_identity='component:' + name, kind=kind, effective_configuration=configuration,
                configuration_xml='', referenced_definitions=[], sources=sources, component_class=name)
            units.append(unit)
            identities.append(identity)
            plan.unit_roots[identity] = key
        plan.components[key] = PlannedConversionComponent(component_id=key, kind='java_implementation',
            label=name, status='source_recorded', roles=['format_leaf' if profile.component_type == 'format' else 'step_implementation'],
            unit_ids=identities, provenance={**origin, 'supporting_sources': [item for item in dependencies if item['definition_id'] != origin['definition_id']]})
    # Each target receives the complete source closure, so no independent helper conversion is invented.
    plan.groups = order_component_groups(plan.components)
    plan.fingerprint = digest(plan.model_dump(mode='json', exclude={'fingerprint'}))
    preparation = dict(conversion_scope='components', selected_components=list(profile.selected_components),
                       component_attributes=deepcopy(profile.component_attributes),
                       component_type=profile.component_type, standalone_units=units, java_origins=origins,
                       operations={}, component_plan=plan.model_dump(mode='json'))
    from tools.source_discovery_tools.classpath_scope import discover_conversion_classpath
    classpath = discover_conversion_classpath(profile.source_root, profile.classpath_jars,
        profile.eclipse_classpath_variables, profile=profile)
    from runtime.behavior_conversion.verification_mode import facts_disabled
    boundaries = build_boundary_report(preparation, collect_checklists=not facts_disabled(profile),
        classpath_index=classpath, framework_jars=profile.framework_jars)
    preparation['boundaries'] = boundaries
    preparation['selection_hash'] = digest(dict(type=profile.component_type, names=profile.selected_components,
        attributes=profile.component_attributes, boundaries=boundaries, plan=plan.model_dump(mode='json')))
    return preparation, classpath


def verify_preparation(profile, preparation):
    """Recheck selected source/configuration/JAR evidence before every standalone task."""
    from tools.conversion_tools.standalone_sources import verify_sources
    from tools.behavior_verification.framework_jars import framework_libraries
    if profile.conversion_scope != 'components' or profile.selected_components != preparation['selected_components'] or profile.component_type != preparation['component_type']:
        raise ValueError('Standalone component selection changed')
    verify_sources(preparation['java_origins'])
    if profile.component_attributes != preparation['component_attributes']:
        raise ValueError('Standalone component initialization changed')
    from tools.behavior_verification.java_tool import default_tool_path
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    if file_digest(default_tool_path()) != preparation['boundaries']['analysis_tool_hash']:
        raise ValueError('Standalone boundary analyzer changed')
    frameworks = {item['path']: item['sha256'] for item in framework_libraries(profile.framework_jars)}
    from tools.composer_mapper_tools.scoped_intake_evidence import file_digest
    from pathlib import Path
    for boundary in preparation['boundaries']['boundaries'].values():
        method = boundary.get('framework_method')
        if method and frameworks.get(method['jar_path']) != method['jar_sha256']:
            raise ValueError('Standalone framework method revision changed')
    for context in preparation['boundaries'].get('analysis_classpaths', {}).values():
        for project in context['projects'].values():
            for library in project['libraries']:
                if file_digest(Path(library['path'])) != library['sha256']:
                    raise ValueError('Standalone project JAR changed')
