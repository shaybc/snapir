"""Classify conversion responsibilities explicitly instead of routing by bundle schema alone."""
PIPELINE_VERSION='staged-pipeline-v2'
_TASKS={
    'component_generation':'component', 'unit':'unit', 'service':'service',
    'service_implementation':'implementation', 'contract':'contract',
    'route_scenario_test':'tests', 'thin_path_experiment':'isolated_unit',
    'side_road_baseline':'unit', 'side_road_simplify':'unit',
}
_CODE_SCHEMAS={'NativeUnitBundle','NativeComponentBundle','NativeFormatComponentBundle','OperationDataContract'}


def conversion_task(category,schema):
    """Metadata/review tasks remain narrow calls; unknown code jobs cannot bypass staging."""
    if schema.__name__ not in _CODE_SCHEMAS:return 'metadata'
    if category not in _TASKS:raise ValueError('No staged conversion task registered for '+category+' / '+schema.__name__)
    return _TASKS[category]
