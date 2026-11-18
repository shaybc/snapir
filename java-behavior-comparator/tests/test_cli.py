"""Exercise the actual standalone CLI and HTTP transport without another tool on PYTHONPATH."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import yaml
from comparison_config_fixture import write_config
from support import sources, settings, answer

ROOT=Path(__file__).resolve().parents[1]


def test_standalone_cli_calls_own_endpoint_and_resumes(tmp_path):
    tmp_path=tmp_path/'תיקיה';tmp_path.mkdir()
    request=sources(tmp_path);received=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            payload=json.loads(body['messages'][1]['content']);received.append(payload['stage'])
            assert self.path=='/v1/chat/completions'
            value=answer(payload['stage'],payload)
            data=json.dumps(dict(choices=[dict(message=dict(content=json.dumps(value)))])).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        configured=settings();configured['model_base_url']='http://127.0.0.1:'+str(server.server_port)+'/v1'
        configured['model_api_key_environment']='COMPARATOR_TEST_KEY'
        config=tmp_path/'config.yaml';write_config(config, configured)
        inputs=tmp_path/'request.json';inputs.write_text(json.dumps(request))
        env=os.environ.copy();env['PYTHONPATH']='';env['COMPARATOR_TEST_KEY']='synthetic-not-a-real-key'
        env['PYTHONIOENCODING']='cp1252'
        snapshot=tmp_path/'progress.json'
        command=[sys.executable,str(ROOT/'run.py'),'compare','--config',str(config),'--request',str(inputs),
                 '--output',str(tmp_path/'reports'),'--progress-file',str(snapshot)]
        first=subprocess.run(command,env=env,cwd=tmp_path,capture_output=True,text=True,encoding='utf-8',timeout=120)
        result=json.loads(first.stdout)
        assert first.returncode==0,result
        assert result['decision']=='consistent_in_review' and received
        assert json.loads(snapshot.read_text())['phase']=='complete'
        count=len(received)
        second=subprocess.run(command,env=env,cwd=tmp_path,capture_output=True,text=True,encoding='utf-8',timeout=120)
        assert second.returncode==0 and len(received)==count
        assert 'synthetic-not-a-real-key' not in ''.join(path.read_text(encoding='utf-8') for path in (tmp_path/'reports').rglob('*.json'))
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)


def test_application_imports_are_independent():
    forbidden={'format_library','runtime','tools','agents','models'}
    for path in (ROOT/'comparator').glob('*.py'):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            names=[name.name for name in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
            assert not any(name.split('.')[0] in forbidden for name in names),path
