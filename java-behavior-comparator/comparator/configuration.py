"""Own YAML settings for the independent comparator; foreign tool configs are not loaded."""
import codecs
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = dict(model_provider='openai_compatible', model_name='', model_base_url='',
    model_api_key_environment='COMPARISON_AI_API_KEY', model_timeout_seconds=120,
    max_model_attempts=2, max_model_calls=200, max_run_seconds=3300,
    request_character_limit=45000, response_character_limit=100000,
    catalog_page_size=12, max_evidence_rounds=3, max_interaction_pairs=100, index_timeout_seconds=300,
    java_home=None, maven_command='mvn', source_excludes=['.git','target','build','bin','.venv','node_modules'])


def load(path):
    """Validate independent settings and resolve its selected JDK location."""
    path = Path(path).resolve()
    value = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict) or set(value) - set(DEFAULTS):
        raise ValueError('Comparator configuration must contain only its documented settings')
    settings = {**DEFAULTS, **value}
    for key in ('model_timeout_seconds','max_model_attempts','max_model_calls','max_run_seconds',
                'request_character_limit','response_character_limit','catalog_page_size','max_evidence_rounds','max_interaction_pairs','index_timeout_seconds'):
        if type(settings[key]) is not int or settings[key] <= 0:
            raise ValueError(key + ' must be a positive integer')
    if settings['model_provider'] not in {'openai_compatible', 'openai', 'litellm'}:
        raise ValueError('Use an OpenAI-compatible endpoint, including an organization LiteLLM gateway')
    for key in ('model_name','model_base_url','model_api_key_environment','maven_command'):
        if not isinstance(settings[key], str): raise ValueError(key + ' must be text')
    if not isinstance(settings['source_excludes'], list) or not all(isinstance(v,str) for v in settings['source_excludes']):
        raise ValueError('source_excludes must list directory names')
    if settings['java_home']:
        settings['java_home'] = str((path.parent / settings['java_home']).resolve())
    return settings
