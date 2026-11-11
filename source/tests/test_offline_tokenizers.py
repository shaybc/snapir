"""Exercise verified tokenizer caching and real initialization without public HTTP."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from runtime.model_execution import offline_tokenizers as offline


@pytest.fixture
def local_cache(tmp_path, monkeypatch):
    for name in ('TIKTOKEN_CACHE_DIR', 'CUSTOM_TIKTOKEN_CACHE_DIR', 'DATA_GYM_CACHE_DIR'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(offline, 'DEFAULT_CACHE', tmp_path / 'cache')
    import tiktoken.load
    # Restore the process-level offline reader after each isolated test.
    monkeypatch.setattr(tiktoken.load, 'read_file', tiktoken.load.read_file)
    return tmp_path / 'cache'


def test_cache_preserves_exact_asset_bytes_and_repairs_damage(local_cache):
    cache = offline.prepare_offline_tokenizers()
    assert cache == local_cache
    manifest = json.loads((offline.ASSET_DIRECTORY / 'manifest.json').read_text())
    paths = []
    for asset in manifest['assets']:
        path = cache / hashlib.sha1(asset['url'].encode()).hexdigest()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == asset['sha256']
        assert path.read_bytes() == (offline.ASSET_DIRECTORY / asset['file']).read_bytes()
        paths.append(path)
    paths[0].write_bytes(b'damaged')
    paths[1].unlink()
    offline.prepare_offline_tokenizers()
    assert all(path.is_file() for path in paths)
    assert hashlib.sha256(paths[0].read_bytes()).hexdigest() == manifest['assets'][0]['sha256']
    assert os.environ['TIKTOKEN_CACHE_DIR'] == os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] == str(cache)


@pytest.mark.parametrize('variable', ['TIKTOKEN_CACHE_DIR', 'CUSTOM_TIKTOKEN_CACHE_DIR', 'DATA_GYM_CACHE_DIR'])
def test_explicit_cache_is_populated_and_retained(local_cache, tmp_path, monkeypatch, variable):
    chosen = tmp_path / 'chosen cache'
    monkeypatch.setenv(variable, str(chosen))
    assert offline.prepare_offline_tokenizers() == chosen
    assert not local_cache.exists()
    assert os.environ['TIKTOKEN_CACHE_DIR'] == os.environ['CUSTOM_TIKTOKEN_CACHE_DIR'] == str(chosen)


@pytest.mark.parametrize('failure', ['missing', 'checksum', 'manifest', 'incomplete', 'permissions', 'empty', 'conflict', 'incompatible'])
def test_invalid_setup_fails_without_network(local_cache, tmp_path, monkeypatch, failure):
    assets = tmp_path / 'assets'
    shutil.copytree(offline.ASSET_DIRECTORY, assets)
    monkeypatch.setattr(offline, 'ASSET_DIRECTORY', assets)
    if failure == 'missing':
        (assets / 'cl100k_base.tiktoken').unlink()
    elif failure == 'checksum':
        (assets / 'cl100k_base.tiktoken').write_bytes(b'corrupt')
    elif failure == 'manifest':
        (assets / 'manifest.json').write_text('{invalid')
    elif failure == 'incomplete':
        manifest = json.loads((assets / 'manifest.json').read_text())
        manifest['assets'] = manifest['assets'][:1]
        (assets / 'manifest.json').write_text(json.dumps(manifest))
    elif failure == 'permissions':
        def denied(*_):
            raise PermissionError('cache is read-only')
        monkeypatch.setattr(offline, '_populate_cache', denied)
    elif failure == 'empty':
        monkeypatch.setenv('TIKTOKEN_CACHE_DIR', '')
    elif failure == 'conflict':
        monkeypatch.setenv('CUSTOM_TIKTOKEN_CACHE_DIR', str(tmp_path / 'other'))
        monkeypatch.setenv('TIKTOKEN_CACHE_DIR', str(local_cache))
    else:
        import tiktoken
        def incompatible(*_):
            raise ValueError('unsupported encoding implementation')
        monkeypatch.setattr(tiktoken, 'get_encoding', incompatible)
    with pytest.raises(offline.OfflineTokenizerError, match='Offline tokenizer setup failed'):
        offline.prepare_offline_tokenizers()


def test_uncached_remote_tokenizer_fails_instead_of_downloading(local_cache):
    offline.prepare_offline_tokenizers()
    import tiktoken.load
    with pytest.raises(offline.OfflineTokenizerError, match='public downloads are disabled'):
        tiktoken.load.read_file_cached('https://public.invalid/unsupported.tiktoken')


def test_real_litellm_and_adk_initialize_and_count_with_network_blocked(tmp_path):
    script = r'''
import asyncio, faulthandler, json, socket
faulthandler.dump_traceback_later(120)
original_connect=socket.socket.connect
original_resolve=socket.getaddrinfo
def local_connect(connection,address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):
        return original_connect(connection,address)
    raise AssertionError('Unexpected public network access: '+str(address))
def local_resolve(host,*args,**kwargs):
    if host in ('127.0.0.1','::1','localhost'):
        return original_resolve(host,*args,**kwargs)
    raise AssertionError('Unexpected public DNS lookup: '+str(host))
# Windows asyncio uses loopback sockets for its internal wake-up pipe.
socket.socket.connect = local_connect
socket.getaddrinfo = local_resolve
from runtime.model_execution.offline_tokenizers import prepare_offline_tokenizers
cache = prepare_offline_tokenizers()
print('cache prepared',flush=True)
import tiktoken
for name in ('cl100k_base','o200k_base'):
    codec=tiktoken.get_encoding(name)
    assert codec.decode(codec.encode('offline XML <Value>test</Value>'))=='offline XML <Value>test</Value>'
from google.adk.models.lite_llm import LiteLlm
print('ADK imported',flush=True)
adapter=LiteLlm(model='gemini/gemini-3.8-flash',api_key='test-only-key')
import litellm
print('LiteLLM imported',flush=True)
for model in ('gemini/gemini-3.8-flash','gpt-4o-mini'):
    assert litellm.token_counter(model=model,messages=[{'role':'user','content':'Offline sample'}])>0
import httpx
print('counting passed',flush=True)
from openai import AsyncOpenAI
requests=[]
def respond(request):
    requests.append(request)
    return httpx.Response(200,json={'id':'offline-response','object':'chat.completion','created':1,
        'model':'gpt-4o-mini','choices':[{'index':0,'message':{'role':'assistant','content':'offline answer'},'finish_reason':'stop'}]})
async def execute():
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        client=AsyncOpenAI(api_key='test-only-key',base_url='https://model.internal/v1',http_client=transport)
        result=await litellm.acompletion(model='openai/gpt-4o-mini',api_key='test-only-key',client=client,
            messages=[{'role':'user','content':'Offline sample'}])
        assert result.choices[0].message.content=='offline answer'
        # Missing provider usage may be represented as zero; exercise estimation explicitly.
        assert litellm.completion_cost(model='gpt-4o-mini',messages=[{'role':'user','content':'Offline sample'}],
            completion=result.choices[0].message.content)>0
asyncio.run(execute())
print('request completed',flush=True)
assert len(requests)==1
import os
assert os.environ['TIKTOKEN_CACHE_DIR']==os.environ['CUSTOM_TIKTOKEN_CACHE_DIR']==str(cache)
print('Offline LiteLLM initialization, token counting and simulated endpoint passed')
'''
    environment = os.environ.copy()
    environment['TIKTOKEN_CACHE_DIR'] = str(tmp_path / 'fresh cache')
    environment['CUSTOM_TIKTOKEN_CACHE_DIR'] = str(tmp_path / 'fresh cache')
    environment['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
    environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
    result = subprocess.run([sys.executable, '-B', '-c', script], env=environment,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'simulated endpoint passed' in result.stdout
