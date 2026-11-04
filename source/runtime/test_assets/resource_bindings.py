"""Require declared format-comparison resources to be wired into both executions."""


def validate_comparison_resources(scenario):
    """Check opaque resource identities, without inferring setters or business semantics.

    The AI supplies the actual APIs and resource names. No resource is attached
    automatically. JUnit and operation-step scenarios retain their existing checks.
    """
    if getattr(scenario,'direction',None) not in {'format','unformat'}:return
    native=set()
    def visit(recipe):
        if recipe.source=='resource':native.add(recipe.key)
        for child in [*recipe.arguments,*recipe.properties.values()]:visit(child)
        if recipe.element:visit(recipe.element)
    entry=scenario.native_entry
    for recipe in [*entry.arguments,*entry.constructor_arguments,*entry.configuration_setters.values()]:visit(recipe)
    declared=set(scenario.resources)
    composer=set(scenario.composer_resource_setters.values())
    missing_native=sorted(declared-native)
    missing_composer=sorted(declared-composer)
    if missing_native or missing_composer:
        raise ValueError('Incomplete mock resource setup for '+scenario.scenario_id+
            ': missing native resource recipes='+str(missing_native)+
            '; missing Composer resource attachment='+str(missing_composer)+
            '. Supply exact source-backed setup on both sides; a fixture declaration alone does not attach it.')
