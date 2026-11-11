"""Validate declarative API recipes before a trusted harness invokes any native method."""
import re
from runtime.behavior_conversion.java_api_types import public_api_types
from runtime.behavior_conversion.verification_feedback import VerificationFailure, VerificationIncomplete

SCALARS = {'java.lang.String', 'java.lang.Integer', 'java.lang.Long', 'java.lang.Boolean', 'java.lang.Double',
           'java.math.BigDecimal', 'java.util.Date', 'int', 'long', 'boolean', 'double', 'float', 'short', 'byte', 'char'}


def project_context_only(binding, boundary):
    """A void original request exposes context writes, not its native DTO transport object."""
    original = boundary.legacy_method
    if (boundary.kind == 'request_unformat' and binding.context_writes and
            (original is not None and original.return_type == 'void' or
             boundary.framework_boundaries and boundary.return_contract == 'void')):
        return binding.model_copy(update={'output': 'none', 'output_getters': []})
    return binding


def validate_binding(bundle, extra_types=()):
    """No AI bridge sources, Java expressions, expected outputs or arbitrary JDK object recipes."""
    binding = bundle.verification_binding
    if binding is None:
        raise VerificationFailure(dict(stage='binding', errors=['Missing verification_binding for the actual native API']))
    own = {name for file in bundle.files if file.path.startswith('src/main/java/') for name in public_api_types(file.content)}
    names = own | set(extra_types)
    apis = {api.type_name for api in bundle.unit_contract.apis} if bundle.unit_contract else set()
    if binding.owner_type not in own & apis or not _member(binding.method_name):
        raise VerificationFailure(dict(stage='binding', errors=['Boundary entry must be a declared native unit API']))
    from runtime.behavior_conversion.method_contracts import _signature, java_type_resolver
    owner_source = next(file.content for file in bundle.files if binding.owner_type in public_api_types(file.content))
    resolve = java_type_resolver(owner_source, names)
    signatures = [_signature(signature, resolve) for api in bundle.unit_contract.apis if api.type_name == binding.owner_type
                  for signature in api.method_signatures]
    expected = (binding.method_name, tuple(resolve(argument.type_name) for argument in binding.arguments), binding.static_method)
    if not any(signature and (signature[0], signature[2], signature[3]) == expected for signature in signatures):
        raise VerificationFailure(dict(stage='binding', errors=['Declare the exact boundary method and parameter types in unit_contract.apis']))
    def value(recipe, depth=0):
        if depth > 12:
            raise VerificationFailure(dict(stage='binding', errors=['Generated argument binding exceeds the maximum nesting depth of 12']))
        if recipe.factory_method and (recipe.source!='object' or not _member(recipe.factory_method)):
            raise VerificationFailure(dict(stage='binding',errors=['Factories require a named native object method']))
        if recipe.type_name not in names | SCALARS:
            # The model chose this native API/recipe; correct the candidate rather than declaring a missing harness capability.
            raise VerificationFailure(dict(stage='binding', errors=['Unsupported typed argument: ' + recipe.type_name],
                allowed_types=sorted(names | SCALARS),
                correction='Use the supported scalar inputs or supplied native DTO types for the boundary API; update its code, contract and binding together. Do not add executable harness adapters.'))
        if recipe.source == 'xml' and (recipe.type_name != 'java.lang.String' or recipe.arguments or recipe.properties or recipe.key):
            raise VerificationFailure(dict(stage='binding', errors=['XML binding must pass the original String unchanged']))
        if recipe.source == 'context' and (not recipe.key or recipe.arguments or recipe.properties):
            raise VerificationFailure(dict(stage='binding', errors=['Context binding needs only an original context key']))
        if recipe.source == 'configuration' and (not recipe.key or recipe.arguments or recipe.properties or recipe.factory_method):
            raise VerificationFailure(dict(stage='binding', errors=['Configuration binding needs only an exact attribute key']))
        if recipe.source == 'object':
            if recipe.type_name not in names or recipe.key or any(not _member(name) for name in recipe.properties):
                raise VerificationFailure(dict(stage='binding', errors=['Object bindings construct native types only']))
            for child in [*recipe.arguments, *recipe.properties.values()]: value(child, depth + 1)
    for recipe in [*binding.arguments, *binding.constructor_arguments]: value(recipe)
    for setter, recipe in binding.configuration_setters.items():
        if not _member(setter) or recipe.source != 'configuration' or binding.static_method:
            raise VerificationFailure(dict(stage='binding', errors=['Configuration setters require instance configuration inputs']))
        value(recipe)
    keys = [projection.context_key for projection in binding.context_writes]
    if len(set(keys)) != len(keys):
        raise VerificationIncomplete(dict(stage='binding', errors=['Repeated dynamic writes need an explicit supported observer']))
    for projection in binding.context_writes:
        if projection.source=='receiver' and binding.static_method:
            raise VerificationFailure(dict(stage='binding',errors=['Static boundary has no receiver state']))
        if projection.source == 'argument' and projection.argument_index >= len(binding.arguments):
            raise VerificationFailure(dict(stage='binding', errors=['Projection argument is outside the declared method']))
        if not all(_member(name) for name in [*projection.getters, *projection.presence_getters]):
            raise VerificationFailure(dict(stage='binding', errors=['Projection paths contain public accessors only']))
        if any(not field or not getters or not all(_member(name) for name in getters)
               for field,getters in projection.collection_fields.items()):
            raise VerificationFailure(dict(stage='binding',errors=['Collection observations require exact field names and public accessor paths']))
        if any(not field or not getters or not all(_member(name) for name in getters)
               for field,getters in projection.collection_fields.items()):
            raise VerificationFailure(dict(stage='binding',errors=['Collection observations require exact field names and public accessor paths']))
    if not all(_member(name) for name in binding.output_getters):
        raise VerificationFailure(dict(stage='binding', errors=['Invalid output accessor']))
    for destination in binding.settings_bindings.values():
        if set(destination) != {'class', 'method'} or destination['class'] not in names or not _member(destination['method']):
            raise VerificationFailure(dict(stage='binding', errors=['Settings must bind to an actual supplied native type/method']))
    return binding


def _member(name):
    return bool(re.fullmatch(r'[A-Za-z_$][\w$]*', name)) and name not in {'getClass', 'wait', 'notify', 'notifyAll', 'finalize', 'clone'}
