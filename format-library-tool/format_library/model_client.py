"""Isolated API delivery with real-content inactivity tracking and local attempt records."""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from format_library.configuration import TOOL_ROOT
from format_library.files import read_json, write_json


def delivery_failure(text):
    """Identify empty, HTML and recognizable upstream-error bodies, not model JSON errors."""
    stripped = text.strip()
    if stripped.startswith(('{', '[')):
        return False
    return not stripped or bool(re.search(r'<!doctype\s+html|<html\b|<body\b|<head\b', stripped, re.I)) or stripped.lower().startswith(
        ('failed to fetch response', 'bad gateway', 'upstream request timeout', 'gateway timeout', 'service unavailable'))


def receive(config, request_path):
    """Kill an inactive API worker; only nonempty returned content resets the timeout."""
    command = [sys.executable, '-m', 'format_library.model_client', config['_config_path'], str(request_path)]
    process = subprocess.Popen(command, cwd=TOOL_ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding='utf-8', errors='replace')
    messages = queue.Queue()
    def read():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)
    threading.Thread(target=read, daemon=True).start()
    last = last_notice = time.monotonic()
    chunks, completed = [], False
    response_file = Path(request_path).parent / 'response.partial.txt'
    try:
        while True:
            try:
                line = messages.get(timeout=min(1, config['model_timeout_seconds']))
            except queue.Empty:
                line = ''
            if line is None:
                break
            if line:
                event = json.loads(line)
                if event.get('error'):
                    raise ValueError('No model message delivered: ' + event['error'])
                delta = event.get('delta')
                if isinstance(delta, str) and delta:
                    chunks.append(delta)
                    with response_file.open('a', encoding='utf-8') as stream:
                        stream.write(delta)
                    last = time.monotonic()
                    if last - last_notice >= 5:
                        print('Receiving model content (' + str(sum(map(len, chunks))) + ' characters)', flush=True)
                        last_notice = last
                if event.get('done'):
                    completed = True
            if time.monotonic() - last >= config['model_timeout_seconds']:
                raise ValueError('No model content received within the inactivity timeout; heartbeat messages do not count')
        text = ''.join(chunks)
        if not completed or delivery_failure(text):
            raise ValueError('No model message delivered: empty, HTML, upstream error or incomplete provider response')
        return text
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()


def convert(config, folder):
    """Serialize conversions within one component folder; preserve all prior attempts."""
    from format_library.locking import exclusive
    folder = Path(folder).resolve()
    if not (folder / 'component.json').is_file():
        raise ValueError('Select a prepared component folder')
    with exclusive(folder / '.conversion.lock'):
        return _convert(config, folder)


def _convert(config, folder):
    """Refresh inputs and generate a candidate; retry delivery failures only."""
    from format_library.prompts import build_request
    from format_library.generated_files import extract
    folder = Path(folder).resolve()
    if not config.get('model_name') or 'REPLACE' in config['model_name'] or 'REPLACE' in config['model_base_url']:
        raise ValueError('Configure the real model_name and model_base_url before conversion')
    if not os.environ.get(config['model_api_key_environment']):
        raise ValueError('Set the API-key environment variable: ' + config['model_api_key_environment'])
    manifest = read_json(folder / 'component.json')
    request = build_request(config, folder, manifest)
    for number in range(config['max_model_attempts']):
        identity = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8]
        attempt = folder / 'attempts' / identity
        attempt.mkdir(parents=True)
        write_json(attempt / 'request.json', request)
        print('Model delivery attempt ' + str(number + 1), flush=True)
        try:
            response = receive(config, attempt / 'request.json')
        except (ValueError, OSError) as error:
            write_json(attempt / 'result.json', dict(status='delivery_failed', message=str(error), model_message_received=False))
            print(str(error), flush=True)
            if number + 1 == config['max_model_attempts']:
                raise
            continue
        (attempt / 'response.txt').write_text(response, encoding='utf-8')
        try:
            destination = extract(folder, manifest, response, request, attempt)
        except (ValueError, KeyError, TypeError) as error:
            write_json(attempt / 'result.json', dict(status='invalid_response', message=str(error), model_message_received=True))
            raise ValueError('Model response saved but not accepted: ' + str(error)) from error
        write_json(attempt / 'result.json', dict(status='generated' if destination else 'blocked',
            candidate=str(destination) if destination else None, model_message_received=True,
            reasons=read_json(attempt / 'result.json').get('reasons', []) if not destination else []))
        return destination


def worker(config, request):
    """Stream the configured provider; credentials remain in the worker environment only."""
    key = os.environ.get(config['model_api_key_environment'])
    if not key:
        raise ValueError('Configured API-key environment variable is empty')
    messages = [dict(role='system', content=request['prompt']),
                dict(role='user', content=json.dumps(dict(attachments=request['attachments'], targets=request['targets']), ensure_ascii=False))]
    if config['model_provider'] == 'litellm':
        import litellm
        litellm.suppress_debug_info = True
        response = litellm.completion(model=config['model_name'], api_base=config['model_base_url'], api_key=key,
            messages=messages, stream=config['model_stream'], timeout=config['model_timeout_seconds'])
        if config['model_stream']:
            for chunk in response:
                if chunk.choices:
                    text = chunk.choices[0].delta.content
                    if text:
                        print(json.dumps(dict(delta=text)), flush=True)
        elif response.choices and response.choices[0].message.content:
            print(json.dumps(dict(delta=response.choices[0].message.content)), flush=True)
    elif config['model_provider'] == 'gemini':
        from google import genai
        client = genai.Client(api_key=key, http_options=dict(base_url=config['model_base_url'],
            timeout=config['model_timeout_seconds'] * 1000))
        try:
            options = dict(model=config['model_name'], contents=messages[1]['content'],
                           config=dict(system_instruction=request['prompt']))
            if config['model_stream']:
                for chunk in client.models.generate_content_stream(**options):
                    if chunk.text:
                        print(json.dumps(dict(delta=chunk.text)), flush=True)
            else:
                response = client.models.generate_content(**options)
                if response.text:
                    print(json.dumps(dict(delta=response.text)), flush=True)
        finally:
            client.close()
    else:
        raise ValueError('Unsupported model_provider')
    print(json.dumps(dict(done=True)), flush=True)


if __name__ == '__main__':
    from format_library.configuration import load_config
    try:
        worker(load_config(sys.argv[1]), read_json(sys.argv[2]))
    except Exception as error:
        # Provider exceptions can include API keys and endpoints. Never emit their raw contents.
        print(json.dumps(dict(error='Provider delivery failed (' + type(error).__name__ + '); no complete model message received')), flush=True)
        raise SystemExit(1)
