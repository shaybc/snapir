"""Comparison decisions and evidence receipts gate publication without replacing previous candidates."""
import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from format_library.files import read_json
from format_library.generated_files import extract
from format_library.planning import build_plan
from format_library.workspaces import prepare
from test_tool import config, evidence, response, generate


def test_generation_calls_cli_with_original_dependencies_and_native_sources(config):
    folder=prepare(config,build_plan(evidence(config,{'example.Work':[]})))[0]
    candidate=generate(config,folder)
    receipt=read_json(candidate/'candidate.json')
    assert receipt['comparison']['decision']=='consistent_in_review'
    request=read_json(folder/'attempts/test/comparison-request.json')
    assert request['targets'][0]['original_class']=='example.Work'
    assert request['original']['sources']
    assert request['generated']['dependency_sources']
    assert request['original']['entry_methods']


@pytest.mark.parametrize('decision',['differences_found','inconclusive'])
def test_unaccepted_comparison_keeps_staged_code_feedback_and_previous_candidate(config,decision):
    folder=prepare(config,build_plan(evidence(config,{'example.Work':[]})))[0]
    generate(config,folder);before=(folder/'latest.json').read_bytes()
    Path(config['comparison_config_path']).write_text(json.dumps(dict(decision=decision)))
    attempt=folder/'attempts/second';attempt.mkdir()
    with pytest.raises(ValueError,match='Behavior comparison'):
        extract(folder,read_json(folder/'component.json'),response(read_json(folder/'component.json')),
                dict(prerequisites=[]),attempt,config=config)
    assert (attempt/'candidate').is_dir()
    assert read_json(attempt/'comparison-feedback.json')['remarks']
    assert (folder/'latest.json').read_bytes()==before
    assert not (folder/'generated/second').exists()


def test_stale_comparison_evidence_is_rejected(config):
    Path(config['comparison_config_path']).write_text('{"stale":true}')
    folder=prepare(config,build_plan(evidence(config,{'example.Work':[]})))[0]
    with pytest.raises(ValueError,match='does not match'):
        generate(config,folder)
    assert not (folder/'latest.json').exists()


def test_comparison_feedback_retains_limit_root_causes_and_reuse_counters(config):
    details=dict(root_causes=[dict(id='limit-max_model_calls',category='limit_exhausted',
        message='max_model_calls exhausted: 200 used / 200 limit',
        limit=dict(setting='max_model_calls',used=200,limit=200,stage='mapping',detail=''),
        occurrences=4,affected=['b1','b2'],stages=['mapping','coverage'])],
        budgets=dict(max_model_calls=dict(used=200,limit=200,exhausted=True)),
        calls_by_stage=dict(mapping=180,inventory=20),interactions=[dict(attempted=0,unmapped_behaviors=2)],
        mapping_reuse=dict(preferred_pages=4,preferred_matches=3),cache=dict(reused_receipts=10,migrated_receipts=2))
    Path(config['comparison_config_path']).write_text(json.dumps(dict(decision='inconclusive',**details)))
    folder=prepare(config,build_plan(evidence(config,{'example.Work':[]})))[0]
    with pytest.raises(ValueError,match='inconclusive'):
        generate(config,folder)
    feedback=read_json(folder/'attempts/test/comparison-feedback.json')
    assert all(feedback[key]==value for key,value in details.items())
    assert not (folder/'latest.json').exists()



@pytest.mark.parametrize('different',[False,True])
def test_real_comparator_cli_and_http_review_gate_generation(config,monkeypatch,tmp_path,different):
    from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
    from threading import Thread
    import yaml
    from format_library.files import file_hash
    received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            payload=json.loads(body['messages'][1]['content']);stage=payload['stage'];received.append(stage)
            if stage=='boundary':
                value=dict(input_mapping='Same String input.',output_mapping='Same String output.',
                    context_mapping='No state.',exception_mapping='Same exceptions.',uncertainties=[])
            elif stage=='inventory':
                chunk=payload['evidence'][payload['primary']]
                value=dict(behaviors=[dict(description='Return input',conditions='Any string',result='Input string',exceptions='None',
                    context_effects='None',state_fields=[],covered_facts=[fact['id'] for fact in chunk['facts']])],ignored_facts=[],no_behavior_reason='')
            elif stage=='mapping':
                value=dict(candidates=[item['id'] for item in payload['generated_catalog'] if item['kind']=='method'],reason='Corresponding formatter.')
            elif stage=='coverage':
                value=dict(status='accounted',behaviors=[item['id'] for item in payload['original_behaviors']],reason='Native return implements the original behavior.')
            else:
                assert stage in {'compare','review_difference','interaction'},stage
                value=dict(verdict='difference' if different else 'consistent',explanation='Return value changed.' if different else 'Same return value.',
                    original_outcome='Input value',generated_outcome='changed' if different else 'Input value',suggested_action='Restore input value.' if different else 'No correction.',
                    counterexample='Input abc returns abc originally and changed natively.' if different else '',
                    original_evidence=[next(iter(payload['original_evidence']))],generated_evidence=[next(iter(payload['generated_evidence']))])
            content=json.dumps(dict(choices=[dict(message=dict(content=json.dumps(value)))])).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        comparison_config=tmp_path/'real-comparator.yaml'
        comparison_config.write_text('{}')
        shared_path=Path(config['_common_config_path'])
        shared=yaml.safe_load(shared_path.read_text())
        shared.update(model_name='openai/synthetic-review',model_provider='litellm',
            model_base_url='http://127.0.0.1:'+str(server.server_port)+'/v1',model_api_key_environment='COMPARISON_E2E_KEY')
        shared_path.write_text(yaml.safe_dump(shared))
        config.update(shared)
        if different:
            # A comparator-local connection override must also work through the format-tool CLI handoff.
            comparison_config.write_text(yaml.safe_dump({key:shared[key] for key in
                ('model_name','model_provider','model_base_url','model_api_key_environment')}))
            shared.update(model_provider='mock',model_name='unused-default',model_base_url='')
            shared_path.write_text(yaml.safe_dump(shared))
        monkeypatch.setenv('COMPARISON_E2E_KEY','synthetic-local-key')
        root=Path(__file__).resolve().parents[2]
        config['comparison_command']=[sys.executable,str(root/'java-behavior-comparator/run.py')]
        config['comparison_config_path']=str(comparison_config)
        data=evidence(config,{'example.Work':[]})
        original=Path(data['classes']['example.Work']['file'])
        original.write_text('package example; public class Work {public String format(String value){return value;}}')
        data['hashes'][str(original)]=file_hash(original)
        folder=prepare(config,build_plan(data))[0];manifest=read_json(folder/'component.json')
        payload=json.loads(response(manifest))
        result='"changed"' if different else 'value'
        payload['files'][0]['content']=payload['files'][0]['content'].replace('{}','{public String format(String value){return '+result+';}}')
        attempt=folder/'attempts/e2e';attempt.mkdir()
        if different:
            with pytest.raises(ValueError,match='differences_found'):
                extract(folder,manifest,json.dumps(payload),dict(prerequisites=[]),attempt,config=config)
            assert not (folder/'latest.json').exists()
            feedback=read_json(attempt/'comparison-feedback.json')
            assert feedback['remarks'][0]['counterexample'] and feedback['source_locations']
            assert 'review_difference' in received
        else:
            candidate=extract(folder,manifest,json.dumps(payload),dict(prerequisites=[]),attempt,config=config)
            assert read_json(candidate/'candidate.json')['comparison']['decision']=='consistent_in_review'
        assert {'boundary','inventory','mapping','compare','coverage'}<=set(received)
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
