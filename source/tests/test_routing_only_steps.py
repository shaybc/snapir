"""Keep structural routing nodes in native workflows without invented business implementations."""

from xml.etree import ElementTree
import pytest
from tools.conversion_tools.scoped_closure.step_semantics import routing_only, step_implementation
from tests.test_scoped_vault_identity import scoped_mapper
from tests.test_scoped_closure import import_workspace
from tests.test_scoped_workflow import settings, prepare


@pytest.mark.parametrize('name', ['OperationFailed', 'StopAfterFailure', 'Anything'])
def test_routing_only_classification_is_not_label_based(name):
    assert routing_only(ElementTree.fromstring(f'<opStep id="{name}" onOtherDo="end"/>'), {})


@pytest.mark.parametrize('xml,mappings', [
    ('<opStep id="Stop" implClass="example.Work" onOtherDo="end"/>', {}),
    ('<opStep id="Stop" onOtherDo="end"/>', {'Stop': 'example.Work'}),
    ('<opStep id="Stop" onOtherDo="end"/>', {'opStep': 'example.Work'}),
    ('<opStep id="Stop" fieldValue="business" onOtherDo="end"/>', {}),
    ('<opStep id="Stop" onOtherDo="end"><field id="business"/></opStep>', {}),
    ('<opStep id="Stop" onOtherDo="end">business</opStep>', {}),
    ('<opStep id="Stop" on0Do="end"/>', {}),
    ('<opStep id="Stop"/>', {}),
])
def test_implemented_or_ambiguous_steps_are_not_silently_skipped(xml, mappings):
    assert not routing_only(ElementTree.fromstring(xml), mappings)


def test_explicit_implementation_overrides_registry():
    node = ElementTree.fromstring('<opStep id="Work" implClass="example.Explicit"/>')
    assert step_implementation(node, {'Work': 'example.Alias', 'opStep': 'example.Default'}) == 'example.Explicit'


@pytest.mark.parametrize('route', ['onOtherDo', 'onOtherDoDefault'])
def test_terminal_step_survives_preparation_and_native_inputs_without_unit(tmp_path, scoped_mapper, route):
    def change(root):
        path = root / 'Channel/XML/Flows.xml'
        xml = ElementTree.fromstring(path.read_text())
        operation = xml.find('CCDSEServerOperation')
        for step in list(operation.findall('opStep')):
            operation.remove(step)
        operation.insert(0, ElementTree.fromstring('<opStep id="Work" implClass="example.Work" onOtherDo="StopAfterFailure"/>'))
        operation.insert(1, ElementTree.fromstring(f'<opStep id="StopAfterFailure" {route}="end"/>'))
        path.write_text(ElementTree.tostring(xml, encoding='unicode'))
    conn, root, vault = import_workspace(tmp_path, scoped_mapper, change=change)
    config, profile = settings(root, vault)
    report = prepare(conn, config, profile, selected={'XML/Flow'})
    item = report['operations']['XML/Flow']
    assert item['status'] == 'prepared', item['blockers']
    workflow = item['behavior_request']
    terminal = workflow['steps'][-1]
    assert terminal['execution_kind'] == 'routing_only'
    assert terminal['unit_id'] is None and terminal['routes'] == {route: None}
    assert terminal['note'] not in workflow['unit_bindings']
    assert not any(unit['logical_id'] == 'StopAfterFailure' for unit in item['units'])
    assert 'routing_only_steps' in workflow['requirements']
    from runtime.scoped_native.payloads import native_inputs
    closures, by_operation, units, bindings = native_inputs(report)
    native = closures[0]['scoped_workflow']
    assert native['routing_graph'][terminal['occurrence_id']] == {route: 'end'}
    assert terminal['occurrence_id'] not in bindings['XML/Flow']
    assert len([unit for unit in units.values() if unit.kind == 'configured_step']) == 1
