"""Validate concrete fixture references and capabilities, not business equivalence."""
import json
from models.fixture_reference import FixtureReference
from runtime.test_assets.references import resolve
from runtime.format_comparison.context_discovery import validate_citations, evidence_catalog


def validate_bank(bank, sources, maximum, *, configuration=None, unit=None):
    """Reject missing/cyclic references and unsupported resource contracts before execution."""
    if len(bank.model_dump_json().encode('utf-8'))>maximum:raise ValueError('Shared fixture byte limit exceeded')
    evidence=evidence_catalog(dict(unit or {},sources=sources,effective_configuration=configuration if configuration is not None else (unit or {}).get('effective_configuration',{})))
    for identity,entry in bank.fixtures.items():
        FixtureReference(fixture_id=identity)
        validate_citations(entry.citations,evidence)
        if entry.origin=='source_backed' and not entry.citations:raise ValueError('Source-backed fixture needs citations')
        value=resolve(bank,dict(fixture_id=identity))
        if entry.kind=='xml' and not isinstance(value,str):raise ValueError('XML fixture must be an exact string')
        if entry.kind=='database':
            if not isinstance(value,dict) or set(value)!={'queries'} or not isinstance(value['queries'],list):
                raise ValueError('Database fixture requires explicit prepared queries')
            seen=set()
            for query in value['queries']:
                if set(query)-{'sql','parameters','columns','rows','exception','out_parameters'} or not isinstance(query.get('sql'),str):
                    raise ValueError('Unsupported JDBC fixture operation')
                if not isinstance(query.get('parameters'),list):raise ValueError('JDBC parameters must be explicit')
                key=json.dumps([query['sql'],query['parameters']],sort_keys=True)
                if key in seen:raise ValueError('Ambiguous JDBC fixture query')
                seen.add(key)
                columns=query.get('columns',[])
                if len(set(columns))!=len(columns) or any(not isinstance(n,str) for n in columns):raise ValueError('Invalid JDBC columns')
                if any(not isinstance(row,list) or len(row)!=len(columns) for row in query.get('rows',[])):raise ValueError('JDBC row width mismatch')
                outputs=query.get('out_parameters',{})
                if not isinstance(outputs,dict):raise ValueError('Callable output parameters must be indexed objects')
                for index,output in outputs.items():
                    if not index.isdecimal() or int(index)<1 or not isinstance(output,dict) or not isinstance(output.get('sql_type'),int):
                        raise ValueError('Callable outputs require positive parameter indices and JDBC sql_type')
                    if set(output)-{'sql_type','value','columns','rows'} or ('value' in output)==('rows' in output):
                        raise ValueError('Callable output requires a value or a cursor, not both')
                    if 'rows' in output:
                        cols=output.get('columns',[])
                        if not isinstance(cols,list) or any(not isinstance(n,str) for n in cols) or len(set(cols))!=len(cols) or not isinstance(output['rows'],list) or any(not isinstance(row,list) or len(row)!=len(cols) for row in output['rows']):
                            raise ValueError('Callable cursor columns/rows must match')
                failure=query.get('exception')
                if failure and (set(failure)-{'type','message'} or failure.get('type')!='java.sql.SQLException'):
                    raise ValueError('Unsupported JDBC exception type')
        if entry.kind=='service' and not isinstance(value,list):raise ValueError('Service fixture must be a replay sequence')


def validate_suite(suite, bank, maximum, *, direction=None, sources=(), native_sources=None, unit=None, external_contracts=None, api_inventory=None):
    """Check declared scenarios; preserve unresolved inputs without fabricating runnable cases."""
    if len(suite.scenarios)>maximum:raise ValueError('Scenario case limit exceeded; no cases dropped')
    ids=[s.scenario_id for s in suite.scenarios]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate scenario identity')
    for side in ['legacy','native']:
        proposed=getattr(suite,side+'_external_bindings',{})
        approved=(external_contracts or {}).get(side,{})
        if any(approved.get(target)!=canonical for target,canonical in proposed.items()):
            raise ValueError('External replay needs an existing explicit resource contract; business methods cannot be stubbed')
    for scenario in suite.scenarios:
        native_types=set((api_inventory or {}).get('types',{}))
        if native_sources is not None:
            from runtime.behavior_conversion.java_api_types import public_api_types
            native_types.update(name for source in native_sources for name in public_api_types(source.content))
        constructor_entry=getattr(scenario,'entry_kind','method')=='constructor'
        if hasattr(scenario,'entry_kind'):
            entry=scenario.native_entry
            if entry.context_writes or entry.output_getters or entry.output!='result' or entry.settings_bindings:
                raise ValueError('JUnit fixture entries return the raw result; boundary projections/settings require a supported comparison scenario')
            if constructor_entry and (entry.static_method or entry.arguments or entry.configuration_setters):
                raise ValueError('Constructor scenarios execute only constructor_arguments')
        if api_inventory is not None:
            from runtime.test_assets.api_contracts import validate_invocation
            validate_invocation(scenario.native_entry,api_inventory,constructor_entry=constructor_entry)
        if native_sources is not None:
            from models.format_comparison_plan import FormatComparisonEntry
            from runtime.format_comparison.bindings import resolved_binding
            resolved_binding(FormatComparisonEntry(direction=getattr(scenario,'direction','format'),binding=scenario.native_entry),
                unit or dict(effective_configuration=dict(attributes={})),native_sources,constructor_entry=constructor_entry)
        for setup in getattr(scenario,'setup',[]):
            from models.native_verification_binding import NativeVerificationBinding
            from runtime.behavior_conversion.verification_binding import _member
            if len(setup.arguments)!=len(setup.restore_getters) or not all(_member(name) for name in [setup.method_name,*setup.restore_getters]):
                raise ValueError('Static fixture configuration needs one public restoration getter per argument')
            calls=[NativeVerificationBinding(owner_type=setup.owner_type,method_name=setup.method_name,static_method=True,arguments=setup.arguments),
                *[NativeVerificationBinding(owner_type=setup.owner_type,method_name=name,static_method=True) for name in setup.restore_getters]]
            for call in calls:
                if api_inventory is not None:validate_invocation(call,api_inventory)
                if native_sources is not None:resolved_binding(FormatComparisonEntry(direction='format',binding=call),unit or dict(effective_configuration=dict(attributes={})),native_sources)
        if direction and scenario.direction!=direction:raise ValueError('Scenario selected an unrequested direction')
        refs=[*scenario.inputs.values(),*scenario.resources.values()]
        refs.extend(getattr(scenario,'configuration',{}).values())
        refs.extend(getattr(scenario,'composer_context',{}).values())
        refs.extend(ref for ref in [scenario.input_xml,getattr(scenario,'external_responses',None),getattr(scenario,'settings',None)] if ref)
        for ref in refs:resolve(bank,ref)
        for ref in scenario.resources.values():
            if bank.fixtures[ref.fixture_id].kind!='database':raise ValueError('Unsupported resource provider; capability missing')
            if ref.pointer:raise ValueError('Database resources reference a complete database fixture')
        if scenario.input_xml and not isinstance(resolve(bank,scenario.input_xml),str):raise ValueError('Scenario XML must be a string')
        setting=getattr(scenario,'settings',None)
        if setting and not isinstance(resolve(bank,setting),list):raise ValueError('Settings fixture must be an explicit control list')
        replay=getattr(scenario,'external_responses',None)
        if replay:
            responses=resolve(bank,replay)
            targets=set(getattr(suite,'legacy_external_bindings',{}).values()) & set(getattr(suite,'native_external_bindings',{}).values())
            if not isinstance(responses,list) or any(not isinstance(r,dict) or r.get('target') not in targets for r in responses):
                raise ValueError('Service replay requires explicit matching resource contracts on both sides')
        if set(getattr(scenario,'composer_resource_setters',{}).values())-set(scenario.resources):
            raise ValueError('Unknown Composer resource: composer_resource_setters must map exact context setter method names to declared resource names, not the reverse')
        for method in getattr(scenario,'composer_resource_setters',{}):
            if not method.isidentifier():raise ValueError('Invalid resource setter name')
        def visit(recipe,inside_collection=False):
            if recipe.source in {'fixture','collection'} and recipe.key not in scenario.inputs:raise ValueError('Missing scenario input: '+str(recipe.key))
            if recipe.source=='fixture' and recipe.type_name in native_types and resolve(bank,scenario.inputs[recipe.key]) is not None:
                raise ValueError('Native DTO '+recipe.type_name+' requires source=object with explicit constructor/property recipes; fixture '+str(recipe.key)+' is JSON data, not a constructed Java instance')
            if recipe.source=='context' and recipe.key not in scenario.inputs and recipe.key not in getattr(scenario,'composer_context',{}):raise ValueError('Unresolved context recipe input')
            if recipe.source=='resource' and recipe.key not in scenario.resources:raise ValueError('Missing scenario resource')
            if recipe.source=='configuration' and hasattr(scenario,'configuration') and recipe.key not in scenario.configuration:raise ValueError('Missing JUnit configuration fixture')
            if recipe.source=='item' and not inside_collection:raise ValueError('Item recipe outside a collection')
            if recipe.source=='collection' and (recipe.type_name not in {'java.util.List','java.util.Set'} or recipe.element is None):raise ValueError('Typed collection requires an element recipe')
            if recipe.source=='resource' and recipe.type_name!='java.sql.Connection':raise ValueError('Unsupported resource type')
            for child in [*recipe.arguments,*recipe.properties.values()]:visit(child,inside_collection)
            if recipe.element:visit(recipe.element,True)
        for recipe in [*scenario.native_entry.arguments,*scenario.native_entry.constructor_arguments,*scenario.native_entry.configuration_setters.values()]:visit(recipe)
        for setup in getattr(scenario,'setup',[]):
            for recipe in setup.arguments:visit(recipe)
        if (unit or {}).get('kind')!='configured_step':
            from runtime.test_assets.resource_bindings import validate_comparison_resources
            validate_comparison_resources(scenario)
        if hasattr(scenario,'assertion_citations'):validate_citations(scenario.assertion_citations,evidence_catalog(dict(unit or {},sources=sources,
            effective_configuration=(unit or {}).get('effective_configuration',{}))))
