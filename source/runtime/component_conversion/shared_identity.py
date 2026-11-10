"""Identify neutral implementations independently of run paths and consumer membership."""
from tools.shared_artifact_store.manifests import content_hash


def neutral_group(plan, group):
    """Configured occurrences and external policies retain their existing local acceptance."""
    return all(plan.components[key].kind == 'java_implementation' for key in group.members)


def implementation_identity(plan, group, profile):
    """Bind complete source resolution and semantic policy, never a local Java installation path."""
    pending, seen = list(group.members), {}
    while pending:
        key = pending.pop()
        if key in seen:
            continue
        node = plan.components[key]
        origin = node.provenance
        seen[key] = dict(kind=node.kind, label=node.label, source_hash=origin.get('source_hash'),
                         project=origin.get('source_project'), evidence=origin.get('evidence'),
                         supporting=sorted((item.get('fqcn', ''), item['source_hash']) for item in origin.get('supporting_sources', [])))
        pending.extend(node.dependencies)
    from tools.conversion_tools.component_identity import COMPONENT_POLICY_VERSION
    return content_hash(dict(roots=sorted(plan.components[key].label for key in group.members),
                             resolution=sorted(seen.values(), key=lambda item: (item['kind'], item['label'])),
                             java_version=profile.java_version, policy=COMPONENT_POLICY_VERSION,
                             **({'format_lifecycle_policy': 'format-lifecycle-v1'} if any({'format_leaf','format_wrapper','decorator'}.intersection(plan.components[key].roles) for key in group.members) else {}),
                             allowed_classes=sorted(profile.allowed_ibm_classes), allowed_artifacts=sorted(profile.allowed_ibm_artifacts)))


def request_identity(request, profile):
    """Conservatively match obligations and native dependency bytes before skipping generation."""
    from tools.shared_artifact_store.location import application_id
    excluded = {'group_id', 'input_revision', 'components', 'prerequisite_components', 'comparison_limitations', 'composition_obligations'}
    payload = {key: value for key, value in request.items() if key not in excluded}
    prerequisites = []
    for item in request.get('prerequisite_components', []):
        prerequisites.append(dict(contracts=item.get('contracts'), sources=item.get('sources'),
                                  dependencies=item.get('dependencies'), policy=item.get('policy')))
    from runtime.component_conversion.shared_bindings import request_bindings, replace_bindings
    bindings = request_bindings(request)
    payload = replace_bindings(payload, bindings)
    if 'parser_checklist' in payload:
        payload['parser_checklist'] = [{key:value for key,value in fact.items() if key != 'source_file'}
                                       for fact in payload['parser_checklist']]
    prerequisites = replace_bindings(prerequisites, bindings)
    for field in ('sources', 'parser_checklist'):
        if field in payload:
            payload[field] = sorted(payload[field], key=content_hash)
    from runtime.behavior_conversion.compatibility import versioned_requirements
    requirements = replace_bindings(versioned_requirements(profile, 'component_generation', request), bindings)
    return content_hash(dict(application=application_id(profile), request=payload,
                             requirements=sorted(requirements, key=content_hash),
                             prerequisites=sorted(prerequisites, key=content_hash)))
