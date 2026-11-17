"""Keep upstream error bodies in bounded delivery retries, not JSON correction requests."""
import json
import logging
from types import SimpleNamespace

import pytest

from models.pipeline_configuration import PipelineConfiguration
from runtime.model_execution.adk_executor import AdkExecutor
from runtime.model_execution.response_failures import reject_delivery_error, UpstreamResponseError
from runtime.model_execution.attempt_diagnostics import capture_attempts_for_run


@pytest.mark.parametrize('body', [
    '<!DOCTYPE html><html><body>Bad gateway</body></html>',
    '\ufeff <!-- proxy page --><html>error</html>',
    '<body>Service unavailable</body>',
    'Failed to fetch response. Please try again later. <html>error</html>',
    '502 Bad Gateway', '504 Gateway Timeout', 'Service Unavailable',
    'upstream connect error or disconnect/reset before headers',
    '{"error":{"message":"unavailable","code":503}}',
    '{"error":{"type":"overloaded_error","message":"busy"}}',
])
def test_delivery_error_content_is_rejected(body):
    with pytest.raises(UpstreamResponseError): reject_delivery_error(body)


@pytest.mark.parametrize('body', [
    '{"files":[{"content":"<html>Error</html>"}]}',
    '{"fixtures":{"failure":{"value":{"error":{"code":503}}}}}',
    '{"error":"business validation error"}',
    '{"error":{"type":"validation_error","message":"missing business field"}}',
    '{"error":{"type":[],"message":"bad schema"}}',
    '{"findings":', 'not JSON', '```json\n{"findings":[]}\n```',
])
def test_schema_and_syntax_errors_and_embedded_html_are_not_delivery_errors(body):
    reject_delivery_error(body)


def test_retries_original_payload_and_records_failed_delivery(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr('runtime.model_execution.adk_executor.require_model_readiness', lambda *_: None)
    calls=[]
    executor=AdkExecutor(PipelineConfiguration(max_model_attempts=2))
    async def reply(instruction,payload):
        calls.append((instruction,payload))
        return '<html>private upstream error body</html>' if len(calls)==1 else '{"findings":["ok"]}'
    monkeypatch.setattr(executor,'_execute',reply)
    with caplog.at_level(logging.INFO), capture_attempts_for_run(tmp_path):
        assert executor.execute('original instructions','original payload')=='{"findings":["ok"]}'
    assert calls==[('original instructions','original payload')]*2
    events=[json.loads(line) for line in (tmp_path/'reports/model_attempts/events.jsonl').read_text().splitlines()]
    assert len([event for event in events if event['event']=='delivery_failed'])==1
    assert len([event for event in events if event['event']=='dispatch_attempted'])==2
    failed=next(event for event in events if event['event']=='delivery_failed')
    assert failed['error_type']=='UpstreamResponseError'
    assert failed['http_status'] is None
    assert failed['usable_model_message'] is False
    assert len([event for event in events if event['event']=='response_received'])==1
    assert (tmp_path/'reports/model_attempts/blobs'/ (failed['response_blob']+'.txt')).read_text()=='<html>private upstream error body</html>'
    assert 'No usable model message received' in caplog.text
    assert 'private upstream error body' not in caplog.text


@pytest.mark.parametrize('first', ['Failed to fetch response <html>error</html>', '{"findings":', '{"findings":[]}'])
def test_generation_uses_delivery_retries_only_for_upstream_errors(tmp_path, monkeypatch, first):
    from runtime.behavior_conversion.generation import _generate, EvidenceSummary
    from tools.state_store_tools.db import get_connection,create_all_tables
    from tools.state_store_tools.runs import upsert_run
    monkeypatch.setattr('runtime.model_execution.adk_executor.require_model_readiness', lambda *_: None)
    calls=[]
    async def reply(self,instruction,payload):
        calls.append(json.loads(payload))
        return first if len(calls)==1 else '{"findings":["accepted"]}'
    monkeypatch.setattr(AdkExecutor,'_execute',reply)
    conn=get_connection(str(tmp_path/'state.db'))
    try:
        create_all_tables(conn)
        upsert_run(conn,run_id='delivery-test',run_mode='conversion')
        result,_=_generate(conn,SimpleNamespace(run_id='delivery-test'),PipelineConfiguration(max_model_attempts=2,max_agent_task_retries=2),
            'evidence_summary','sample','Return JSON',{},EvidenceSummary)
        assert result.findings==['accepted']
        expected=1 if first.startswith('Failed') else 2
        assert conn.execute('SELECT count(*) FROM behavior_attempts').fetchone()[0]==expected
        assert ('previous_model_response' in calls[1]) is (expected==2)
        if expected==1: assert calls[0]==calls[1]
    finally:conn.close()


def test_exhausted_delivery_errors_do_not_enter_json_correction(tmp_path, monkeypatch):
    from runtime.behavior_conversion.generation import _generate, EvidenceSummary
    from tools.state_store_tools.db import get_connection,create_all_tables
    from tools.state_store_tools.runs import upsert_run
    monkeypatch.setattr('runtime.model_execution.adk_executor.require_model_readiness', lambda *_: None)
    calls=[]
    async def reply(self,instruction,payload):
        calls.append(payload)
        return '<html>Gateway Timeout</html>'
    monkeypatch.setattr(AdkExecutor,'_execute',reply)
    conn=get_connection(str(tmp_path/'state.db'))
    try:
        create_all_tables(conn)
        upsert_run(conn,run_id='delivery-test',run_mode='conversion')
        with pytest.raises(RuntimeError,match='failed after 2 attempts'):
            _generate(conn,SimpleNamespace(run_id='delivery-test'),PipelineConfiguration(max_model_attempts=2,max_agent_task_retries=3),
                'evidence_summary','sample','Return JSON',{},EvidenceSummary)
        assert len(calls)==2 and calls[0]==calls[1]
        rows=conn.execute('SELECT response,error FROM behavior_attempts').fetchall()
        assert len(rows)==1 and rows[0]['response'] is None
        assert 'No usable model message received' in rows[0]['error']
    finally:conn.close()
