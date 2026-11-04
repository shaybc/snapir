"""Check exact public signatures using existing parser metadata, never internal Java flow."""


def validate_invocation(binding, inventory, *, constructor_entry=False):
    """Validate declared calls/constructors/setters; the AI remains responsible for selecting them."""
    types=inventory.get('types',{})
    if not types:return
    def signature(owner,name,arguments,static=False,constructor=False):
        if owner not in types:raise ValueError('Scenario owner is absent from parsed native APIs: '+owner)
        entries=types[owner].get('constructors' if constructor else 'methods',[])
        wanted=[r.type_name for r in arguments]
        matches=[m for m in entries if (constructor or m['name']==name) and
            [p['type'] for p in m['parameters']]==wanted and
            (constructor or str(m.get('static','false')).lower()==str(static).lower())]
        if len(matches)!=1:raise ValueError('Scenario must name one exact parsed public signature: '+owner+'.'+name+'('+', '.join(wanted)+')')
    def recipe(value):
        if value.source=='object':
            signature(value.type_name,value.factory_method or '<init>',value.arguments,static=bool(value.factory_method),constructor=not value.factory_method)
            for setter,child in value.properties.items():signature(value.type_name,setter,[child])
        for child in [*value.arguments,*value.properties.values()]:recipe(child)
        if value.element:recipe(value.element)
    if not binding.static_method:signature(binding.owner_type,'<init>',binding.constructor_arguments,constructor=True)
    if not constructor_entry:signature(binding.owner_type,binding.method_name,binding.arguments,binding.static_method)
    for setter,value in binding.configuration_setters.items():signature(binding.owner_type,setter,[value])
    for value in [*binding.arguments,*binding.constructor_arguments,*binding.configuration_setters.values()]:recipe(value)
