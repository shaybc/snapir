"""Select complete original group source and exact prerequisite evidence for bounded generation."""
from pathlib import Path
from models.native_component_bundle import NativeComponentBundle
from runtime.behavior_conversion.request_context import encode_request
from runtime.behavior_conversion.testing_contract import attach_testing_contract
from agents.behavior_conversion.component_generation import component_instruction
from tools.conversion_tools.component_identity import component_target, input_revision
from tools.behavior_verification.component_artifacts import verify_original_sources
from runtime.component_conversion.source_evidence import component_sources
from runtime.component_conversion.saved_experiment import saved_package


def basic_group(plan, group):
    """CF3 converts Java helpers/leaves/decorators; steps and composition wait for CF4/CF5."""
    return all(plan.components[key].kind == 'java_implementation' and
        not (set(plan.components[key].roles) - {'utility', 'format_leaf', 'decorator'}) for key in group.members)


def build_component_request(plan, group, boundaries, dependencies, profile, *, check_budget=True, units=None):
    """Keep exact source and parser obligations; reject indivisible oversized groups without summaries."""
    if any(plan.components[key].kind=='java_implementation' and not
           {'step_implementation','format_leaf','format_wrapper','decorator'}.intersection(plan.components[key].roles)
           for key in group.members):
        raise ValueError('Supporting Java source is not a standalone format or operation-step generation target')
    from runtime.component_conversion.steps import source_bindings, configured_step
    from runtime.component_conversion.formats import format_source_bindings, configured_format
    bindings = source_bindings(plan, group)
    bindings.update(format_source_bindings(plan, group, units or {}))
    if bindings:
        from tools.conversion_tools.component_identity import component_group
        for target in bindings.values(): verify_original_sources(plan, component_group(plan, target))
    else: verify_original_sources(plan, group)
    step = configured_step(plan, group, units or {})
    composed = configured_format(plan, group, units or {})
    sources, entries, checklist = component_sources(plan, group, bindings), {}, {}
    from runtime.behavior_conversion.verification_mode import facts_disabled
    skip_facts = facts_disabled(profile)
    composition_obligations={}
    basic_members={key for key in group.members if composed is None and {'format_leaf','format_wrapper','decorator'}.intersection(plan.components[key].roles)}
    basic_format=bool(basic_members)
    for key in group.members:
        node = plan.components[bindings.get(key, key)]
        identity = node.provenance['definition_id']
        basic_element=key in basic_members
        methods = set()
        for unit_id, boundary in boundaries['boundaries'].items():
            if unit_id not in plan.components[key].unit_ids:
                continue
            graph = boundary.get('reachable_slice') or {}
            composition_nodes=set((boundary.get('basic_parser_checklist') or {}).get('composition_code_nodes',[])) if basic_element else set()
            for method in graph.get('nodes', []):
                if method['source_identity'] == identity and method['source_hash'] == node.provenance['source_hash'] and method['kind'] == 'method' and method.get('id') not in composition_nodes:
                    methods.add(method['signature'])
            full_checklist=boundary.get('parser_checklist') or {}
            selected_checklist={} if skip_facts else full_checklist
            if basic_element and not skip_facts:
                selected_checklist=boundary.get('basic_parser_checklist') or {}
                if selected_checklist.get('status')!='extracted' or selected_checklist.get('fact_scope')!='basic_element':
                    raise ValueError('Basic formats/decorators require the current deterministic basic-element fact collector')
                basic_ids={item['id'] for item in selected_checklist.get('items',[])}
                composition_obligations.update({item['id']:item for item in full_checklist.get('items',[]) if
                    item['source_identity']==identity and item['id'] not in basic_ids})
            for item in selected_checklist.get('items', []):
                if item['source_identity'] == identity and item['source_hash'] == node.provenance['source_hash']:
                    existing = checklist.get(item['id'])
                    if existing and {name:value for name,value in existing.items() if name!='path_certainty'} != {name:value for name,value in item.items() if name!='path_certainty'}:
                        raise ValueError('Conflicting parser checklist provenance')
                    checklist[item['id']] = dict(item, path_certainty='uncertain' if existing and
                        existing['path_certainty']=='uncertain' else item['path_certainty'])
        if composed is not None:
            from runtime.component_conversion.formats import current_format_boundary
            boundary=current_format_boundary(units[composed['unit_id']],boundaries)
            if boundary.get('analysis_status')!='identified' or not skip_facts and (boundary.get('parser_checklist') or {}).get('status')!='extracted':
                raise ValueError('Complete format requires identified original boundary and parser checklist')
            methods={boundary['legacy_method']['signature']}
            checklist={} if skip_facts else {item['id']:item for item in boundary['parser_checklist']['items']}
        if not methods:
            raise ValueError('Component has no parser-backed entry points: ' + node.label)
        entries[key] = sorted(methods)
    revision = input_revision(plan, group, component_target(profile))
    from runtime.component_conversion.shared_identity import neutral_group, implementation_identity
    package_revision = implementation_identity(plan, group, profile) if neutral_group(plan, group) else revision
    from tools.conversion_tools.scoped_reuse.fingerprints import digest
    requirements = {'entry-' + digest([key, method]): 'Exercise original entry point ' + method
                    for key, methods in entries.items() for method in methods}
    request = dict(group_id=group.group_id, input_revision=revision, kind='basic_component',
        native_package=saved_package(profile,group.group_id,'com.company.generated.components.c' + package_revision[:16],
            {key:plan.components[key] for key in group.members}),
        components={key: plan.components[key].model_dump(mode='json') for key in group.members},
        source_entry_points=entries, sources=sources,
        parser_checklist=[] if skip_facts else [checklist[key] for key in sorted(checklist)], analysis_tool_hash=boundaries['analysis_tool_hash'],
        prerequisite_components=dependencies, java_version=profile.java_version, requirements=requirements,
        validation_scope='build_and_tests', behavioral_equivalence='not_established',
        comparison_limitations=['No independent component invocation adapter; whole configured-unit comparison remains required.'])
    if basic_format:
        request['composition_obligations']=[dict(checklist_id=key,source_identity=composition_obligations[key]['source_identity'],
            source_hash=composition_obligations[key]['source_hash'],owner='complete_configured_format') for key in sorted(composition_obligations)]
    if step is not None:
        request.update(kind='configured_step', configured_unit=step, configuration_evidence_ids=[step['source_definition_id']],
            operation_calls=step['operation_calls'], service_connections=step['service_connections'])
        request['requirements'].update({'configured-step-values': 'Initialize and use this occurrence\'s exact attributes and runtime state',
            'configured-step-outcomes': 'Preserve original integer outcomes, state changes, exceptions and external effects without routing siblings'})
    elif any('step_implementation' in plan.components[key].roles for key in group.members):
        request['kind'] = 'step_implementation'
    if composed is not None:
        request.update(kind='format_composition',configured_format=composed,configuration_evidence_ids=[composed['source_definition_id']],
            verification_boundary={name:boundary[name] for name in ('unit_id','source_manifest_hash','configuration_hash')},
            verification_policy=profile.unit_verification_policy.model_dump(mode='json'),
            verification_authorizations=[item.model_dump(mode='json') for item in profile.unit_verification_authorizations],
            boundary_verification_version='component-format-boundary-v1',
            comparison_limitations=['Observed original/native boundary comparison does not prove exhaustive equivalence or final acceptance.'])
        request['requirements'].update({'configured-format-structure':'Preserve configured structure, field/reference order, collection semantics and decorator order',
            'configured-format-boundary':'Invoke validated implementations and match original output/state/exception behavior at this configured direction'})
    elif any('format_wrapper' in plan.components[key].roles for key in group.members):
        request['kind']='format_implementation'
    from runtime.component_conversion.format_chains import attach_format_chains
    attach_format_chains(request,plan,group,units or {})
    from agents.behavior_conversion.step_component import step_instruction
    specific = step_instruction(request['kind'])
    if skip_facts:
        from runtime.behavior_conversion.verification_mode import test_based_mode
        specific+= ('\nSupported test-based conversion: parser facts and fact validation are disabled. Leave checklist mappings empty and checklist_answers null. Preserve all source behavior, API, settings, dependency, chain, compilation and JUnit requirements.' if test_based_mode(profile) else
            '\nExperimental test only: parser facts and fact validation are disabled. Leave checklist mappings empty and checklist_answers null. Preserve all source behavior, API, settings, dependency, chain, compilation and JUnit requirements.')
    if request.get('format_chain_policy'):
        from runtime.component_conversion.format_chains import INSTRUCTION
        specific+='\n'+INSTRUCTION
    instruction_factory=component_instruction; schema=NativeComponentBundle
    if composed is not None:
        from agents.behavior_conversion.format_component import format_instruction
        from models.native_format_component_bundle import NativeFormatComponentBundle
        instruction_factory=format_instruction; schema=NativeFormatComponentBundle
    elif request['kind']=='format_implementation':
        from agents.behavior_conversion.format_component import FORMAT_IMPLEMENTATION_INSTRUCTION
        specific+=FORMAT_IMPLEMENTATION_INSTRUCTION
    from runtime.behavior_conversion.typed_boundaries import attach_typed_boundary, INSTRUCTION as TYPED_BOUNDARY_INSTRUCTION
    if attach_typed_boundary(request):
        specific += '\n' + TYPED_BOUNDARY_INSTRUCTION
    request['component_generation_policy'] = digest(dict(instruction=instruction_factory()+specific, schema=schema.model_json_schema()))
    from runtime.behavior_conversion.verification_mode import conversion_mode,policy_payload
    if conversion_mode(profile):
        request['conversion_acceptance_policy']=policy_payload(profile)
        request['component_generation_policy']=digest(dict(base=request['component_generation_policy'],conversion_policy=policy_payload(profile)))
    pins = {}
    for dependency in dependencies:
        from runtime.dependency_policy import canonical_dependencies
        for selected in canonical_dependencies(profile,dependency.get('dependencies', []),historical=True):
            pin=selected.model_dump(mode='json')
            key = (pin['group_id'], pin['artifact_id'])
            if key in pins and (pins[key]['version'], pins[key]['scope']) != (pin['version'], pin['scope']):
                raise ValueError('Conflicting prerequisite dependency pins')
            pins[key] = pin
    from runtime.dependency_policy import inventory
    request['known_dependencies'] = inventory(profile,list(pins.values()))
    if step is not None:
        from runtime.behavior_conversion.connection_contract import attach_connections
        attach_connections(request, step['service_connections'])
    attach_testing_contract(request, profile)
    from runtime.behavior_conversion.compatibility import versioned_requirements
    if step is not None or composed is not None:
        # Unit-only obligations must reach the code generator, not just the later binding checker.
        configured = step if step is not None else composed
        request['requirements'].update({item['requirement_id']:item['description'] for item in
            versioned_requirements(profile,'unit',dict(kind=configured['kind'],requirements={}))})
    platform = (request.get('testing_contract') or {}).get('requirement', {}).get('requirement_id')
    request['requirements'] = {item['requirement_id']: item['description'] for item in
        versioned_requirements(profile, 'component_generation', request) if item['requirement_id'] != platform}
    allowed = {item['identity'] for item in request['sources']} | set(request.get('configuration_evidence_ids', []))
    allowed.update(identity for dependency in dependencies for identity in dependency.get('evidence_ids', []))
    request['allowed_evidence_ids'] = sorted(allowed)
    request['coverage_response_example'] = {'coverage': {key: [
        'src/test/java/' + request['native_package'].replace('.', '/') + '/ComponentBehaviorTest.java'
    ] for key in request['requirements']}}
    request['expected_contract_fields'] = {}
    from runtime.behavior_conversion.verification_mode import executable_mode,policy_payload
    if executable_mode(profile):request['executable_verification']=policy_payload(profile)
    for key in group.members:
        node = plan.components[key]
        own = node.configuration.get('definition_id') or node.provenance.get('definition_id') or node.provenance.get('source_definition_id')
        request['expected_contract_fields'][key] = dict(component_id=key,source_entry_points=entries[key],
            configuration_mode='specialized' if node.kind in {'configured_step','format_composition'} else 'parameterized',
            evidence_ids=[own],dependencies=node.dependencies)
    instruction = instruction_factory(request.get('known_dependencies', [])) + specific
    from agents.behavior_conversion.native_instructions import java_compatibility_instruction
    instruction += '\n' + java_compatibility_instruction(profile.java_version)
    # The same encoder runs again with correction feedback immediately before each actual request.
    if check_budget:
        encode_request(dict(request, schema=schema.model_json_schema()), instruction, profile.behavior_context_chars)
    return request, instruction


def prerequisite_sources(results):
    """Read validated owned production sources; never send sibling tests or unrelated operations."""
    import json
    sources, dependencies = {}, []
    for key, result in sorted(results.items()):
        root = Path(result.artifact_root)
        report = json.loads((root / result.validation_report).read_text(encoding='utf-8'))
        owned = report.get('owned_sources')
        if not owned or any(name not in result.files or not name.startswith('src/main/java/') for name in owned):
            raise ValueError('Prerequisite lacks a checked component source ownership manifest')
        files = {name: (root / name).read_text(encoding='utf-8') for name in owned}
        for name, content in files.items():
            if name in sources and sources[name] != content:
                raise ValueError('Conflicting native prerequisite files')
            sources[name] = content
        dependencies.extend(report.get('dependencies', []))
    return sources, dependencies
