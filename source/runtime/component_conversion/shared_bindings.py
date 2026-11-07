"""Rebind run-local evidence identifiers while retaining immutable converted Java APIs."""
from tools.shared_artifact_store.manifests import content_hash


def request_bindings(request):
    """Give source, component and obligation identifiers stable semantic aliases."""
    bindings = {}
    for key, node in request.get('components', {}).items():
        bindings[key] = 'component:' + content_hash([node['label'], node['provenance'].get('source_hash')])
    for prerequisite in request.get('prerequisite_components', []):
        for key, contract in prerequisite.get('contracts', {}).items():
            alias = 'native:' + content_hash(sorted(api['type_name'] for api in contract['apis']))
            bindings[key] = alias
            for index, identity in enumerate(sorted(contract.get('evidence_ids', []))):
                bindings.setdefault(identity, alias + ':evidence:' + str(index))
    for source in request.get('sources', []):
        bindings[source['identity']] = 'source:' + content_hash([
            bindings.get(source.get('component_id')), source.get('role'), source['content_hash']])
    for fact in request.get('parser_checklist', []):
        value = {key: bindings.get(item, item) if isinstance(item, str) else item
                 for key, item in fact.items() if key not in {'id', 'source_file'}}
        bindings[fact['id']] = 'fact:' + content_hash(value)
    from tools.conversion_tools.scoped_reuse.fingerprints import digest
    for component, entries in request.get('source_entry_points', {}).items():
        for method in entries:
            bindings['entry-' + digest([component, method])] = 'entry:' + content_hash([bindings.get(component, component), method])
    return bindings


def replace_bindings(value, bindings):
    """Replace complete metadata identifiers, never substrings inside generated Java code."""
    if isinstance(value, str):
        return bindings.get(value, value)
    if isinstance(value, list):
        return [replace_bindings(item, bindings) for item in value]
    if isinstance(value, dict):
        return {bindings.get(key, key): replace_bindings(item, bindings) for key, item in value.items()}
    return value


def restore_bundle(bundle, saved_bindings, request):
    """Translate saved citations into the current source scope before its normal validator runs."""
    if not saved_bindings:
        return bundle
    current = {alias: identity for identity, alias in request_bindings(request).items()}
    replacement = {identity: current[alias] for identity, alias in saved_bindings.items() if alias in current}
    return bundle.__class__.model_validate(replace_bindings(bundle.model_dump(mode='json'), replacement))
