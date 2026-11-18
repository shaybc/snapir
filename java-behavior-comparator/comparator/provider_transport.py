"""Use the common converter's provider names without importing its model client."""
import contextlib
import sys


def request_provider(settings, messages, timeout):
    """Return text from LiteLLM or Gemini; SDK diagnostics must never pollute JSON stdout."""
    import os
    key = os.environ[settings['model_api_key_environment']]
    with contextlib.redirect_stdout(sys.stderr):
        if settings['model_provider'] == 'litellm':
            import litellm
            litellm.suppress_debug_info = True
            response = litellm.completion(model=settings['model_name'], api_base=settings['model_base_url'] or None,
                api_key=key, messages=messages, stream=False, timeout=timeout)
            return response.choices[0].message.content
        if settings['model_provider'] == 'gemini':
            from google import genai
            options = dict(timeout=int(timeout * 1000))
            if settings['model_base_url']:
                options['base_url'] = settings['model_base_url']
            client = genai.Client(api_key=key, http_options=options)
            try:
                return client.models.generate_content(model=settings['model_name'].removeprefix('gemini/'), contents=messages[1]['content'],
                    config=dict(system_instruction=messages[0]['content'])).text
            finally:
                client.close()
    raise ValueError('A live model_provider is required for comparison')
