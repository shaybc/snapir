"""Supply evidence-derived typed boundary guidance and reject generic public contracts."""
from copy import deepcopy
import re
from runtime.behavior_conversion.java_api_types import public_api_types
from runtime.behavior_conversion.method_contracts import _signature, java_type_resolver


KINDS = {'request_unformat', 'response_format', 'configured_step'}


class TypedBoundaryError(ValueError):
    """The actual selected native interface needs bounded implementation correction."""
INSTRUCTION = '''
Follow typed_boundary_contract from the FIRST response and every correction.
Derive fields, Java value types, nesting and collections from the supplied XML, resolved
definitions and implementing sources; users do not supply DTOs. Do not infer behavior
from tag names alone. Separate a field's value type from its format/decorator behavior:
username and family name may both be String, with different configured transformations.
Reuse compatible accepted native types/APIs and format implementations supplied in the
request, unchanged. Do not copy their implementation or invent imports for unavailable types.
Create a typed model only when the accepted types do not represent the required structure.
Never replace Context with Map, Object, JsonNode or an untyped collection at a public
boundary. Internal collections remain allowed; preserve actual configured indexed fields.
Request example SHAPE ONLY: void unformat(String xml, RequestValues values).
Response example SHAPE ONLY: String format(ResponseValues values, RuntimeOptions options).
Step example SHAPE ONLY: int execute(OperationValues values).
These names are illustrative, not domain data, tests or required class names. Derive actual
fields and behavior from this unit's evidence. RuntimeOptions exposes typed settings;
OperationValues exposes actual read/write fields, not get(String)/put(String,Object).
Declare the actual methods in contract metadata and supply matching scalar/native-object
constructor/setter binding recipes. New DTOs for conditional writes need observable presence;
preserve partial writes when an exception prevents a return. An existing candidate's missing
observability remains a comparison limitation, not itself a behavior correction request.
XML output remains String when required.
Integration must compile against accepted APIs and pass original/native comparisons;
matching DTO names or successful metadata checks alone never establish equivalence.
'''


def attach_typed_boundary(payload):
    """Attach XML field provenance and available accepted APIs without guessing Java types."""
    unit = next((payload[key] for key in ('selected_unit', 'configured_format', 'configured_unit', 'unit')
                 if isinstance(payload.get(key), dict) and payload[key].get('kind') in KINDS), payload)
    if unit.get('kind') not in KINDS:
        return False
    fields = []
    def visit(node, path):
        attributes = node.get('attributes', {})
        name = attributes.get('dataName')
        path = path + ([name] if name else [])
        if name:
            fields.append(dict(path=path, attributes=deepcopy(attributes),
                definition_id=node.get('definition_id'), reference_definition_id=node.get('reference_definition_id'),
                structure=deepcopy({key:value for key,value in node.items() if key!='children'})))
        for child in node.get('children', []):
            visit(child, path)
    visit(unit.get('effective_configuration', {}), [])
    payload['typed_boundary_contract'] = dict(version='typed-boundary-v1', kind=unit['kind'],
        configured_fields=fields, type_resolution='Use XML plus full implementing sources; do not guess unknown types.',
        referenced_definitions=deepcopy(unit.get('referenced_definitions', [])),
        accepted_native_apis=deepcopy(payload.get('converted_dependency_apis', payload.get('prerequisite_components', []))),
        output='xml_string' if unit['kind']=='response_format' else 'typed_values_and_original_outcome',
        user_supplied_dtos_required=False)
    return True


def validate_typed_boundary(bundle, contract, selection=None):
    """Check the bound interface/accessors; leave other helpers to safety/build/behavior checks."""
    if not contract:
        return
    apis = list(bundle.unit_contract.apis) if getattr(bundle, 'unit_contract', None) else [
        api for component in getattr(bundle, 'contracts', {}).values() for api in component.apis]
    sources = {name: file.content for file in bundle.files if file.path.startswith('src/main/java/')
               for name in public_api_types(file.content)}
    if selection is None and getattr(bundle,'verification_binding',None) is not None:
        from runtime.behavior_conversion.typed_boundary_selection import selected_boundary_signatures
        selection=selected_boundary_signatures(bundle,bundle.verification_binding)
    elif selection is None and contract.get('kind') in KINDS and getattr(bundle,'contracts',None):
        from runtime.behavior_conversion.typed_boundary_selection import configured_step_entry_signatures
        selection=configured_step_entry_signatures(bundle,contract['kind'])
    for api in apis:
        resolve = java_type_resolver(sources.get(api.type_name, ''), sources)
        for declaration in api.method_signatures:
            signature = _signature(declaration, resolve)
            if signature is None:
                continue  # The existing method-contract validator rejects malformed declarations.
            if selection is not None and (api.type_name,signature) not in selection:
                continue
            types = (signature[1], *signature[2])
            if signature[:3] == ('equals', 'boolean', ('java.lang.Object',)):
                continue  # Ordinary Object overrides are not generic context boundaries.
            generic = {'java.lang.Object', 'java.util.Map', 'java.util.HashMap', 'java.util.LinkedHashMap',
                       'java.util.Hashtable', 'com.fasterxml.jackson.databind.JsonNode',
                       'com.fasterxml.jackson.databind.node.ObjectNode'}
            raw_collection = re.search(r'\b(?:List|Set|Collection|Iterable)(?![\w$]|\s*<)(?:\s+\w+)?\s*(?=[,)(])',
                                       declaration)
            if any(value.removesuffix('[]') in generic for value in types) or raw_collection or re.search(
                    r'<\s*(?:java.lang.)?Object\s*>', declaration):
                raise TypedBoundaryError('Typed boundary requires scalar or native DTO inputs/results, not generic state: '+declaration+
                    '. Derive fields from supplied XML/source evidence; reuse accepted native types. Update Java, API metadata '
                    'and verification_binding together. Internal maps may remain internal.')
