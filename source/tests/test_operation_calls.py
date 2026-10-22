"""Exercise operation discovery, scheduling and native-service boundary safeguards."""

import json
import sqlite3
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.operation_call_tools.discovery import COMPLEX_CLASS, discover_operation_calls
from tools.operation_call_tools.ordering import operation_waves, ordered_operations
from tools.state_store_tools.operation_calls import save_graph, load_graph, plan_contracts, get_contract, set_contract_status
from tools.conversion_tools.operation_call_closure import resolve_operation_calls
from runtime.behavior_conversion.operation_calls import validate_operation_clients, validate_endpoint, order_closures


def vault(tmp_path, wiki=False):
    for folder in ('operations', 'opsteps', 'formats'):
        (tmp_path / folder).mkdir()
    def link(folder, name):
        return f'[[{folder}/{name}|{name}]]' if wiki else f'[{name}]({folder}/{name}.md)'
    for name, steps in [('A', ['AtoB', 'AtoC']), ('B', ['BtoC']), ('C', [])]:
        (tmp_path / 'operations' / (name + '.md')).write_text(
            f'# {name}\n\n---\nentity_id: {name}\nchannel: INTERNET\nsource_hash: {name}\n---\n\n## Steps\n' +
            '\n'.join('- ' + link('opsteps', step) for step in steps) +
            '\n\n## Request Format\n- F\n\n## Reply Format\n- F\n\n## Other Formats\n- csErrorReplyFormat: F\n', encoding='utf-8')
    for step, caller, target in [('AtoB','A','B'), ('AtoC','A','C'), ('BtoC','B','C')]:
        (tmp_path / 'opsteps' / (step + '.md')).write_text(
            f'# {step}\n\n---\nentity_id: {step}\nused_by_operations:\n  - {caller}\n---\n\n'
            f'## Implementation\n- {link("classes", COMPLEX_CLASS)}\n\n'
            f'## Parameters\n- opExecuteName: `{target}`\n\n## Raw Attributes\n- implClass: `{COMPLEX_CLASS}`\n', encoding='utf-8')
    (tmp_path / 'formats/F.md').write_text('# F\n\n---\nentity_id: F\n---\n\n## Structure\n<CCXML dataName="Customer"/>', encoding='utf-8')
    return tmp_path


@pytest.mark.parametrize('wiki', [False, True])
def test_markdown_calls_and_multiple_prerequisites(tmp_path, wiki):
    graph = discover_operation_calls(vault(tmp_path, wiki))
    assert graph['issues'] == []
    waves = operation_waves(graph)
    assert [waves['INTERNET/'+key]['wave'] for key in ['C','B','A']] == [1,2,3]
    assert waves['INTERNET/A']['prerequisites'] == ['INTERNET/B','INTERNET/C']
    assert waves['INTERNET/A']['calls_count'] == 2
    assert waves['INTERNET/C']['callers_count'] == 2
    graph['calls'].append(dict(graph['calls'][0], step='RepeatedCall'))
    assert operation_waves(graph)['INTERNET/A']['calls_count'] == 2


def test_unresolved_target_blocks_transitive_callers(tmp_path):
    vault(tmp_path)
    path = tmp_path / 'opsteps/BtoC.md'
    path.write_text(path.read_text().replace('`C`', '`Unknown`'))
    graph = discover_operation_calls(tmp_path)
    waves = operation_waves(graph)
    assert graph['issues']
    assert waves['INTERNET/A']['wave'] is None
    assert waves['INTERNET/B']['wave'] is None
    assert waves['INTERNET/C']['wave'] == 1
    with pytest.raises(ValueError, match='Unresolved'):
        ordered_operations(graph, graph['operations'])


@pytest.mark.parametrize('channel', ['SME', 'INTERNET', 'CUSTOM'])
@pytest.mark.parametrize('target_channel', ['XML', 'UNRELATED'])
def test_missing_inherited_view_is_diagnosed_without_global_redirect(tmp_path, channel, target_channel):
    vault(tmp_path)
    for note in (tmp_path / 'operations').glob('*.md'):
        note.write_text(note.read_text().replace('channel: INTERNET', 'channel: ' + channel))
    step = tmp_path / 'opsteps/BtoC.md'
    step.write_text(step.read_text().replace('`C`', '`SharedTarget`'))
    (tmp_path / 'operations/SharedTarget.md').write_text(
        '# SharedTarget\n\n---\nentity_id: SharedTarget\nchannel: ' + target_channel
        + '\nsource_hash: shared\n---\n\n## Steps\n- None\n')
    graph = discover_operation_calls(tmp_path)
    assert len(graph['issues']) == 1
    issue = graph['issues'][0]
    assert issue['operation'] == channel + '/B'
    assert issue['callee'] == channel + '/SharedTarget'
    if target_channel == 'XML':
        assert 'Missing inherited XML-base operation view' in issue['detail']
        assert 'Regenerate the vault' in issue['detail']
    else:
        assert 'Target is missing in caller channel' in issue['detail']
        assert 'Missing inherited XML-base' not in issue['detail']
    assert not any(call['callee'] == target_channel + '/SharedTarget' for call in graph['calls'])
    waves = operation_waves(graph)
    assert waves[channel + '/A']['wave'] is None and waves[channel + '/B']['wave'] is None
    assert waves[target_channel + '/SharedTarget']['wave'] == 1


def test_step_id_collision_is_reported(tmp_path):
    vault(tmp_path)
    path = tmp_path / 'opsteps/AtoB.md'
    path.write_text(path.read_text().replace('  - A', '  - B'))
    assert 'collision' in discover_operation_calls(tmp_path)['issues'][0]['detail']


def test_cycles_and_long_chains_do_not_recurse():
    graph = dict(operations={str(i):{} for i in range(1500)}, calls=[dict(caller=str(i),callee=str(i-1)) for i in range(1,1500)], issues=[])
    assert operation_waves(graph)['1499']['wave'] == 1500
    graph['calls'].append(dict(caller='0',callee='1'))
    waves = operation_waves(graph)
    assert waves['0']['cycle_group'].startswith('cycle-')
    assert waves['0']['cycle_group'] == waves['1']['cycle_group']
    with pytest.raises(ValueError, match='Cycle'):
        ordered_operations(graph, graph['operations'])


def test_contract_persistence_and_changes_reset_readiness(tmp_path):
    graph = discover_operation_calls(vault(tmp_path))
    conn = sqlite3.connect(':memory:')
    save_graph(conn, 'run', graph)
    plan_contracts(conn, 'run', graph, tmp_path)
    assert load_graph(conn, 'run') == graph
    contract = get_contract(conn, 'run', 'INTERNET/C')
    assert contract['path'] == '/operations/INTERNET/C'
    assert contract['status'] == 'planned'
    set_contract_status(conn, 'run', 'INTERNET/C', 'validated')
    plan_contracts(conn, 'run', graph, tmp_path)
    assert get_contract(conn, 'run', 'INTERNET/C')['status'] == 'validated'
    (tmp_path / 'formats/F.md').write_text((tmp_path / 'formats/F.md').read_text() + '\nChanged contract')
    plan_contracts(conn, 'run', graph, tmp_path)
    assert get_contract(conn, 'run', 'INTERNET/C')['status'] == 'planned'
    assert get_contract(conn, 'run', 'INTERNET/C')['fingerprint'] != contract['fingerprint']


def test_closure_attaches_target_contract_and_blocks_legacy(tmp_path):
    graph = discover_operation_calls(vault(tmp_path))
    conn = sqlite3.connect(':memory:')
    save_graph(conn, 'run', graph)
    plan_contracts(conn, 'run', graph, tmp_path)
    calls, issues = resolve_operation_calls(conn,'run','A','INTERNET',['AtoB','AtoC'],SimpleNamespace(conversion_strategy='behavior_units'))
    assert not issues
    assert len(calls) == 2
    assert calls[0]['service_contract']['path'] == '/operations/INTERNET/B'
    _, issues = resolve_operation_calls(conn,'run','A','INTERNET',['AtoB'],SimpleNamespace(conversion_strategy='legacy'))
    assert issues and 'behavior_units' in issues[0].detail
    closures = [dict(operation_id=name,channel='INTERNET') for name in ['A','B','C']]
    assert [item['operation_id'] for item in order_closures(conn,SimpleNamespace(run_id='run'),closures)] == ['C','B','A']
    with pytest.raises(ValueError, match='include prerequisite'):
        order_closures(conn,SimpleNamespace(run_id='run'),closures[:1])


def test_target_readiness_does_not_change_caller_evidence(tmp_path):
    graph = discover_operation_calls(vault(tmp_path))
    conn = sqlite3.connect(':memory:')
    save_graph(conn, 'run', graph)
    plan_contracts(conn, 'run', graph, tmp_path)
    profile = SimpleNamespace(conversion_strategy='behavior_units')
    original, issues = resolve_operation_calls(conn,'run','A','INTERNET',['AtoB','AtoC'],profile)
    assert not issues and all('status' not in call['service_contract'] for call in original)
    for status in ('assembled', 'validated'):
        set_contract_status(conn, 'run', 'INTERNET/B', status)
        calls, issues = resolve_operation_calls(conn,'run','A','INTERNET',['AtoB','AtoC'],profile)
        assert not issues and calls == original
        assert get_contract(conn, 'run', 'INTERNET/B')['status'] == status
    graph['operations']['INTERNET/B']['source_hash'] = 'changed'
    plan_contracts(conn, 'run', graph, tmp_path)
    changed, issues = resolve_operation_calls(conn,'run','A','INTERNET',['AtoB','AtoC'],profile)
    assert not issues and changed != original


def test_client_guard_rejects_dispatcher_only_and_unused_transport():
    calls = [dict(service_contract=dict(path='/operations/INTERNET/C'))]
    def bundle(source):
        return SimpleNamespace(files=[SimpleNamespace(path='src/main/java/Client.java',content=source)],unresolved_questions=[])
    with pytest.raises(ValueError, match='Composer'):
        validate_operation_clients(bundle('class CCComplexOpStep {}'),calls)
    with pytest.raises(ValueError, match='execute'):
        validate_operation_clients(bundle('class Client { HttpClient client; }'),calls)
    validate_operation_clients(bundle('class Client { HttpClient client; void call(){ client.send(request("/operations/INTERNET/C")); } }'),calls)


def test_client_path_can_use_matching_base_url_slash_normalization():
    calls = [dict(service_contract=dict(path='/operations/INTERNET/C'))]
    source = ('class Client { HttpClient client; void call(){ '
        'String url = baseUrl + (baseUrl.endsWith("/") ? "" : "/") + "operations/INTERNET/C"; '
        'client.send(request(url)); } }')
    def bundle(content):
        return SimpleNamespace(files=[SimpleNamespace(path='src/main/java/Client.java',content=content)],unresolved_questions=[])
    validate_operation_clients(bundle(source), calls)
    for invalid in (source.replace('operations/INTERNET/C', 'operations/INTERNET/Wrong'),
                    source.replace('baseUrl.endsWith', 'otherUrl.endsWith'),
                    source.replace('? "" : "/"', '? "/" : ""')):
        with pytest.raises(ValueError, match='saved target path'):
            validate_operation_clients(bundle(invalid), calls)


def test_controller_must_expose_saved_contract():
    contract = dict(path='/operations/INTERNET/C')
    with pytest.raises(ValueError, match='POST'):
        validate_endpoint({'Controller.java':'@RestController class Controller { @PostMapping("/wrong") void call(){} }'},contract)
    validate_endpoint({'Controller.java':'@RestController @RequestMapping("/operations/INTERNET") public class Controller { @PostMapping("/C") void call(){} }'},contract)


def test_caller_host_is_supplied_from_deployment_configuration():
    from runtime.behavior_conversion.operation_calls import validate_client_configuration
    calls = [dict(service_contract=dict(base_url_property='operations.customer.base-url'))]
    with pytest.raises(ValueError,match='Configure target'):
        validate_client_configuration({'application.properties':'baseUrl=http://localhost:8080'},calls)
    validate_client_configuration({'Beans.java':'@Value("${operations.customer.base-url}") String host'},calls)


def test_missing_graph_does_not_silently_convert_old_dispatcher():
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE source_artifacts (run_id TEXT,kind TEXT,logical_id TEXT,metadata_json TEXT)')
    conn.execute('INSERT INTO source_artifacts VALUES (?,?,?,?)',('run','opStep','Dispatch',json.dumps(dict(impl_class=COMPLEX_CLASS))))
    calls, issues = resolve_operation_calls(conn,'run','A','INTERNET',['Dispatch'],SimpleNamespace(conversion_strategy='behavior_units'))
    assert not calls and issues
    assert 'refresh vault import' in issues[0].detail


def test_unit_evidence_carries_saved_contract_and_changes_its_identity(tmp_path):
    from tests.test_behavior_unit_builder import setup
    from tools.conversion_tools.behavior_unit_builder import build_behavior_units
    conn, config, closure, _ = setup(tmp_path)
    units, _ = build_behavior_units(conn, config, closure)
    original = next(item for item in units if item.kind == 'configured_step')
    closure['operation_calls'] = [dict(step='CheckDatabase',callee='WEB/Target',service_contract=dict(path='/operations/WEB/Target',fingerprint='one'))]
    units, _ = build_behavior_units(conn, config, closure)
    client = next(item for item in units if item.kind == 'configured_step')
    assert client.operation_calls == closure['operation_calls']
    assert client.fingerprint != original.fingerprint
    assert client.consumers == ['WEB/WebOp']


def test_changed_target_contract_blocks_reusing_client(tmp_path):
    from runtime.behavior_conversion.operation_calls import verify_operation_contracts
    graph = discover_operation_calls(vault(tmp_path))
    conn = sqlite3.connect(':memory:')
    save_graph(conn, 'run', graph)
    plan_contracts(conn, 'run', graph, tmp_path)
    call = dict(callee='INTERNET/C',service_contract=get_contract(conn,'run','INTERNET/C'))
    graph['operations']['INTERNET/C']['source_hash'] = 'changed'
    plan_contracts(conn, 'run', graph, tmp_path)
    with pytest.raises(ValueError, match='contract changed'):
        verify_operation_contracts(conn,SimpleNamespace(run_id='run'),[call])


def test_bank_demo_maps_chain_and_multiple_direct_targets(tmp_path):
    root = Path(__file__).resolve().parents[2]
    mapper = root / 'source/composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar'
    if not mapper.exists() or not shutil.which('java'):
        pytest.skip('Build Composer Mapper and install Java to run this integration test')
    result = subprocess.run(['java','-jar',str(mapper),'--root',str(root / 'bank-demo/composer/Workspace'),
                             '--vault',str(tmp_path),'--md','--channel','INTERNET'],capture_output=True,text=True,timeout=60)
    assert result.returncode == 0, result.stderr
    graph = discover_operation_calls(tmp_path)
    assert graph['issues'] == []
    assert len(graph['calls']) == 3
    waves = operation_waves(graph)
    assert waves['INTERNET/GetClientLinksOp']['wave'] == 1
    assert waves['INTERNET/ValidateClientLinksOp']['wave'] == 2
    assert waves['INTERNET/GetClientOverviewOp']['wave'] == 3
    assert waves['INTERNET/GetClientOverviewOp']['calls_count'] == 2
    from tests.test_composer_mapper_tools import memory_conn, run_config
    from tools.composer_mapper_tools.vault_importer import import_vault
    from agents.migration_planning.agent import get_operations_for_planning
    conn = memory_conn()
    config = run_config(tmp_path).model_copy(update={'vault_root':str(tmp_path)})
    summary = import_vault(conn,str(tmp_path),config)
    assert not summary.errors
    saved = load_graph(conn,config.run_id)
    assert len(saved['calls']) == 3
    calls, issues = resolve_operation_calls(conn,config.run_id,'GetClientOverviewOp','INTERNET',
        ['OverviewValidateLinks','OverviewRefreshLinks'],SimpleNamespace(conversion_strategy='behavior_units'))
    assert len(calls) == 2 and not issues
    planning = get_operations_for_planning(conn,config.run_id)
    overview = next(item for item in planning if item['operation_id'] == 'GetClientOverviewOp')
    assert overview['operation_dependencies']['wave'] == 3


def test_demo_dispatcher_shares_context_and_propagates_return_code(tmp_path):
    if not shutil.which('javac') or not shutil.which('java'):
        pytest.skip('Java compiler is required for dispatcher execution')
    source = Path(__file__).resolve().parents[2] / 'bank-demo/composer/Workspace/WSBCC_XML/src'
    probe = tmp_path / 'DispatchProbe.java'
    probe.write_text('''import com.ibm.dse.base.*;
import com.ibm.il.dse.cc.cut.CCComplexOpStep;
public class DispatchProbe {
  public static void main(String[] args) throws Exception {
    Context context = new Context();
    CCComplexOpStep dispatch = new CCComplexOpStep();
    dispatch.setContext(context);
    dispatch.setOpExecuteName("C");
    dispatch.setService("C", new CCOperationStep() {
      public int execute() { getContext().setValueAt("called", true); return 4; }
    });
    if (dispatch.execute() != 4 || !Boolean.TRUE.equals(context.getValueAt("called"))) {
      throw new AssertionError("Nested operation lost context or return code");
    }
  }
}''', encoding='utf-8')
    sources = [source / 'com/ibm/dse/base/Context.java', source / 'com/ibm/dse/base/CCOperationStep.java',
               source / 'com/ibm/il/dse/cc/cut/CCComplexOpStep.java',probe]
    compiled = subprocess.run(['javac','-d',str(tmp_path),*map(str,sources)],capture_output=True,text=True,timeout=60)
    assert compiled.returncode == 0, compiled.stderr
    executed = subprocess.run(['java','-cp',str(tmp_path),'DispatchProbe'],capture_output=True,text=True,timeout=30)
    assert executed.returncode == 0, executed.stderr


@pytest.mark.parametrize('wiki', [False, True])
@pytest.mark.parametrize('name', ['#GPKOp', 'GPK#Op', 'Literal%23', 'Mixed%#Name', 'Space # Op', 'Call(#)'])
def test_hash_link_filenames_round_trip(tmp_path, wiki, name):
    from urllib.parse import quote
    from tools.operation_call_tools.discovery import _links, _note_path
    owner = tmp_path / 'operation.md'
    owner.write_text('source')
    note = tmp_path / 'opsteps' / (name + '.md')
    note.parent.mkdir()
    note.write_text('step')
    relative = note.relative_to(tmp_path).as_posix()
    link = '[[' + relative[:-3] + '|' + name + ']]' if wiki else '[' + name + '](' + quote(relative, safe='/') + ')'
    assert _note_path(tmp_path, owner, _links(link)[0]) == note


@pytest.mark.parametrize('wiki', [False, True])
def test_percent_escapes_are_decoded_once_and_wiki_percent_names_are_literal(tmp_path, wiki):
    from tools.operation_call_tools.discovery import _links, _note_path
    owner = tmp_path / 'operation.md'
    owner.write_text('source')
    hashed = tmp_path / '#Target.md'
    literal = tmp_path / '%23Target.md'
    hashed.write_text('hash')
    literal.write_text('percent')
    link = '[[%23Target|literal]]' if wiki else '[literal](%2523Target.md)'
    assert _note_path(tmp_path, owner, _links(link)[0]) == literal
    assert _note_path(tmp_path, owner, _links('[hash](%23Target.md)')[0]) == hashed


@pytest.mark.parametrize('link', ['[call](Call.md#Details)', '[[Call#Details|call]]', '[call](Call%23Name.md#Details)'])
def test_heading_fragments_are_removed_before_percent_decoding(tmp_path, link):
    from tools.operation_call_tools.discovery import _links, _note_path
    owner = tmp_path / 'operation.md'
    owner.write_text('source')
    note = tmp_path / ('Call#Name.md' if '%23' in link else 'Call.md')
    note.write_text('step')
    assert _note_path(tmp_path, owner, _links(link)[0]) == note


@pytest.mark.parametrize('link', ['[call](Call#Name.md)', '[[Call#Name|call]]'])
def test_old_unescaped_hash_links_prefer_the_exact_filename(tmp_path, link):
    from tools.operation_call_tools.discovery import _links, _note_path
    owner = tmp_path / 'operation.md'
    owner.write_text('source')
    (tmp_path / 'Call.md').write_text('heading decoy')
    note = tmp_path / 'Call#Name.md'
    note.write_text('actual step')
    assert _note_path(tmp_path, owner, _links(link)[0]) == note


@pytest.mark.parametrize('target', ['../outside.md', '%2e%2e%2foutside.md', '../outside.md#Heading'])
def test_encoded_link_paths_cannot_escape_the_vault(tmp_path, target):
    from tools.operation_call_tools.discovery import _note_path
    root = tmp_path / 'vault'
    root.mkdir()
    owner = root / 'operation.md'
    owner.write_text('source')
    (tmp_path / 'outside.md').write_text('outside')
    with pytest.raises(ValueError, match='Missing linked step note'):
        _note_path(root, owner, target)


@pytest.mark.parametrize('syntax', ['encoded', 'old-markdown', 'old-wiki'])
def test_legacy_hash_operation_graph_keeps_targets_and_waves(tmp_path, syntax):
    from urllib.parse import quote
    root = vault(tmp_path, wiki=syntax == 'old-wiki')
    operation = root / 'operations/A.md'
    text = operation.read_text(encoding='utf-8').replace('entity_id: A\n', 'entity_id: #GPKOp\n')
    step = root / 'opsteps/AtoB.md'
    renamed = root / 'opsteps/#GPKOp/#Call.md'
    renamed.parent.mkdir()
    renamed.write_text(step.read_text(encoding='utf-8').replace('  - A\n', '  - #GPKOp\n')
                       .replace('entity_id: AtoB\n', 'entity_id: #Call\n'), encoding='utf-8')
    step.unlink()
    relative = renamed.relative_to(root).as_posix()
    link = ('[[opsteps/#GPKOp/#Call|#Call]]' if syntax == 'old-wiki' else
            '[#Call](' + (quote(relative, safe='/') if syntax == 'encoded' else relative) + ')')
    text = text.replace('[[opsteps/AtoB|AtoB]]' if syntax == 'old-wiki' else '[AtoB](opsteps/AtoB.md)', link)
    operation.write_text(text, encoding='utf-8')
    other = root / 'opsteps/AtoC.md'
    other.write_text(other.read_text(encoding='utf-8').replace('  - A\n', '  - #GPKOp\n'), encoding='utf-8')
    graph = discover_operation_calls(root)
    assert graph['issues'] == []
    assert operation_waves(graph)['INTERNET/#GPKOp']['wave'] == 3
    assert ('INTERNET/#GPKOp', 'INTERNET/B', '#Call') in {
        (call['caller'], call['callee'], call['step']) for call in graph['calls']}
