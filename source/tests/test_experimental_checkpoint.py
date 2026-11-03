"""Controlled continuation preserves checkpoints and isolates package reuse."""
import json
import sqlite3
from types import SimpleNamespace
import pytest
from tools.behavior_verification.experimental_checkpoint import copy_checkpoint, file_hash
from runtime.component_conversion.saved_experiment import retain_packages, saved_package, candidate_key


def test_copy_retains_history_and_does_not_modify_origin(tmp_path):
    source = tmp_path/'original'
    database = source/'run/state/migration.db'
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE runs(run_id TEXT,run_config_json TEXT)')
        conn.execute('INSERT INTO runs VALUES (?,?)',('run',json.dumps(dict(output_root=str(source)))))
        conn.execute('CREATE TABLE attempts(attempt INTEGER)')
        conn.execute('INSERT INTO attempts VALUES (4)')
    digest = file_hash(database)
    destination = tmp_path/'experiment'
    profile = SimpleNamespace(model_dump_json=lambda **kwargs:'{"experimental_only":true}')
    result = copy_checkpoint(source,destination,'run',profile)
    assert result['original_database_hash'] == digest == file_hash(database)
    with sqlite3.connect(destination/'run/state/migration.db') as conn:
        assert conn.execute('SELECT attempt FROM attempts').fetchone()[0] == 4
        assert json.loads(conn.execute('SELECT run_config_json FROM runs').fetchone()[0])['output_root'] == str(destination)
    with pytest.raises(ValueError,match='fresh and separate'):
        copy_checkpoint(source,destination,'run',profile)


def test_saved_package_scope_cannot_affect_normal_policy():
    from models.pipeline_configuration import PipelineConfiguration
    normal = PipelineConfiguration()
    trial = normal.model_copy(deep=True)
    trial.executable_verification.mode = 'conversion_checklist_v1'
    trial.executable_verification.experimental_disable_facts = True
    with retain_packages({'group':'original.package'}):
        assert saved_package(trial,'group','new.package') == 'original.package'
        assert saved_package(normal,'group','new.package') == 'new.package'
        assert saved_package(trial,'other','new.package') == 'new.package'
    assert saved_package(trial,'group','new.package') == 'new.package'


def test_policy_identity_changes_do_not_change_original_candidate_key():
    from copy import deepcopy
    node = dict(kind='format_composition',label='Example',configuration=dict(direction='format',configuration_xml='<x/>'),
        provenance=dict(unit_fingerprint='old',source_definition_id='source',selector='unit'))
    changed = deepcopy(node)
    changed['provenance']['unit_fingerprint'] = 'new-policy'
    changed['configuration'] = dict(reversed(list(changed['configuration'].items())))
    assert candidate_key({'old-id':node}) == candidate_key({'new-id':changed})
    changed['configuration']['configuration_xml'] = '<y/>'
    assert candidate_key({'old-id':node}) != candidate_key({'new-id':changed})


def test_historical_normalized_text_requires_current_original_hash():
    from copy import deepcopy
    import hashlib
    from tools.behavior_verification.experimental_checkpoint import verify_saved_inputs
    text = 'class Example {\r\n}\r\n'
    current = dict(sources=[dict(identity='source',content=text,content_hash=hashlib.sha256(text.encode()).hexdigest())])
    prior = deepcopy(current)
    prior['sources'][0]['content'] = text.replace('\r\n','\n')
    verify_saved_inputs(prior,current)
    current['sources'][0]['content'] += '// changed'
    with pytest.raises(ValueError,match='source bytes changed'):
        verify_saved_inputs(prior,current)


def test_removed_supporting_evidence_still_checks_original_file(tmp_path):
    from tools.behavior_verification.experimental_checkpoint import verify_saved_inputs
    path = tmp_path/'Helper.java'
    path.write_bytes(b'class Helper {}\r\n')
    prior = dict(sources=[dict(identity='helper',content_hash=file_hash(path),content='class Helper {}\n')],
        components=dict(helper=dict(provenance=dict(definition_id='helper',source_file=str(path)))))
    verify_saved_inputs(prior,dict(sources=[]))
    path.write_bytes(b'class Helper { int changed; }\r\n')
    with pytest.raises(ValueError,match='supporting source changed'):
        verify_saved_inputs(prior,dict(sources=[]))


def test_regeneration_guard_permits_only_selected_complete_formats():
    from tools.behavior_verification.format_regeneration_scope import selected_composition, guarded_model_call
    payload = dict(configured_format=dict(logical_id='Selected'),components=dict(root=dict(kind='format_composition')))
    assert selected_composition(payload,{'Selected'})
    assert not selected_composition(payload,{'Other'})
    payload['components']['root']['kind'] = 'java_implementation'
    assert not selected_composition(payload,{'Selected'})
    calls = []
    call = lambda prompt,encoded:calls.append(encoded) or 'response'
    encoded = json.dumps(dict(schema=dict(title='NativeImplementation')))
    with pytest.raises(ValueError,match='outside the authorized'):
        guarded_model_call(call,False)('prompt',encoded)
    assert not calls
    assert guarded_model_call(call,True)('prompt',encoded) == 'response'
    assert guarded_model_call(call,False)('prompt',json.dumps(dict(schema=dict(title='NativeTestBundle')))) == 'response'


def test_composition_upgrade_keeps_obligations_and_old_attempt_identity(monkeypatch):
    from copy import deepcopy
    from runtime.component_conversion import runner
    from runtime.behavior_conversion.staged_adapters import task_revision_payload
    from tools.behavior_verification.format_regeneration_scope import composition_upgrade_requests
    payload = dict(configured_format=dict(logical_id='Selected'),components=dict(root=dict(kind='format_composition')),
        format_chains=[dict(occurrence_id='original-occurrence')],input_revision='same-source-policy',sources=['original'])
    original = lambda *args,**kwargs:(deepcopy(payload),'existing instructions')
    monkeypatch.setattr(runner,'build_component_request',original)
    before = task_revision_payload(payload)
    with composition_upgrade_requests({'Selected'},{'Selected':'original-java-hash'}):
        upgrade,instruction = runner.build_component_request()
        assert upgrade['format_chains'] == payload['format_chains']
        assert upgrade['sources'] == payload['sources']
        assert upgrade['input_revision'] == payload['input_revision']
        assert task_revision_payload(upgrade) != before
        repeated,_ = runner.build_component_request()
        assert task_revision_payload(repeated) == task_revision_payload(upgrade)
        assert 'without changing basic formats' in instruction
    assert runner.build_component_request is original
    with composition_upgrade_requests({'Selected'},{'Selected':'original-java-hash'},{'Selected':'Repair the missing accepted basic call'}):
        repaired,_ = runner.build_component_request()
        assert repaired['correction_feedback']=='Repair the missing accepted basic call'
        assert task_revision_payload(repaired)==task_revision_payload(upgrade)


def test_increased_cap_keeps_used_attempts_and_original_history():
    from tools.state_store_tools import staged_conversion_state as state
    with sqlite3.connect(':memory:') as conn:
        for number in range(1,5):
            assert state.reserve(conn,'run','selected-format','same-revision','tests',4,{'attempt':number})==number
            state.finish(conn,'run','selected-format','same-revision','tests',number,error='retained failure')
        history=conn.execute('SELECT * FROM staged_conversion_attempts ORDER BY attempt').fetchall()
        with pytest.raises(ValueError,match='budget exhausted'):
            state.reserve(conn,'run','selected-format','same-revision','tests',4,{})
        for number in range(5,8):
            assert state.reserve(conn,'run','selected-format','same-revision','tests',7,{'attempt':number})==number
        assert conn.execute('SELECT * FROM staged_conversion_attempts WHERE attempt<=4 ORDER BY attempt').fetchall()==history
        with pytest.raises(ValueError,match='budget exhausted'):
            state.reserve(conn,'run','selected-format','same-revision','tests',7,{})
        assert state.read(conn,'run','selected-format','same-revision','tests')['attempts']==7


def test_automatic_replay_rejects_manual_overrides_before_touching_checkpoint(monkeypatch):
    from tools.behavior_verification import resume_fact_experiment as launcher
    from models.pipeline_configuration import PipelineConfiguration
    profile=PipelineConfiguration(executable_verification={'mode':'conversion_checklist_v1','experimental_disable_facts':True})
    monkeypatch.setattr(launcher,'load_configuration',lambda _:profile)
    for override in ({'corrected_formats':['Selected=manual.json']},{'retained_metadata':['Selected=manual.json']},
                     {'retained_tests':['Selected=manual.json']},{'format_feedback':'manual.json'}):
        with pytest.raises(ValueError,match='forbids manual'):
            launcher.run('unused','unused','unused',continue_experiment=True,regenerate_formats=['Selected'],automatic_chain_replay=True,**override)


def test_automatic_generation_has_distinct_identity_and_no_prior_candidate_in_request(monkeypatch):
    from copy import deepcopy
    from runtime.component_conversion import runner
    from tools.behavior_verification.format_regeneration_scope import composition_upgrade_requests
    payload=dict(configured_format=dict(logical_id='Selected'),components={'root':dict(kind='format_composition')})
    monkeypatch.setattr(runner,'build_component_request',lambda *a,**kw:(deepcopy(payload),'existing'))
    with composition_upgrade_requests({'Selected'},{'Selected':'old-hash'}):
        old,_=runner.build_component_request()
    with composition_upgrade_requests({'Selected'},{'Selected':'old-hash'},automatic=True):
        automatic,_=runner.build_component_request()
    assert automatic['authorized_composition_upgrade']['version']!=old['authorized_composition_upgrade']['version']
    assert automatic['authorized_composition_upgrade']['manual_overrides_allowed'] is False
    assert 'previous_implementation' not in automatic and 'correction_feedback' not in automatic
