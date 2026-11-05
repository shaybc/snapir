"""Verify explicit operation scenario links without inventing fixtures or component joins."""
import json
from pathlib import Path
from xml.etree import ElementTree
from models.operation_demo_scenarios import OperationDemoScenarios
from models.fixture_demo_catalogue import FixtureDemoCatalogue
from models.shared_test_fixture import SharedFixtureBank
from runtime.test_assets.store import load
from runtime.test_assets.references import resolve
from runtime.fixture_jdbc_tools.releases import file_hash
from runtime.fixture_demo.artifact_paths import demo_artifact


def prepare_catalogue(project, identity):
    """Return verified reference-only scenarios or fail with an actionable preparation reason.

    Only banks carried by this assembled operation are accepted. An explicit saved
    operation scenario is required: unrelated component scenarios are never combined.
    """
    project = Path(project).resolve()
    definition = demo_artifact(project, 'operation-demo-scenarios.json')
    if not definition.is_file():
        raise ValueError('No saved whole-operation demo scenario links the request, step resources and response lookups. '
                         'Retain '+str(definition)+' with explicit references to the accepted fixture banks; '
                         'component tests and sample-request.xml alone do not establish a coherent operation scenario.')
    scenarios = OperationDemoScenarios.model_validate(json.loads(definition.read_text(encoding='utf-8')))
    if scenarios.operation != identity:
        raise ValueError('Demo scenario belongs to another operation')
    allowed = (project / 'src/test/resources/shared-test-assets').resolve()
    roots = set()
    def value(reference):
        root = (project / reference.asset_root).resolve()
        if not root.is_relative_to(allowed):
            raise ValueError('Demo fixture is not part of the assembled operation')
        _, documents = load(root, reference.manifest_hash)
        roots.add(str(root))
        bank=SharedFixtureBank.model_validate(documents['fixtures.json'])
        if bank.unresolved:raise ValueError('Saved fixture bank has unresolved inputs')
        return resolve(bank, reference)
    catalogue, requests = {}, {}
    for scenario in scenarios.scenarios:
        if scenario.scenario_id in catalogue:
            raise ValueError('Duplicate operation demo scenario ID')
        xml = value(scenario.input_xml)
        if not isinstance(xml, str):
            raise ValueError('Demo request must reference XML text')
        ElementTree.fromstring(xml)
        if scenario.expected_xml is not None:
            from tools.behavior_verification.boundary_xml import xml_structure
            xml_structure(value(scenario.expected_xml))
        for link in scenario.links:
            if value(link.producer) != value(link.consumer):
                raise ValueError('Saved operation scenario contains a conflicting producer/consumer link')
        resources = {}
        for name, references in scenario.resources.items():
            queries = {}
            for reference in references:
                payload = value(reference)
                if not isinstance(payload, dict) or not isinstance(payload.get('queries'), list):
                    raise ValueError('Demo database resource must reference saved query definitions')
                for query in payload['queries']:
                    key = json.dumps([query['sql'], query.get('parameters', [])], sort_keys=True)
                    if key in queries and queries[key] != query:
                        raise ValueError('Conflicting saved responses for the same SQL and parameters')
                    queries[key] = query
            resources[name] = dict(fixtures=[dict(ref.model_dump(), asset_root=str((project/ref.asset_root).resolve()))
                                             for ref in references])
        catalogue[scenario.scenario_id] = dict(resources=resources)
        requests[scenario.scenario_id] = dict(input_xml=dict(scenario.input_xml.model_dump(),
            asset_root=str((project/scenario.input_xml.asset_root).resolve())),
            expected_xml=(dict(scenario.expected_xml.model_dump(),
                asset_root=str((project/scenario.expected_xml.asset_root).resolve())) if scenario.expected_xml else None),
            expected_resource_executions=scenario.expected_resource_executions)
    result = FixtureDemoCatalogue(scenarios=catalogue).model_dump(mode='json')
    selected=scenarios.selected_scenario
    if selected is not None and selected not in catalogue:
        raise ValueError('Selected operation demo scenario is missing')
    return result, dict(definition_hash=file_hash(definition), fixture_roots=sorted(roots), requests=requests,
                        selected_scenario=selected)
