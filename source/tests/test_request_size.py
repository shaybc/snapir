"""Request-size diagnostics include evidence and instructions without exposing their contents."""
import json
import logging
import pytest
from models.pipeline_configuration import PipelineConfiguration
from runtime.behavior_conversion.request_context import encode_request
from runtime.behavior_conversion.request_size import log_request_size


def events(caplog):
    return [json.loads(record.getMessage().split('Model request size: ',1)[1]) for record in caplog.records
            if record.name=='runtime.behavior_conversion.request_size']


def test_utf8_units_file_contents_schema_and_instructions_are_counted_without_exposing_text(caplog):
    request=dict(unit_id='unit-1',slice_sources=[dict(original_identity='original.java',content='private-source-🙂'),
        dict(original_identity='original.java',content='second-method')],
        files=[dict(path='Test.java',content='test-code')],schema={'secret_marker':'schema-value'})
    encoded=json.dumps(request,ensure_ascii=False); instruction='private-instruction-אב'
    with caplog.at_level(logging.INFO): report=log_request_size(request,encoded,instruction,100000,stage='test')
    expected=len((encoded+instruction).encode('utf-8'))
    assert report['total']['bytes']==expected and report['total']['characters']==len(encoded)+len(instruction)
    assert report['total']['KB']==round(expected/1000,6)
    assert report['total']['MB']==round(expected/1000000,9) and report['total']['GB']==round(expected/1000000000,12)
    assert report['embedded_files']==2 and report['embedded_content_blocks']==3
    assert sum(item['bytes'] for item in report['components'].values())+report['json_envelope']['bytes']==report['json_payload']['bytes']
    assert report['json_payload']['bytes']+report['instructions']['bytes']==expected
    for secret in ('private-source','second-method','test-code','schema-value','private-instruction'): assert secret not in caplog.text
    assert events(caplog)[0]['decision']=='fits_budget'


def test_exact_character_boundary_and_rejected_size_are_logged(caplog,monkeypatch):
    monkeypatch.setattr('runtime.behavior_conversion.request_context.attach_composer_behavior',lambda value:dict(value))
    payload={'sources':[{'identity':'source','content':'abc'}]}
    size=len(json.dumps(payload,ensure_ascii=False))+len('Convert')
    with caplog.at_level(logging.INFO): encode_request(payload,'Convert',size)
    assert events(caplog)[-1]['decision']=='fits_budget'
    caplog.clear()
    with caplog.at_level(logging.INFO),pytest.raises(ValueError,match=str(size)+' characters > '+str(size-1)):
        encode_request(payload,'Convert',size-1)
    assert [item['stage'] for item in events(caplog)]==['initial_budget_check','after_correction_compaction']
    assert all(item['decision']=='too_large' and item['total']['characters']==size for item in events(caplog))
    assert payload['sources'][0]['content']=='abc'


def test_compacted_request_is_measured_again_before_it_is_allowed(caplog,monkeypatch):
    monkeypatch.setattr('runtime.behavior_conversion.request_context.attach_composer_behavior',lambda value:dict(value))
    monkeypatch.setattr('runtime.behavior_conversion.correction_payload.compact_correction',lambda value:{'source':'retained'})
    with caplog.at_level(logging.INFO): actual,encoded=encode_request({'source':'x'*100},'Convert',50)
    logged=events(caplog)
    assert [item['decision'] for item in logged]==['too_large','fits_budget']
    assert logged[-1]['total']['characters']==len(encoded)+7 and actual=={'source':'retained'}


def test_new_default_allows_2700k_characters_and_counts_bytes_separately(caplog,monkeypatch):
    assert PipelineConfiguration().behavior_context_chars==2700000
    assert PipelineConfiguration(behavior_context_chars=300000).behavior_context_chars==300000
    monkeypatch.setattr('runtime.behavior_conversion.request_context.attach_composer_behavior',lambda value:dict(value))
    payload={'content':'🙂'*1000000}
    with caplog.at_level(logging.INFO): encode_request(payload,'Convert',PipelineConfiguration().behavior_context_chars)
    report=events(caplog)[-1]
    assert report['decision']=='fits_budget' and report['total']['bytes']>1000000 and report['total']['characters']>300000
    with pytest.raises(ValueError,match='budget'): encode_request(payload,'Convert',300000)


def test_legacy_surrogate_evidence_does_not_break_diagnostics(caplog):
    with caplog.at_level(logging.INFO): report=log_request_size({'value':'\ud800'},'{"value":"\\ud800"}','Convert',1000,stage='test')
    assert report['decision']=='fits_budget'


def test_request_budget_defaults_and_explicit_saved_limits():
    profile = PipelineConfiguration()
    assert profile.metadata_checklist_request_chars == 2700000
    assert profile.format_comparison.discovery_request_chars == 2700000
    assert profile.test_preparation.request_chars == 2700000
    assert PipelineConfiguration(behavior_context_chars=2700000).behavior_context_chars == 2700000
    assert PipelineConfiguration(behavior_context_chars=900000).behavior_context_chars == 900000
    with pytest.raises(ValueError):
        PipelineConfiguration(behavior_context_chars=2700001)
