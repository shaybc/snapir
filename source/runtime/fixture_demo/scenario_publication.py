"""Validate AI selections and publish append-only data through the shared fixture store."""
from pathlib import Path
from xml.etree import ElementTree
from models.shared_test_fixture import SharedFixtureBank
from models.comparison_test_scenario import ComparisonScenarioSuite
from models.operation_demo_scenarios import OperationDemoScenarios
from runtime.test_assets.validation import validate_bank
from runtime.test_assets.references import resolve
from runtime.test_assets.store import publish
from runtime.format_comparison.context_discovery import validate_citations
from runtime.fixture_jdbc_tools.releases import digest


def validate_proposal(proposal,evidence,maximum,case_limit):
    """Check concrete schemas/references/citations; behavior is checked by later execution."""
    if proposal.operation!=evidence['operation']:raise ValueError('Scenario proposal belongs to another operation')
    if len(proposal.scenarios)>case_limit:raise ValueError('Whole-operation scenario case limit exceeded')
    sources=[*evidence['original_evidence'].get('sources',[]),*evidence['native_sources']]
    if evidence['original_evidence'].get('configuration'):
        import json
        sources.append(dict(identity='operation-configuration',content=json.dumps(
            evidence['original_evidence']['configuration'],sort_keys=True,ensure_ascii=False)))
    banks={key:SharedFixtureBank.model_validate(value['fixtures']) for key,value in evidence['saved_banks'].items()}
    catalog={s['identity']:s['content'] for s in sources}
    def citations(values):
        for citation in values:
            try:validate_citations([citation],catalog)
            except ValueError as error:
                raise ValueError('Citation must use a supplied source identity and exact literal excerpt: '
                    +citation.source_identity+'; excerpt='+repr(citation.excerpt[:300])) from error
    if proposal.new_fixtures:
        banks['generated']=SharedFixtureBank(fixtures=proposal.new_fixtures)
        for entry in proposal.new_fixtures.values():citations(entry.citations)
        validate_bank(banks['generated'],sources,maximum)
    def value(reference):
        if reference.bank not in banks:raise ValueError('Scenario selected an unknown fixture bank')
        return resolve(banks[reference.bank],dict(fixture_id=reference.fixture_id,pointer=reference.pointer))
    ids=[s.scenario_id for s in proposal.scenarios]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate whole-operation scenario ID')
    if not proposal.unresolved and (not ids or proposal.selected_scenario not in ids):
        raise ValueError('A runnable proposal needs an explicit selected whole-operation scenario')
    for scenario in proposal.scenarios:
        citations(scenario.expectation_citations)
        for ref in [scenario.input_xml,scenario.expected_xml]:
            xml=value(ref)
            if not isinstance(xml,str):raise ValueError('Operation request/expected response must be XML text')
            if '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():raise ValueError('DTD/entity-bearing demo XML is unsupported')
            if ref==scenario.input_xml:ElementTree.fromstring(xml)
            else:
                from tools.behavior_verification.boundary_xml import xml_structure
                xml_structure(xml)
        for link in scenario.links:
            if value(link.producer)!=value(link.consumer):raise ValueError('Conflicting operation producer/consumer fixture values')
        for references in scenario.resources.values():
            if not references:raise ValueError('Operation database resource has no fixture references')
            seen={}
            for ref in references:
                payload=value(ref)
                # Reuse the same concrete JDBC fixture checks for old and newly generated resources.
                from models.shared_test_fixture import SharedTestFixture
                validate_bank(SharedFixtureBank(fixtures={'resource':SharedTestFixture(kind='database',value=payload)}),[],maximum)
                for query in payload['queries']:
                    key=digest([query['sql'],query['parameters']])
                    if key in seen and seen[key]!=query:raise ValueError('Conflicting operation query responses')
                    seen[key]=query
    return banks


def publish_proposal(project,proposal,evidence,locations,fingerprint):
    """Store new data in a fresh revision and resolve explicit bank aliases to frozen references."""
    project=Path(project);locations=dict(locations)
    if proposal.new_fixtures:
        root,manifest=publish(project/'src/test/resources/shared-test-assets',
            'whole-operation-demo:'+proposal.operation,dict(input_fingerprint=fingerprint),
            SharedFixtureBank(fixtures=proposal.new_fixtures),None,ComparisonScenarioSuite(),
            definition_checks=['whole_operation_references','source_citations','jdbc_resource_shapes','expected_xml_before_execution'])
        locations['generated']=dict(asset_root=root.relative_to(project).as_posix(),manifest_hash=digest(manifest.model_dump(mode='json')))
    def reference(ref):return dict(**locations[ref.bank],fixture_id=ref.fixture_id,pointer=ref.pointer)
    result=OperationDemoScenarios(operation=proposal.operation,selected_scenario=proposal.selected_scenario,
        scenarios=[dict(scenario_id=s.scenario_id,input_xml=reference(s.input_xml),expected_xml=reference(s.expected_xml),
            resources={key:[reference(ref) for ref in refs] for key,refs in s.resources.items()},
            links=[dict(producer=reference(link.producer),consumer=reference(link.consumer)) for link in s.links],
            expected_resource_executions=s.expected_resource_executions) for s in proposal.scenarios])
    return result,locations
