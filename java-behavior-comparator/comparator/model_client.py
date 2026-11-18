"""Own model transport with common provider settings; no other tool is imported."""
import json
import os
import urllib.request
from urllib.parse import urlparse


def request(settings, stage, prompt, payload, timeout):
    """Request one bounded JSON result; credentials stay in HTTP headers, never artifacts."""
    base=settings['model_base_url'].rstrip('/')
    if (settings['model_provider']!='gemini' and urlparse(base).scheme not in {'http','https'}) or not settings['model_name'] or 'REPLACE' in base+settings['model_name']:
        raise ValueError('Configure model_name and model_base_url in the common converter YAML')
    key=os.environ.get(settings['model_api_key_environment'])
    if not key: raise ValueError('Set comparator API-key environment: '+settings['model_api_key_environment'])
    body=dict(model=settings['model_name'],stream=False,messages=[
        dict(role='system',content=prompt),dict(role='user',content=json.dumps(dict(stage=stage,**payload),ensure_ascii=False))])
    try:
        if settings['model_provider'] in {'gemini','litellm'}:
            from comparator.provider_transport import request_provider
            text=request_provider(settings,body['messages'],timeout)
        else:
            outgoing=urllib.request.Request(base+'/chat/completions',data=json.dumps(body).encode('utf-8'),
                headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
            with urllib.request.urlopen(outgoing,timeout=timeout) as incoming:
                raw=incoming.read(settings['response_character_limit']*4+1)
            if len(raw)>settings['response_character_limit']*4: raise ValueError('Model response exceeded limit')
            envelope=json.loads(raw)
            text=envelope['choices'][0]['message']['content']
    except Exception as error:
        # Upstream exceptions/bodies may contain credentials; retain only the error category.
        raise ValueError('Comparator model delivery failed ('+type(error).__name__+')') from None
    if not isinstance(text,str) or len(text)>settings['response_character_limit']:
        raise ValueError('Invalid or oversized model response')
    return text
