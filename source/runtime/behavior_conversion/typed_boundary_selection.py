"""Select the binding's public entry, construction and value-access methods only."""
from runtime.behavior_conversion.java_api_types import public_api_types
from runtime.behavior_conversion.method_contracts import _signature, java_type_resolver


def configured_step_entry_signatures(bundle):
    """Check possible execute entries before binding; setup/projection APIs are checked once bound."""
    sources={name:file.content for file in bundle.files if file.path.startswith('src/main/java/')
             for name in public_api_types(file.content)}
    selected=set()
    for contract in bundle.contracts.values():
        for api in contract.apis:
            resolve=java_type_resolver(sources.get(api.type_name,''),sources)
            for declaration in api.method_signatures:
                signature=_signature(declaration,resolve)
                if signature and signature[0]=='execute':selected.add((api.type_name,signature))
    # Missing entries retain the existing validation/routing rather than silently selecting no methods.
    return selected or None


def selected_boundary_signatures(bundle,binding):
    """Keep helpers out of typed-boundary policy without removing their normal validation."""
    apis = list(bundle.unit_contract.apis) if getattr(bundle,'unit_contract',None) else [
        api for contract in getattr(bundle,'contracts',{}).values() for api in contract.apis]
    sources={name:file.content for file in bundle.files if file.path.startswith('src/main/java/')
             for name in public_api_types(file.content)}
    index={}
    for api in apis:
        resolve=java_type_resolver(sources.get(api.type_name,''),sources)
        index[api.type_name]=[signature for text in api.method_signatures if (signature:=_signature(text,resolve))]
    selected=set()
    def method(owner,name,parameters=None,static=None):
        matches=[sig for sig in index.get(owner,[]) if sig[0]==name and
                 (parameters is None or sig[2]==tuple(parameters)) and (static is None or sig[3]==static)]
        for sig in matches:selected.add((owner,sig))
        return matches[0][1] if len(matches)==1 else None
    def getters(owner,names):
        for name in names:
            owner=method(owner,name,(),False)
            if owner is None:break  # Actual missing/ambiguous members remain binding/compile errors.
    def construct(recipe):
        if recipe.source!='object':return
        method(recipe.type_name,recipe.type_name.rsplit('.',1)[-1].rsplit('$',1)[-1],[arg.type_name for arg in recipe.arguments],False)
        for child in recipe.arguments:construct(child)
        for name,child in recipe.properties.items():
            method(recipe.type_name,name,[child.type_name],False)
            if name.startswith('set'):
                for prefix in ('get','is'):method(recipe.type_name,prefix+name[3:],(),False)
            construct(child)
    result=method(binding.owner_type,binding.method_name,[arg.type_name for arg in binding.arguments],binding.static_method)
    if not binding.static_method:
        method(binding.owner_type,binding.owner_type.rsplit('.',1)[-1].rsplit('$',1)[-1],
               [arg.type_name for arg in binding.constructor_arguments],False)
    for recipe in [*binding.constructor_arguments,*binding.arguments]:construct(recipe)
    getters(result,binding.output_getters)
    for projection in binding.context_writes:
        owner=result if projection.source=='result' else binding.arguments[projection.argument_index].type_name
        getters(owner,projection.getters)
        getters(owner,projection.presence_getters)
    return selected
